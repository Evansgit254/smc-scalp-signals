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

async def run_high_fidelity_backtest():
    # Last 7 days to ensure M1 availability
    start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    print(f"🚀 HIGH-FIDELITY 7-DAY M1 BACKTEST: {start_date} to {end_date}")
    
    global_results = []
    
    for symbol in SYMBOLS:
        print(f"\n--- Analyzing {symbol} (M1/M5 Logic) ---")
        # Fetch high-res data
        m5_df = DataFetcher.fetch_range(symbol, BIAS_TF, start=start_date, end=end_date)
        m1_df = DataFetcher.fetch_range(symbol, ENTRY_TF, start=start_date, end=end_date)
        
        if m5_df is None or m1_df is None or m1_df.empty:
            print(f"   Insufficient M1 data for {symbol}. Moving on...")
            continue
            
        m5_df = IndicatorCalculator.add_indicators(m5_df, "m5")
        m1_df = IndicatorCalculator.add_indicators(m1_df, "m1")
        
        setups = []
        # Use M1 for detection to match live logic
        i = 100
        while i < len(m1_df):
            current_m1 = m1_df.iloc[:i+1]
            t = current_m1.index[-1]
            
            # Align M5 bias
            state_m5 = m5_df[m5_df.index <= t]
            if state_m5.empty:
                i += 1
                continue
            
            bias = BiasAnalyzer.get_bias(state_m5)
            if bias == "NEUTRAL":
                i += 1
                continue
            
            sweep = LiquidityDetector.detect_sweep(current_m1, bias)
            if not sweep:
                i += 1
                continue
            
            direction = "BUY" if bias == "BULLISH" else "SELL"
            displaced = DisplacementAnalyzer.is_displaced(current_m1, direction)
            entry_valid = EntryLogic.check_pullback(current_m1, direction)
            
            # Use production Scoring weights
            score_details = {
                'bias_strength': True,
                'sweep_type': sweep['type'],
                'displaced': displaced,
                'pullback': entry_valid is not None,
                'session': "Active Market", 
                'volatile': True
            }
            score = ScoringEngine.calculate_score(score_details)
            
            # Test against adjusted threshold for holiday study
            if score >= 8.0: 
                atr = current_m1.iloc[-1]['atr']
                levels = EntryLogic.calculate_levels(current_m1, direction, sweep['level'], atr)
                
                win = False
                loss = False
                # Hold for up to 60 mins
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
                        if future_bar['high'] >= levels['sl']:
                            loss = True
                            break
                        if future_bar['low'] <= levels['tp2']:
                            win = True
                            break
                
                if win or loss:
                    result = "WIN" if win else "LOSS"
                    setups.append({
                        'time': t,
                        'symbol': symbol,
                        'dir': direction,
                        'score': score,
                        'result': result
                    })
                    i += 30 # Avoid cluster signals
                else:
                    i += 1
            else:
                i += 1

        if setups:
            wins = sum(1 for s in setups if s['result'] == "WIN")
            losses = sum(1 for s in setups if s['result'] == "LOSS")
            acc = (wins / (wins + losses)) * 100
            print(f"✅ {symbol}: {len(setups)} signals | {wins}W - {losses}L | Acc: {acc:.1f}%")
            global_results.extend(setups)
            for s in setups:
                color = "🟢" if s['result'] == "WIN" else "🔴"
                print(f"   {color} [{s['time']}] {s['dir']} Signal (Score: {s['score']})")
        else:
            print(f"   No production-grade signals found for {symbol} this week.")

    print("\n" + "═"*40)
    print(f"🏆 HIGH-FIDELITY SUMMARY")
    t_w = sum(1 for r in global_results if r['result'] == "WIN")
    t_l = sum(1 for r in global_results if r['result'] == "LOSS")
    t_acc = (t_w / (t_w + t_l)) * 100 if (t_w + t_l) > 0 else 0
    print(f"Total Precise Signals: {len(global_results)}")
    print(f"Overall Accuracy: {t_acc:.1f}% ({t_w} Wins / {t_l} Losses)")
    print("═"*40)

if __name__ == "__main__":
    asyncio.run(run_high_fidelity_backtest())
