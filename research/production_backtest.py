import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from config.config import SYMBOLS, DXY_SYMBOL, TNX_SYMBOL
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator

from strategies.crt_strategy import CRTStrategy
from strategies.advanced_pattern_strategy import AdvancedPatternStrategy

async def run_production_backtest(days=30):
    print(f"🏛️  CRT + ADVANCED PATTERN PRODUCTION BACKTEST")
    print("="*80)
    print(f"Window: Last {days} days")
    print(f"Models: CRT_ALGORITHM, ADV_PATTERN_ENGINE")
    print("="*80)
    
    fetcher = DataFetcher()
    strategies = {
        'CRT_ALGORITHM':     CRTStrategy(),
        'ADV_PATTERN_ENGINE': AdvancedPatternStrategy(),
    }
    
    start_date = (datetime.now() - timedelta(days=days + 60)).strftime("%Y-%m-%d") # Extra buffer for 200-period EMAs
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    all_data = {}
    for symbol in SYMBOLS:
        print(f"  📥 Fetching {symbol} (MTF)...")
        m5_df  = await fetcher.fetch_range_async(symbol, "5m", start_date, end_date)
        m15_df = await fetcher.fetch_range_async(symbol, "15m", start_date, end_date)
        h1_df  = await fetcher.fetch_range_async(symbol, "1h", start_date, end_date)
        d1_df  = await fetcher.fetch_range_async(symbol, "1d", start_date, end_date)
        
        if any(df is None or df.empty for df in [m5_df, m15_df, h1_df, d1_df]):
            print(f"  ⚠️ Skipping {symbol}: Incomplete data.")
            continue
            
        all_data[symbol] = {
            'm5':  IndicatorCalculator.add_indicators(m5_df, "5m"),
            'm15': IndicatorCalculator.add_indicators(m15_df, "15m"),
            'h1':  IndicatorCalculator.add_indicators(h1_df, "1h"),
            'd1':  IndicatorCalculator.add_indicators(d1_df, "1d")
        }

    # Macro Context
    market_context = {}
    print("  🌍 Fetching Macro Narrative...")
    dxy_df = await fetcher.fetch_range_async(DXY_SYMBOL, "1h", start_date, end_date)
    if dxy_df is not None: market_context['DXY'] = IndicatorCalculator.add_indicators(dxy_df, "1h")
    
    tnx_df = await fetcher.fetch_range_async(TNX_SYMBOL, "1h", start_date, end_date)
    if tnx_df is not None: market_context['^TNX'] = IndicatorCalculator.add_indicators(tnx_df, "1h")

    trades = []
    print("\n🚀 Executing Simulation...")
    
    # Run test only on the last 'days' days to save time, but use full history for indicators
    test_cutoff = datetime.now() - timedelta(days=days)
    
    for symbol, data in all_data.items():
        h1_df = data['h1']
        # Filter for the actual test window
        test_indices = h1_df[h1_df.index > test_cutoff.replace(tzinfo=h1_df.index.tz)].index
        
        print(f"  🔬 Testing {symbol} ({len(test_indices)} bars)...")
        
        for ts in test_indices:
            # Reconstruct point-in-time data bundles
            h1_idx = h1_df.index.get_loc(ts)
            h1_state = h1_df.iloc[:h1_idx+1]
            
            d1_i = data['d1'].index.get_indexer([ts], method='ffill')[0]
            d1_state = data['d1'].iloc[:d1_i+1]
            
            m15_i = data['m15'].index.get_indexer([ts], method='ffill')[0]
            m15_state = data['m15'].iloc[:m15_i+1]
            
            m5_i = data['m5'].index.get_indexer([ts], method='ffill')[0]
            m5_state = data['m5'].iloc[:m5_i+1]
            
            data_bundle = {'h1': h1_state, 'd1': d1_state, 'm15': m15_state, 'm5': m5_state}
            
            for name, strat in strategies.items():
                signal = await strat.analyze(symbol, data_bundle, [], market_context)
                
                if signal:
                    entry = signal['entry_price']
                    sl = signal['sl']
                    tp = signal['tp0']
                    sl_dist = abs(entry - sl)
                    if sl_dist == 0: continue
                    
                    hit = None
                    pnl_r = 0.0
                    
                    # Simulation range
                    for j in range(m5_i+1, min(m5_i+288, len(data['m5']))): # 24h lookahead
                        fut = data['m5'].iloc[j]
                        if signal['direction'] == "BUY":
                            if fut['low'] <= sl: hit = "LOSS"; pnl_r = -1.0; break
                            if fut['high'] >= tp: hit = "WIN"; pnl_r = (tp - entry) / sl_dist; break
                        else:
                            if fut['high'] >= sl: hit = "LOSS"; pnl_r = -1.0; break
                            if fut['low'] <= tp: hit = "WIN"; pnl_r = (entry - tp) / sl_dist; break
                    
                    if hit:
                        trades.append({'t': ts, 'symbol': symbol, 'strategy': name, 'res': hit, 'r': pnl_r})

    if not trades:
        print("\n🏁 Backtest Complete: No trades generated in this window.")
        return
        
    df_results = pd.DataFrame(trades)
    print("\n" + "="*80)
    print(f"{'V28.1 PRODUCTION ALPHA REPORT':^80}")
    print("="*80)
    print(f"{'MODEL':<20} | {'TRADES':>6} | {'WIN%':>8} | {'PROF (R)':>10} | {'PF':>6}")
    print("-" * 80)
    
    for name in strategies.keys():
        sub = df_results[df_results['strategy'] == name]
        if sub.empty: continue
        wr = (sub['res'] == 'WIN').mean() * 100
        total_p = sub['r'].sum()
        win_sum = sub[sub['r'] > 0]['r'].sum()
        loss_sum = abs(sub[sub['r'] < 0]['r'].sum())
        pf = win_sum / loss_sum if loss_sum > 0 else float('inf')
        print(f"{name:<20} | {len(sub):>6} | {wr:>7.1f}% | {total_p:>9.1f}R | {pf:>6.2f}")
        
    print("-" * 80)
    print(f"TOTAL PERFORMANCE: {df_results['r'].sum():.1f}R over {len(df_results)} trades.")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(run_production_backtest(30))
