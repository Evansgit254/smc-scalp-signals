import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from config.config import SYMBOLS, SPREAD_PIPS, DXY_SYMBOL, TNX_SYMBOL
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator
from strategies.intraday_quant_strategy import IntradayQuantStrategy
from strategies.swing_quant_strategy import SwingQuantStrategy
from strategies.session_clock_strategy import SessionClockStrategy
from strategies.advanced_pattern_strategy import AdvancedPatternStrategy
from strategies.gold_quant_strategy import GoldQuantStrategy
from strategies.statistical_arbitrage_strategy import StatisticalArbitrageStrategy
from strategies.smc_liquidity_sweep import SMCLiquiditySweepStrategy
from strategies.anchored_poc_strategy import AnchoredPOCStrategy
from strategies.pre_news_quant_strategy import PreNewsQuantStrategy

# Disable warnings for clean output
import warnings

async def run_master_backtest(days=30):
    print(f"🚀 MASTER BACKTEST V23 (Last {days} days)")
    print("="*80)
    
    fetcher = DataFetcher()
    strategies = {
        'INTRADAY': IntradayQuantStrategy(),
        'SWING':    SwingQuantStrategy(),
        'CLOCK':    SessionClockStrategy(),
        'ADVANCED': AdvancedPatternStrategy(),
        'GOLD_Q':   GoldQuantStrategy(),
        'STAT_ARB': StatisticalArbitrageStrategy(),
        'SMC_SWEEP':  SMCLiquiditySweepStrategy(),
        'POC_EDGE':   AnchoredPOCStrategy(),
        'PRE_NEWS':   PreNewsQuantStrategy(),
    }
    
    start_date = (datetime.now() - timedelta(days=days + 15)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    all_data = {}
    for symbol in SYMBOLS:
        print(f"  Fetching {symbol}...")
        m5_df = fetcher.fetch_range(symbol, "5m", start_date, end_date)
        h1_df = fetcher.fetch_range(symbol, "1h", start_date, end_date)
        
        if m5_df is None or m5_df.empty or h1_df is None or h1_df.empty:
            continue
            
        all_data[symbol] = {
            'm5': IndicatorCalculator.add_indicators(m5_df, "5m"),
            'h1': IndicatorCalculator.add_indicators(h1_df, "1h")
        }

    if not all_data:
        print("❌ No data loaded.")
        return

    # Load macro context for Stat Arb and Gold strategies
    market_context = {}
    try:
        dxy_df = fetcher.fetch_range(DXY_SYMBOL, "1h", start_date, end_date)
        if dxy_df is not None and not dxy_df.empty:
            market_context['DXY'] = IndicatorCalculator.add_indicators(dxy_df, "1h")
            print(f"  ✅ DXY loaded: {len(market_context['DXY'])} bars")
        tnx_df = fetcher.fetch_range(TNX_SYMBOL, "1h", start_date, end_date)
        if tnx_df is not None and not tnx_df.empty:
            market_context['^TNX'] = IndicatorCalculator.add_indicators(tnx_df, "1h")
    except Exception as e:
        print(f"  ⚠️ DXY fetch: {e}")

    trades = []

    for symbol, data in all_data.items():
        print(f"  Testing {symbol}...")
        h1_df = data['h1']
        m5_df = data['m5']
        
        for i in range(200, len(h1_df) - 1):
            ts = h1_df.index[i]
            h1_state = h1_df.iloc[:i+1]
            m5_i = m5_df.index.get_indexer([ts], method='ffill')[0]
            m5_state = m5_df.iloc[:m5_i+1]
            
            data_bundle = {'h1': h1_state, 'm5': m5_state}
            
            for name, strat in strategies.items():
                if symbol == "GC=F" and name != "GOLD_Q":
                    continue
                if symbol != "GC=F" and name == "GOLD_Q":
                    continue
                    
                signal = await strat.analyze(symbol, data_bundle, [], market_context)
                
                if signal:
                    entry = signal['entry_price']
                    sl = signal['sl']
                    tp = signal['tp0']
                    trade_type = signal.get('trade_type', 'QUANT')
                    sl_dist = abs(entry - sl)
                    if sl_dist == 0: continue
                    
                    # V26.2: SESSION_CLOCK now uses TP/SL simulation like all strategies.
                    # Time-exit was masking the fact that TPs were never being hit.
                    # With tighter 1.5 ATR SL and 1.5:1 TP, we now test if the TP is reachable.
                    hit = None
                    pnl_r = 0.0
                    lookahead = 200  # ~16 hours of M5 bars max hold
                    for j in range(m5_i+1, min(m5_i+lookahead, len(m5_df))):
                        fut = m5_df.iloc[j]
                        if signal['direction'] == "BUY":
                            if fut['low'] <= sl: hit = "LOSS"; pnl_r = -1.0; break
                            if fut['high'] >= tp: hit = "WIN"; pnl_r = (tp - entry) / sl_dist; break
                        else:
                            if fut['high'] >= sl: hit = "LOSS"; pnl_r = -1.0; break
                            if fut['low'] <= tp: hit = "WIN"; pnl_r = (entry - tp) / sl_dist; break
                    
                    if hit:
                        trades.append({'t': ts, 'symbol': symbol, 'strategy': name, 'res': hit, 'r': pnl_r})

    if not trades:
        print("No trades found.")
        return
        
    df_results = pd.DataFrame(trades)
    print("\n" + "="*80)
    print(f"{'STRATEGY':<15} | {'N':>5} | {'WIN%':>8} | {'PF':>6} | {'EXP':>8}")
    print("-" * 80)
    
    for name in strategies.keys():
        sub = df_results[df_results['strategy'] == name]
        if sub.empty: continue
        wr = (sub['res'] == 'WIN').mean() * 100
        win_r = sub[sub['r'] > 0]['r'].sum()
        loss_r = abs(sub[sub['r'] < 0]['r'].sum())
        pf = win_r / loss_r if loss_r > 0 else float('inf')
        print(f"{name:<15} | {len(sub):>5} | {wr:>7.1f}% | {pf:>6.2f} | {sub['r'].mean():>7.3f}R")
        
    total_r = df_results['r'].sum()
    print("-" * 80)
    print(f"Total Trades: {len(df_results)}  |  Total Profit: {total_r:.1f}R")
    print("="*80)

if __name__ == "__main__":
    import sys
    d = 30
    if len(sys.argv) > 1: d = int(sys.argv[1])
    asyncio.run(run_master_backtest(d))
