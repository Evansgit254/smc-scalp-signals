import asyncio
import pandas as pd
from datetime import datetime, timedelta
from config.config import SYMBOLS, EMA_TREND, EMA_FAST, EMA_SLOW
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator
from structure.bias import BiasAnalyzer
from liquidity.sweep_detector import LiquidityDetector
from strategy.displacement import DisplacementAnalyzer
from strategy.entry import EntryLogic
from strategy.scoring import ScoringEngine

async def run_intraday_backtest(start_date: str, end_date: str):
    print(f"🕵️ TOP-DOWN INTRADAY BACKTEST: {start_date} to {end_date}")
    print("Logic: 1H Narrative -> 15M Sweep -> 5M Entry Rejection")
    
    total_wins = 0
    total_losses = 0
    
    for symbol in SYMBOLS:
        print(f"\n--- Backtesting {symbol} ---")
        # Fetch required data
        h1_df = DataFetcher.fetch_range(symbol, "1h", start=start_date, end=end_date)
        m15_df = DataFetcher.fetch_range(symbol, "15m", start=start_date, end=end_date)
        m5_df = DataFetcher.fetch_range(symbol, "5m", start=start_date, end=end_date)
        
        if any(df is None or df.empty for df in [h1_df, m15_df, m5_df]):
            print(f"   Missing data for {symbol}. Skipping...")
            continue
            
        # Add Indicators
        h1_df = IndicatorCalculator.add_indicators(h1_df, "h1")
        m15_df = IndicatorCalculator.add_indicators(m15_df, "15m")
        m5_df = IndicatorCalculator.add_indicators(m5_df, "5m")
        
        setups = []
        # Iterate through M15 data for setups
        idx = 100
        while idx < len(m15_df):
            t = m15_df.index[idx]
            
            # 1. Align Narrative (H1)
            state_h1 = h1_df[h1_df.index <= t]
            if state_h1.empty: 
                idx += 1
                continue
                
            h1_trend = "BULLISH" if state_h1.iloc[-1]['close'] > state_h1.iloc[-1][f'ema_{EMA_TREND}'] else "BEARISH"
            
            # 2. Structural Sweep (M15)
            state_m15 = m15_df.iloc[:idx+1]
            # Simple rejection for backtest
            prev_low = state_m15.iloc[-21:-1]['low'].min()
            prev_high = state_m15.iloc[-21:-1]['high'].max()
            latest = state_m15.iloc[-1]
            
            direction = None
            sweep_level = None
            
            if h1_trend == "BULLISH" and latest['low'] < prev_low and latest['close'] > prev_low:
                direction = "BUY"
                sweep_level = prev_low
            elif h1_trend == "BEARISH" and latest['high'] > prev_high and latest['close'] < prev_high:
                direction = "SELL"
                sweep_level = prev_high
                
            if not direction:
                idx += 1
                continue
                
            # 3. Entry Confirmation (M5 within M15 window)
            m5_window = m5_df[(m5_df.index >= t) & (m5_df.index < t + pd.Timedelta(minutes=15))]
            if m5_window.empty:
                idx += 1
                continue
                
            # ATR from M15
            atr = latest['atr']
            levels = EntryLogic.calculate_levels(state_m15, direction, sweep_level, atr)
            
            # 4. Check Outcome (Next 24 hours on M5)
            win = False
            loss = False
            # Find the index in m5_df to start checking
            m5_start_idx = m5_df.index.get_indexer([t], method='nearest')[0]
            
            for j in range(m5_start_idx + 1, min(m5_start_idx + 288, len(m5_df))): # 24h of M5
                future_bar = m5_df.iloc[j]
                if direction == "BUY":
                    if future_bar['low'] <= levels['sl']:
                        loss = True
                        break
                    if future_bar['high'] >= levels['tp2']:
                        win = True
                        break
                else:
                    if future_bar['high'] >= levels['sl']:
                        loss = True
                        break
                    if future_bar['low'] <= levels['tp2']:
                        win = True
                        break
            
            if win or loss:
                result = "WIN" if win else "LOSS"
                setups.append(result)
                idx += 16 # Avoid cluster signals (skip 4 hours)
            else:
                idx += 1

        if setups:
            w = setups.count("WIN")
            l = setups.count("LOSS")
            acc = (w / (w + l)) * 100 if (w + l) > 0 else 0
            print(f"✔️ {symbol}: {len(setups)} setups | {w}Wins - {l}Losses | Acc: {acc:.1f}%")
            total_wins += w
            total_losses += l
        else:
            print(f"   No setups found for {symbol}.")

    print("\n" + "═"*40)
    print(f"🏁 GLOBAL INTRADAY SUMMARY")
    denominator = total_wins + total_losses
    total_acc = (total_wins / denominator) * 100 if denominator > 0 else 0
    print(f"Total Setups: {denominator}")
    print(f"Total Wins: {total_wins} | Total Losses: {total_losses}")
    print(f"Success Rate: {total_acc:.1f}%")
    print("═"*40)

if __name__ == "__main__":
    # Start from Dec 4 to Jan 4
    start = (datetime.now() - timedelta(days=32)).strftime("%Y-%m-%d")
    end = datetime.now().strftime("%Y-%m-%d")
    asyncio.run(run_intraday_backtest(start, end))
