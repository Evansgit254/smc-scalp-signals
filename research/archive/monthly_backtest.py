import asyncio
import pandas as pd
from datetime import datetime, timedelta
from config.config import SYMBOLS, EMA_FAST, EMA_SLOW
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator
from structure.bias import BiasAnalyzer
from liquidity.sweep_detector import LiquidityDetector
from strategy.displacement import DisplacementAnalyzer
from strategy.entry import EntryLogic
from strategy.scoring import ScoringEngine

async def run_monthly_backtest(start_date: str, end_date: str):
    print(f"📊 MONTHLY BACKTEST (M5 Resolution): {start_date} to {end_date}")
    
    total_wins = 0
    total_losses = 0
    
    for symbol in SYMBOLS:
        print(f"\n--- Backtesting {symbol} ---")
        df = DataFetcher.fetch_range(symbol, "5m", start=start_date, end=end_date)
        
        if df is None or df.empty:
            print(f"   Missing data for {symbol}. Skipping...")
            continue
            
        df = IndicatorCalculator.add_indicators(df, "5m")
        
        symbol_setups = []
        i = 100
        while i < len(df):
            current_df = df.iloc[:i+1]
            t = current_df.index[-1]
            
            bias = BiasAnalyzer.get_bias(current_df)
            if bias == "NEUTRAL":
                i += 1
                continue
            
            # Simple M5 Rejection Logic
            latest = current_df.iloc[-1]
            prev_low = current_df.iloc[-50:-1]['low'].min()
            prev_high = current_df.iloc[-50:-1]['high'].max()
            
            direction = None
            sweep_level = None
            
            if bias == "BULLISH" and latest['low'] < prev_low and latest['close'] > prev_low:
                direction = "BUY"
                sweep_level = prev_low
            elif bias == "BEARISH" and latest['high'] > prev_high and latest['close'] < prev_high:
                direction = "SELL"
                sweep_level = prev_high
            
            if not direction:
                i += 1
                continue
            
            # Displacement check
            displaced = DisplacementAnalyzer.is_displaced(current_df, direction)
            
            # Entry check (Modified for M5)
            entry_valid = False
            if direction == "BUY":
                if current_df.iloc[-1]['low'] <= current_df.iloc[-1][f'ema_{EMA_FAST}'] * 1.002:
                    if any(current_df.iloc[-5:]['rsi'] < 45):
                        entry_valid = True
            else: # SELL
                if current_df.iloc[-1]['high'] >= current_df.iloc[-1][f'ema_{EMA_FAST}'] * 0.998:
                    if any(current_df.iloc[-5:]['rsi'] > 55):
                        entry_valid = True
            
            # Scoring
            score_details = {
                'bias_strength': True,
                'sweep_type': "M5_REJECTION",
                'displaced': displaced,
                'pullback': entry_valid,
                'session': "Mixed",
                'volatile': True
            }
            score = ScoringEngine.calculate_score(score_details)
            
            if score >= 6.5: # Lowered threshold for M5 statistical study
                atr = current_df.iloc[-1]['atr']
                levels = EntryLogic.calculate_levels(current_df, direction, sweep_level, atr)
                
                win = False
                loss = False
                for j in range(i + 1, min(i + 49, len(df))):
                    future_bar = df.iloc[j]
                    if direction == "BUY":
                        if future_bar['low'] <= levels['sl']:
                            loss = True
                            break
                        if future_bar['high'] >= levels['tp2']:
                            win = True
                            break
                    else: # SELL
                        if future_bar['high'] >= levels['sl']:
                            loss = True
                            break
                        if future_bar['low'] <= levels['tp2']:
                            win = True
                            break
                
                if win or loss:
                    result = "WIN" if win else "LOSS"
                    symbol_setups.append(result)
                    i += 24 # 2 hour cooldown to avoid clustering
                else:
                    i += 1
            else:
                i += 1

        if symbol_setups:
            wins = symbol_setups.count("WIN")
            losses = symbol_setups.count("LOSS")
            acc = (wins / (wins + losses)) * 100 if (wins + losses) > 0 else 0
            print(f"✔️ {symbol}: {len(symbol_setups)} setups | Wins: {wins} | Losses: {losses} | Accuracy: {acc:.1f}%")
            total_wins += wins
            total_losses += losses
        else:
            print(f"   No setups met our M5 filters for {symbol}.")

    print("\n" + "="*40)
    print(f"🏁 GLOBAL BACKTEST SUMMARY")
    denominator = total_wins + total_losses
    total_acc = (total_wins / denominator) * 100 if denominator > 0 else 0
    print(f"Total Setups: {denominator}")
    print(f"Total Wins: {total_wins} | Total Losses: {total_losses}")
    print(f"Weighted Success Rate: {total_acc:.1f}%")
    print("="*40)

if __name__ == "__main__":
    start = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    end = datetime.now().strftime("%Y-%m-%d")
    asyncio.run(run_monthly_backtest(start, end))
