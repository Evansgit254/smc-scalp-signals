import asyncio
import pandas as pd
import joblib
import os
from datetime import datetime, timedelta, time
from config.config import EMA_TREND, MIN_CONFIDENCE_SCORE, ATR_MULTIPLIER, ADR_THRESHOLD_PERCENT, ASIAN_RANGE_MIN_PIPS
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator
from strategy.displacement import DisplacementAnalyzer
from strategy.entry import EntryLogic
from strategy.scoring import ScoringEngine
from filters.correlation import CorrelationAnalyzer

async def run_gold_stress_test(days=30):
    symbol = "GC=F"
    print(f"🥇 GOLD SPECIALIST V6.2 STRESS TEST ({days} days)")
    print(f"Safety Gates: Mandatory H1 Alignment, 20-pip Asian Range, 0.5 ATR Buffer, POC Penalty")
    
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    print("Fetching Gold data...")
    h1 = DataFetcher.fetch_range(symbol, "1h", start=start_date, end=end_date)
    m15 = DataFetcher.fetch_range(symbol, "15m", start=start_date, end=end_date)
    m5 = DataFetcher.fetch_range(symbol, "5m", start=start_date, end=end_date)
    
    if any(df is None or df.empty for df in [h1, m15, m5]):
        print("Error fetching Gold data.")
        return

    h1 = IndicatorCalculator.add_indicators(h1, "h1")
    m15 = IndicatorCalculator.add_indicators(m15, "15m")
    m5 = IndicatorCalculator.add_indicators(m5, "5m")
    
    timeline = m15.index
    total_wins = 0
    total_losses = 0
    total_breakevens = 0
    cooldown = timeline[0] - timedelta(days=1)
    
    print(f"Simulating Gold execution over {len(timeline)} bars...")
    
    for t in timeline:
        if t < cooldown: continue
        
        idx = m15.index.get_loc(t)
        if idx < 100: continue
        
        latest_m5 = m5[m5.index <= t].iloc[-1]
        state_m15 = m15.iloc[:idx+1]
        state_h1 = h1[h1.index <= t]
        if state_h1.empty: continue
        
        # V6.2 Gold Specialists Logic
        adr = IndicatorCalculator.calculate_adr(state_h1)
        asian_range = IndicatorCalculator.get_asian_range(state_m15)
        poc = IndicatorCalculator.calculate_poc(m5[m5.index <= t])
        ema_slope = IndicatorCalculator.calculate_ema_slope(state_h1, f'ema_{EMA_TREND}')
        
        h1_close = state_h1.iloc[-1]['close']
        h1_ema = state_h1.iloc[-1][f'ema_{EMA_TREND}']
        h1_dist = (h1_close - h1_ema) / h1_ema
        h1_trend_val = 1 if h1_close > h1_ema else -1
        
        prev_low = state_m15.iloc[-21:-1]['low'].min()
        prev_high = state_m15.iloc[-21:-1]['high'].max()
        
        direction = None
        sweep_level = None
        if h1_trend_val == 1 and state_m15.iloc[-1]['low'] < prev_low < state_m15.iloc[-1]['close']:
            direction = "BUY"; sweep_level = prev_low
        elif h1_trend_val == -1 and state_m15.iloc[-1]['high'] > prev_high > state_m15.iloc[-1]['close']:
            direction = "SELL"; sweep_level = prev_high
            
        if not direction: continue
        
        # Gold Specialist Asian Quality (20 pips)
        asian_sweep = False
        asian_quality = False
        if asian_range:
            pips = (asian_range['high'] - asian_range['low']) * 10000 # Scaling for Gold
            if pips >= 20: asian_quality = True # 20 pip gap for Gold
            if direction == "BUY" and latest_m5['low'] < asian_range['low']: asian_sweep = True
            elif direction == "SELL" and latest_m5['high'] > asian_range['high']: asian_sweep = True

        at_value = abs(latest_m5['close'] - poc) <= (0.5 * latest_m5['atr'])
        h1_aligned = (h1_trend_val == 1 and direction == "BUY") or (h1_trend_val == -1 and direction == "SELL")

        score_details = {
            'h1_aligned': h1_aligned, 'sweep_type': 'M15_SWEEP', 'displaced': DisplacementAnalyzer.is_displaced(state_m15, direction),
            'pullback': True, 'volatile': True, 'asian_sweep': asian_sweep, 'asian_quality': asian_quality,
            'adr_exhausted': False, 'at_value': at_value,
            'ema_slope': ema_slope, 'h1_dist': h1_dist, 'symbol': symbol, 'direction': direction
        }
        confidence = ScoringEngine.calculate_score(score_details)
        if confidence < MIN_CONFIDENCE_SCORE: continue

        # Simulate Entry
        levels = EntryLogic.calculate_levels(m5[m5.index <= t], direction, sweep_level, latest_m5['atr'])
        m5_start_idx = m5.index.get_indexer([t], method='nearest')[0]
        
        hit = None
        tp1_hit = False
        for j in range(m5_start_idx + 1, min(m5_start_idx + 288, len(m5))):
            fut = m5.iloc[j]
            if direction == "BUY":
                if fut['high'] >= levels['tp1']: tp1_hit = True
                if tp1_hit and fut['low'] <= levels['entry']: hit = "BE"; break
                if fut['low'] <= levels['sl']: hit = "LOSS"; break
                if fut['high'] >= levels['tp2']: hit = "WIN"; break
            else:
                if fut['low'] <= levels['tp1']: tp1_hit = True
                if tp1_hit and fut['high'] >= levels['entry']: hit = "BE"; break
                if fut['high'] >= levels['sl']: hit = "LOSS"; break
                if fut['low'] <= levels['tp2']: hit = "WIN"; break
        
        if hit == "WIN": total_wins += 1
        elif hit == "LOSS": total_losses += 1
        elif hit == "BE": total_breakevens += 1
        
        if hit: cooldown = t + timedelta(hours=6)

    print("\n" + "═"*40)
    print(f"🏁 GOLD SPECIALIST RESULTS")
    print(f"Total Trades: {total_wins + total_losses + total_breakevens}")
    print(f"Wins: {total_wins}")
    print(f"Losses: {total_losses}")
    print(f"Breakevens: {total_breakevens}")
    print(f"Win Rate (Adjusted): {(total_wins/(total_wins+total_losses)*100) if (total_wins+total_losses)>0 else 0:.1f}%")
    print("═"*40)

if __name__ == "__main__":
    asyncio.run(run_gold_stress_test(30))
