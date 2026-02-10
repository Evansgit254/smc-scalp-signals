import asyncio
import pandas as pd
from datetime import datetime, timedelta
from config.config import SYMBOLS, BIAS_TF, ENTRY_TF, MIN_CONFIDENCE_SCORE
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator
from structure.bias import BiasAnalyzer
from liquidity.sweep_detector import LiquidityDetector
from strategy.displacement import DisplacementAnalyzer
from strategy.entry import EntryLogic
from strategy.scoring import ScoringEngine

async def run_weekly_replay(start_date: str, end_date: str):
    print(f"🚀 WEEKLY HISTORICAL REPLAY: {start_date} to {end_date}")
    
    for symbol in SYMBOLS:
        print(f"\n--- Analyzing {symbol} ---")
        # Fetch data for the range
        m5_df = DataFetcher.fetch_range(symbol, BIAS_TF, start=start_date, end=end_date)
        m1_df = DataFetcher.fetch_range(symbol, ENTRY_TF, start=start_date, end=end_date)
        
        if m5_df is None or m1_df is None:
            print(f"   Missing data for {symbol}. Skipping...")
            continue
            
        # Add Indicators
        m5_df = IndicatorCalculator.add_indicators(m5_df, "m5")
        m1_df = IndicatorCalculator.add_indicators(m1_df, "m1")
        
        setups = []
        # Iterate through M1 data
        # We start a bit into the data to have enough history for indicators
        for i in range(100, len(m1_df)):
            current_m1 = m1_df.iloc[:i+1]
            t = current_m1.index[-1]
            
            # Get M5 state for this time
            state_m5 = m5_df[m5_df.index <= t]
            if state_m5.empty: continue
            
            bias = BiasAnalyzer.get_bias(state_m5)
            if bias == "NEUTRAL": continue
            
            sweep = LiquidityDetector.detect_sweep(current_m1, bias)
            if not sweep: continue
            
            direction = "BUY" if bias == "BULLISH" else "SELL"
            displaced = DisplacementAnalyzer.is_displaced(current_m1, direction)
            entry_valid = EntryLogic.check_pullback(current_m1, direction)
            
            # Scoring
            score_details = {
                'bias_strength': True,
                'sweep_type': sweep['type'],
                'displaced': displaced,
                'pullback': entry_valid is not None,
                'session': "London Open", # Forced for replay to evaluate core logic
                'volatile': True
            }
            score = ScoringEngine.calculate_score(score_details)
            
            if score >= 7.0: # Moderate threshold for New Year's week study
                atr = current_m1.iloc[-1]['atr']
                levels = EntryLogic.calculate_levels(current_m1, direction, sweep['level'], atr)
                
                # Check outcome (next 60 minutes)
                win = False
                loss = False
                pnl = 0
                for j in range(i + 1, min(i + 61, len(m1_df))):
                    future_bar = m1_df.iloc[j]
                    if direction == "BUY":
                        if future_bar['low'] <= levels['sl']:
                            loss = True
                            break
                        if future_bar['high'] >= levels['tp2']:
                            win = True
                            break
                    else: # SELL
                        if future_bar['high'] <= levels['sl']:
                            loss = True
                            break
                        if future_bar['low'] >= levels['tp2']:
                            win = True
                            break
                
                result = "WIN" if win else ("LOSS" if loss else "EXPIRED")
                setups.append({
                    'time': t,
                    'direction': direction,
                    'score': score,
                    'logic': sweep['description'],
                    'result': result
                })
                # Skip 30 bars to avoid duplicate signals
                i += 30

        if setups:
            wins = sum(1 for s in setups if s['result'] == "WIN")
            losses = sum(1 for s in setups if s['result'] == "LOSS")
            expired = sum(1 for s in setups if s['result'] == "EXPIRED")
            accuracy = (wins / (wins + losses)) * 100 if (wins + losses) > 0 else 0
            
            print(f"📊 Summary for {symbol}:")
            print(f"   Total Setups: {len(setups)}")
            print(f"   Wins: {wins} | Losses: {losses} | Expired: {expired}")
            print(f"   Success Rate: {accuracy:.1f}%")
            
            for s in setups:
                print(f"   [{s['time']}] {s['direction']} (Score: {s['score']}) - {s['result']} | {s['logic']}")
        else:
            print(f"   No high-confidence setups found for {symbol} this week.")

if __name__ == "__main__":
    # Last Monday to Friday
    # yfinance end date is exclusive
    asyncio.run(run_weekly_replay("2025-12-29", "2026-01-03"))
