import asyncio
import pandas as pd
from datetime import datetime, timedelta
from config.config import SYMBOLS, SPREAD_PIPS, SLIPPAGE_PIPS
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator
from strategies.intraday_quant_strategy import IntradayQuantStrategy
from strategies.swing_quant_strategy import SwingQuantStrategy

async def run_dual_backtest(days=30):
    print(f"📊 DUAL-TIMEFRAME BACKTEST (Last {days} days)")
    print("="*70)
    
    from config.config import DXY_SYMBOL, TNX_SYMBOL
    
    fetcher = DataFetcher()
    intraday_strategy = IntradayQuantStrategy()
    swing_strategy = SwingQuantStrategy()
    
    start_date = (datetime.now() - timedelta(days=days + 10)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    # Fetch macro context for filters
    print("📊 Fetching macro context...")
    market_context = {}
    try:
        dxy_df = fetcher.fetch_range(DXY_SYMBOL, "1h", start_date, end_date)
        tnx_df = fetcher.fetch_range(TNX_SYMBOL, "1h", start_date, end_date)
        
        if dxy_df is not None and not dxy_df.empty:
            market_context['DXY'] = IndicatorCalculator.add_indicators(dxy_df, "1h")
        if tnx_df is not None and not tnx_df.empty:
            market_context['^TNX'] = IndicatorCalculator.add_indicators(tnx_df, "1h")
    except Exception as e:
        print(f"⚠️  Warning: Could not fetch macro context: {e}")
    
    # Fetch data for all symbols
    all_data = {}
    for symbol in SYMBOLS:
        print(f"Fetching {symbol}...")
        m5_df = fetcher.fetch_range(symbol, "5m", start_date, end_date)
        h1_df = fetcher.fetch_range(symbol, "1h", start_date, end_date)
        
        if m5_df is None or m5_df.empty or h1_df is None or h1_df.empty:
            continue
            
        all_data[symbol] = {
            'm5': IndicatorCalculator.add_indicators(m5_df, "5m"),
            'h1': IndicatorCalculator.add_indicators(h1_df, "1h")
        }
    
    if not all_data:
        print("❌ No data loaded for any symbol. Check date range / fetch.")
        return
    
    m5_lens = [len(d['m5']) for d in all_data.values()]
    h1_lens = [len(d['h1']) for d in all_data.values()]
    print(f"✅ Loaded {len(all_data)} symbols. M5 bars: min={min(m5_lens)}, max={max(m5_lens)}. H1 bars: min={min(h1_lens)}, max={max(h1_lens)}")
    
    intraday_trades = []
    swing_trades = []
    
    # Backtest Intraday (M5)
    print("\n🔄 Testing Intraday Strategy (M5)...")
    for symbol, data in all_data.items():
        df = data['m5']
        for i in range(200, len(df)-288):
            state = df.iloc[:i+1]
            # Create time-appropriate market context (use latest available)
            current_market_context = {}
            if 'DXY' in market_context:
                # Get DXY data up to current time
                dxy_current = market_context['DXY'].iloc[:min(i*12, len(market_context['DXY']))]
                if not dxy_current.empty:
                    current_market_context['DXY'] = dxy_current
            if '^TNX' in market_context:
                tnx_current = market_context['^TNX'].iloc[:min(i*12, len(market_context['^TNX']))]
                if not tnx_current.empty:
                    current_market_context['^TNX'] = tnx_current
            
            signal = await intraday_strategy.analyze(symbol, {'m5': state}, [], current_market_context)
            
            if signal:
                entry = signal['entry_price']
                sl = signal['sl']
                tp = signal['tp0']
                
                # Spread adjustment
                half_spread = (SPREAD_PIPS / 2.0) / 10000.0
                if "JPY" in symbol: half_spread = (SPREAD_PIPS / 2.0) / 100.0
                
                hit = None
                for j in range(i+1, min(i+288, len(df))):
                    fut = df.iloc[j]
                    if signal['direction'] == "BUY":
                        if (fut['low'] - half_spread) <= sl: hit = "LOSS"; break
                        if (fut['high'] - half_spread) >= tp: hit = "WIN"; break
                    else:
                        if (fut['high'] + half_spread) >= sl: hit = "LOSS"; break
                        if (fut['low'] + half_spread) <= tp: hit = "WIN"; break
                
                if hit:
                    r_val = 2.5 if hit == "WIN" else -1.0
                    
                    # Capture factor details for forensic audit
                    factors = signal.get('score_details', {})
                    
                    intraday_trades.append({
                        't': df.index[i],
                        'symbol': symbol,
                        'res': hit,
                        'r': r_val,
                        'strategy': 'INTRADAY',
                        'velocity': factors.get('velocity', 0),
                        'zscore': factors.get('zscore', 0),
                        'signal': factors.get('signal', 0)
                    })
    
    # Backtest Swing (H1)
    print("🔄 Testing Swing Strategy (H1)...")
    for symbol, data in all_data.items():
        df = data['h1']
        for i in range(200, len(df)-168):
            state = df.iloc[:i+1]
            # Create time-appropriate market context
            current_market_context = {}
            if 'DXY' in market_context:
                dxy_current = market_context['DXY'].iloc[:min(i, len(market_context['DXY']))]
                if not dxy_current.empty:
                    current_market_context['DXY'] = dxy_current
            if '^TNX' in market_context:
                tnx_current = market_context['^TNX'].iloc[:min(i, len(market_context['^TNX']))]
                if not tnx_current.empty:
                    current_market_context['^TNX'] = tnx_current
            
            signal = await swing_strategy.analyze(symbol, {'h1': state}, [], current_market_context)
            
            if signal:
                entry = signal['entry_price']
                sl = signal['sl']
                tp = signal['tp0']
                
                half_spread = (SPREAD_PIPS / 2.0) / 10000.0
                if "JPY" in symbol: half_spread = (SPREAD_PIPS / 2.0) / 100.0
                
                hit = None
                for j in range(i+1, min(i+168, len(df))):
                    fut = df.iloc[j]
                    if signal['direction'] == "BUY":
                        if (fut['low'] - half_spread) <= sl: hit = "LOSS"; break
                        if (fut['high'] - half_spread) >= tp: hit = "WIN"; break
                    else:
                        if (fut['high'] + half_spread) >= sl: hit = "LOSS"; break
                        if (fut['low'] + half_spread) <= tp: hit = "WIN"; break
                
                if hit:
                    r_val = 5.0 if hit == "WIN" else -1.0  # Swing targets are bigger
                    
                    # Capture factor details
                    factors = signal.get('score_details', {})
                    
                    swing_trades.append({
                        't': df.index[i],
                        'symbol': symbol,
                        'res': hit,
                        'r': r_val,
                        'strategy': 'SWING',
                        'velocity': factors.get('velocity', 0),
                        'zscore': factors.get('zscore', 0),
                        'signal': factors.get('signal', 0)
                    })
    
    # Detailed CSV Logging
    print("\n📝 Saving detailed trade logs...")
    all_trades = intraday_trades + swing_trades
    if all_trades:
        df_log = pd.DataFrame(all_trades)
        df_log.to_csv("research/backtest_trade_logs.csv", index=False)
        print(f"✅ Saved {len(df_log)} trades to research/backtest_trade_logs.csv")
    
    # Results
    print("\n" + "="*70)
    print("📈 DUAL-TIMEFRAME BACKTEST RESULTS")
    print("="*70)
    
    def calc_metrics(trades, name):
        if not trades:
            print(f"\n{name}: No trades generated")
            return
            
        df = pd.DataFrame(trades)
        total = len(df)
        wins = len(df[df['res'] == 'WIN'])
        losses = len(df[df['res'] == 'LOSS'])
        wr = (wins / total) * 100
        
        total_r = df['r'].sum()
        expectancy = total_r / total
        
        win_r = df[df['r'] > 0]['r'].sum()
        loss_r = abs(df[df['r'] < 0]['r'].sum())
        pf = win_r / loss_r if loss_r != 0 else float('inf')
        
        print(f"\n{name}")
        print("-"*70)
        print(f"{'Total Trades':<30} | {total}")
        print(f"{'Wins':<30} | {wins}")
        print(f"{'Losses':<30} | {losses}")
        print(f"{'Win Rate':<30} | {wr:.2f}%")
        print(f"{'Profit Factor':<30} | {pf:.2f}")
        print(f"{'Total R-Multiple':<30} | {total_r:.1f}R")
        print(f"{'Expectancy':<30} | {expectancy:.4f}R")
    
    calc_metrics(intraday_trades, "🎯 INTRADAY SCALP (M5)")
    calc_metrics(swing_trades, "🎯 SWING POSITION (H1)")
    
    print("\n" + "="*70)

if __name__ == "__main__":
    import sys
    days = 30
    if len(sys.argv) > 1:
        try:
            days = int(sys.argv[1])
        except ValueError:
            pass
    # Note: 60+ day backtest may yield no data (Yahoo 5m history limit). Use 30 days for reliable run.
    asyncio.run(run_dual_backtest(days=days))
