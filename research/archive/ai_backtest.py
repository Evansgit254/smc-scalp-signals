import asyncio
import os
from dotenv import load_dotenv
load_dotenv() # Load env vars before importing config

import pandas as pd
from datetime import datetime, timedelta
from config.config import SYMBOLS, EMA_TREND, EMA_FAST, EMA_SLOW, MIN_CONFIDENCE_SCORE
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator
from structure.bias import BiasAnalyzer
from liquidity.sweep_detector import LiquidityDetector
from strategy.displacement import DisplacementAnalyzer
from strategy.entry import EntryLogic
from strategy.scoring import ScoringEngine
from ai.analyst import AIAnalyst

async def run_ai_backtest(start_date: str, end_date: str):
    print(f"🧠 AI-ENHANCED BACKTEST: {start_date} to {end_date}")
    print(f"Logic: Conservative + AI Validation | Score >= {MIN_CONFIDENCE_SCORE}")
    
    total_tp1_wins = 0
    total_tp2_wins = 0
    total_losses = 0
    total_ai_rejected = 0
    
    ai_analyst = AIAnalyst()
    
    for symbol in SYMBOLS:
        print(f"\n--- AI Backtesting {symbol} ---")
        h1_df = DataFetcher.fetch_range(symbol, "1h", start=start_date, end=end_date)
        m15_df = DataFetcher.fetch_range(symbol, "15m", start=start_date, end=end_date)
        m5_df = DataFetcher.fetch_range(symbol, "5m", start=start_date, end=end_date)
        
        if any(df is None or df.empty for df in [h1_df, m15_df, m5_df]):
            print(f"   Missing data for {symbol}. Skipping...")
            continue
            
        h1_df = IndicatorCalculator.add_indicators(h1_df, "h1")
        m15_df = IndicatorCalculator.add_indicators(m15_df, "15m")
        m5_df = IndicatorCalculator.add_indicators(m5_df, "5m")
        
        setups = []
        idx = 100
        while idx < len(m15_df):
            t = m15_df.index[idx]
            latest_m15 = m15_df.iloc[idx]
            
            # 1. H1 Narrative
            state_h1 = h1_df[h1_df.index <= t]
            if state_h1.empty: 
                idx += 1
                continue
            h1_trend = "BULLISH" if state_h1.iloc[-1]['close'] > state_h1.iloc[-1][f'ema_{EMA_TREND}'] else "BEARISH"
            
            # 2. Setup (M15 Sweep)
            state_m15 = m15_df.iloc[:idx+1]
            prev_low = state_m15.iloc[-21:-1]['low'].min()
            prev_high = state_m15.iloc[-21:-1]['high'].max()
            
            direction = None
            sweep_level = None
            description = ""
            if h1_trend == "BULLISH" and latest_m15['low'] < prev_low and latest_m15['close'] > prev_low:
                direction = "BUY"
                sweep_level = prev_low
                description = f"Sweep of M15 Low ({prev_low:.5f})"
            elif h1_trend == "BEARISH" and latest_m15['high'] > prev_high and latest_m15['close'] < prev_high:
                direction = "SELL"
                sweep_level = prev_high
                description = f"Sweep of M15 High ({prev_high:.5f})"
                
            if not direction:
                idx += 1
                continue

            # 3. Scoring
            displaced = DisplacementAnalyzer.is_displaced(state_m15, direction)
            score_details = {'h1_aligned': True, 'sweep_type': 'M15_SWEEP', 'displaced': displaced, 'pullback': True, 'volatile': True}
            score = ScoringEngine.calculate_score(score_details)
            
            if score < MIN_CONFIDENCE_SCORE:
                idx += 1
                continue

            # 4. AI Validation
            ai_result = await ai_analyst.validate_signal({
                'pair': symbol,
                'direction': direction,
                'h1_trend': h1_trend,
                'setup_tf': 'M15',
                'liquidity_event': description,
                'confidence': score
            })
            await asyncio.sleep(13)
            
            if not ai_result.get('valid', True):
                print(f"   [AI REJECTED] {t}: {ai_result.get('institutional_logic')}")
                total_ai_rejected += 1
                idx += 1
                continue

            # 5. Levels & Outcome
            atr = latest_m15['atr']
            levels = EntryLogic.calculate_levels(state_m15, direction, sweep_level, atr)
            
            tp1_hit, tp2_hit, sl_hit = False, False, False
            m5_start_idx = m5_df.index.get_indexer([t], method='nearest')[0]
            for j in range(m5_start_idx + 1, min(m5_start_idx + 288, len(m5_df))):
                future_bar = m5_df.iloc[j]
                if direction == "BUY":
                    if future_bar['low'] <= levels['sl']: sl_hit = True; break
                    if not tp1_hit and future_bar['high'] >= levels['tp1']: tp1_hit = True
                    if future_bar['high'] >= levels['tp2']: tp2_hit = True; break
                else:
                    if future_bar['high'] >= levels['sl']: sl_hit = True; break
                    if not tp1_hit and future_bar['low'] <= levels['tp1']: tp1_hit = True
                    if future_bar['low'] <= levels['tp2']: tp2_hit = True; break
            
            if tp1_hit or sl_hit:
                if tp2_hit: result = "TP2_WIN"
                elif tp1_hit: result = "TP1_WIN"
                else: result = "LOSS"
                setups.append(result)
                idx += 24
            else:
                idx += 1

        if setups:
            tp2, tp1, losses = setups.count("TP2_WIN"), setups.count("TP1_WIN"), setups.count("LOSS")
            acc = ((tp1 + tp2) / len(setups)) * 100
            print(f"✔️ {symbol}: {len(setups)} setups | {tp2} TP2 | {tp1} TP1 | {losses}L | WinRate: {acc:.1f}%")
            total_tp2_wins += tp2; total_tp1_wins += tp1; total_losses += losses

    print("\n" + "═"*40)
    print(f"🏁 AI PERFORMANCE SUMMARY")
    denominator = total_tp1_wins + total_tp2_wins + total_losses
    total_acc = ((total_tp1_wins + total_tp2_wins) / denominator) * 100 if denominator > 0 else 0
    print(f"AI Filtered: {total_ai_rejected} setups")
    print(f"Final Signals: {denominator}")
    print(f"TP2 Wins: {total_tp2_wins} | TP1 Wins: {total_tp1_wins} | Losses: {total_losses}")
    print(f"Final Win Rate: {total_acc:.1f}%")
    print("═"*40)

if __name__ == "__main__":
    from dotenv import load_dotenv
    import os
    load_dotenv()
    start = (datetime.now() - timedelta(days=32)).strftime("%Y-%m-%d")
    end = datetime.now().strftime("%Y-%m-%d")
    asyncio.run(run_ai_backtest(start, end))
