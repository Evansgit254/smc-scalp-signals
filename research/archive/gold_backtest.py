import asyncio
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List
import sys
import os

# Ensure project root is in path
sys.path.append(os.getcwd())

from config.config import SYMBOLS
from data.fetcher import DataFetcher
from strategies.smc_strategy import SMCStrategy
from indicators.calculations import IndicatorCalculator
from audit.optimizer import AutoOptimizer

# Override Symbols for Gold Test
GOLD_SYMBOLS = ["GC=F"]

async def run_gold_backtest(days: int = 7):
    print(f"🏆 GOLD SPECIALIST BACKTEST (Last {days} days)")
    print(f"Symbols: {GOLD_SYMBOLS}")
    print("Optimization: V13.0 + Gold Specifics (Session 07-21, Lookback 30, Chop allowed)")
    
    # Initialize components
    fetcher = DataFetcher()
    strategy = SMCStrategy()
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    print("Fetching Gold data...")
    # Fetch Data
    all_data = {}
    for symbol in GOLD_SYMBOLS:
        try:
            # Reusing fetch logic (simplified)
            h1 = DataFetcher.fetch_data(symbol, "1h", period=f"{days+5}d")
            m15 = DataFetcher.fetch_data(symbol, "15m", period=f"{days+3}d")
            m5 = DataFetcher.fetch_data(symbol, "5m", period=f"{days+2}d")
            h4 = DataFetcher.fetch_data(symbol, "1h", period=f"{days+20}d") # Approx H4 via H1 resample? Or just H1
            
            if h1 is None or m15 is None or m5 is None:
                print(f"❌ Failed to fetch complete data for {symbol}")
                continue
                
            # ADD INDICATORS (Critical missing step)
            m5 = IndicatorCalculator.add_indicators(m5, "5m")
            m15 = IndicatorCalculator.add_indicators(m15, "15m")
            h1 = IndicatorCalculator.add_indicators(h1, "1h")
            h4 = IndicatorCalculator.add_indicators(h4, "4h")
            
            all_data[symbol] = {
                'h1': h1,
                'm15': m15,
                'm5': m5,
                'h4': h1 # Fallback if H4 not available directly
            }
            print(f"✅ Loaded {symbol} (M5 bars: {len(m5)})")
        except Exception as e:
            print(f"❌ Error loading {symbol}: {e}")

    # Simulation
    trades = []
    
    # Create unified timeline from first valid symbol's M5 data
    if not all_data:
        print("No data available.")
        return

    ref_symbol = list(all_data.keys())[0]
    timeline = all_data[ref_symbol]['m5'].index
    timeline = timeline[timeline >= (start_date.astimezone())]
    
    print(f"Simulating {len(timeline)} bars...")
    
    for i, t in enumerate(timeline):
        if i % 100 == 0: print(f"Processing {t}...", end='\r')
        
        for symbol in all_data:
            data_pack = all_data[symbol]
            
            # Slice data up to time t
            current_m5 = data_pack['m5']
            if t not in current_m5.index: continue
            
            # Slice efficiently
            idx = current_m5.index.get_loc(t)
            if idx < 50: continue
            
            m5_slice = current_m5.iloc[:idx+1]
            
            # Context (Mocking news/macro for speed)
            news = []
            context = {'DXY': None} 
            
            sliced_data = {
                'm5': m5_slice,
                'm15': data_pack['m15'][data_pack['m15'].index <= t],
                'h1': data_pack['h1'][data_pack['h1'].index <= t],
                'h4': data_pack['h4'][data_pack['h4'].index <= t]
            }
            
            # Verify data exists
            if sliced_data['m15'].empty or sliced_data['h1'].empty: continue

            signal = await strategy.analyze(symbol, sliced_data, news, context)
            
            if signal:
                print(f"\n🔮 SIGNAL {t} {symbol} {signal['direction']} Conf: {signal.get('confidence',0):.2f}")
                
                # Check outcome (TP/SL)
                entry_price = m5_slice.iloc[-1]['close']
                entry_price = m5_slice.iloc[-1]['close']
                sl = signal.get('sl', 0) 
                tp = signal.get('tp2', 0)
                
                # Forward test outcome
                outcome = "OPEN"
                pnl = 0
                
                future_data = current_m5.iloc[idx+1:]
                for _, bar in future_data.iterrows():
                    if signal['direction'] == "BUY":
                        if bar['low'] <= sl:
                            outcome = "LOSS"
                            pnl = -1.0
                            break
                        if bar['high'] >= tp:
                            outcome = "WIN"
                            pnl = 2.0
                            break
                    else:
                        if bar['high'] >= sl:
                            outcome = "LOSS"
                            pnl = -1.0
                            break
                        if bar['low'] <= tp:
                            outcome = "WIN"
                            pnl = 2.0
                            break
                
                if outcome == "OPEN": # End of data
                    outcome = "BE" # Assume BE for incomplete
                    pnl = 0
                
                print(f"   Result: {outcome} ({pnl}R)")
                trades.append({
                    'time': t,
                    'symbol': symbol,
                    'dir': signal['direction'],
                    'res': outcome,
                    'r': pnl
                })

    # Summary
    print("\n\n=== GOLD BACKTEST RESULTS ===")
    df = pd.DataFrame(trades)
    if not df.empty:
        print(df.to_string())
        print(f"\nTotal Trades: {len(df)}")
        print(f"Win Rate: {len(df[df['res']=='WIN'])/len(df)*100:.1f}%")
        print(f"Total R: {df['r'].sum()}R")
    else:
        print("No trades generated.")

if __name__ == "__main__":
    asyncio.run(run_gold_backtest())
