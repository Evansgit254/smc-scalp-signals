import asyncio
import pandas as pd
import joblib
import os
from datetime import datetime, timedelta, time
from config.config import SYMBOLS, EMA_TREND, MIN_CONFIDENCE_SCORE, ATR_MULTIPLIER, ADR_THRESHOLD_PERCENT, ASIAN_RANGE_MIN_PIPS
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator
from strategy.displacement import DisplacementAnalyzer
from strategy.entry import EntryLogic
from strategy.scoring import ScoringEngine
from filters.correlation import CorrelationAnalyzer

# Load ML Model
ML_MODEL = None
if os.path.exists("training/win_prob_model.joblib"):
    ML_MODEL = joblib.load("training/win_prob_model.joblib")

async def run_v6_backtest(days=60):
    print(f"🚀 V6 ANTI-TRAP PORTFOLIO BACKTEST (Last {days} days)")
    print(f"Filters: POC Penalty, Asian Quality Gate, EMA Velocity Filter, Profit Guard (BE at TP1)")
    
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    all_data = {}
    valid_symbols = []
    
    print("Fetching data...")
    for symbol in SYMBOLS:
        h1 = DataFetcher.fetch_range(symbol, "1h", start=start_date, end=end_date)
        m15 = DataFetcher.fetch_range(symbol, "15m", start=start_date, end=end_date)
        m5 = DataFetcher.fetch_range(symbol, "5m", start=start_date, end=end_date)
        
        if all(df is not None and not df.empty for df in [h1, m15, m5]):
            h1 = IndicatorCalculator.add_indicators(h1, "h1")
            m15 = IndicatorCalculator.add_indicators(m15, "15m")
            m5 = IndicatorCalculator.add_indicators(m5, "5m")
            all_data[symbol] = {'h1': h1, 'm15': m15, 'm5': m5}
            valid_symbols.append(symbol)
    
    if not valid_symbols: return

    timeline = all_data[valid_symbols[0]]['m15'].index
    total_wins = 0
    total_losses = 0
    total_breakevens = 0
    heartbreakers_saved = 0
    
    cooldowns = {s: timeline[0] - timedelta(days=1) for s in SYMBOLS}
    
    print(f"Simulating {len(timeline)} bars...")
    
    for t in timeline:
        potential_batch = []
        for symbol in valid_symbols:
            if t < cooldowns[symbol]: continue
            m15_df = all_data[symbol]['m15']
            if t not in m15_df.index: continue
            idx = m15_df.index.get_loc(t)
            if idx < 100: continue
            
            latest_m5 = all_data[symbol]['m5'][all_data[symbol]['m5'].index <= t].iloc[-1]
            latest_m15 = m15_df.iloc[idx]
            state_m15 = m15_df.iloc[:idx+1]
            state_h1 = all_data[symbol]['h1'][all_data[symbol]['h1'].index <= t]
            if state_h1.empty: continue
            
            # V6 Logic
            adr = IndicatorCalculator.calculate_adr(state_h1)
            asian_range = IndicatorCalculator.get_asian_range(state_m15)
            poc = IndicatorCalculator.calculate_poc(all_data[symbol]['m5'][all_data[symbol]['m5'].index <= t])
            ema_slope = IndicatorCalculator.calculate_ema_slope(state_h1, f'ema_{EMA_TREND}')
            
            today_data = state_h1[state_h1.index.date == t.date()]
            current_range = today_data['high'].max() - today_data['low'].min() if not today_data.empty else 0
            adr_exhausted = (adr > 0 and current_range >= (adr * ADR_THRESHOLD_PERCENT))
            
            h1_trend_val = 1 if state_h1.iloc[-1]['close'] > state_h1.iloc[-1][f'ema_{EMA_TREND}'] else -1
            
            # Sweep Logic
            prev_low = state_m15.iloc[-21:-1]['low'].min()
            prev_high = state_m15.iloc[-21:-1]['high'].max()
            
            direction = None
            sweep_level = None
            if h1_trend_val == 1 and latest_m15['low'] < prev_low < latest_m15['close']:
                direction = "BUY"; sweep_level = prev_low
            elif h1_trend_val == -1 and latest_m15['high'] > prev_high > latest_m15['close']:
                direction = "SELL"; sweep_level = prev_high
            
            if not direction: continue
            
            # Quality Checks
            asian_sweep = False
            asian_quality = False
            if asian_range:
                raw_range = asian_range['high'] - asian_range['low']
                pips = raw_range * 100 if "JPY" in symbol else raw_range * 10000
                if pips >= ASIAN_RANGE_MIN_PIPS: asian_quality = True
                if direction == "BUY" and latest_m5['low'] < asian_range['low']: asian_sweep = True
                elif direction == "SELL" and latest_m5['high'] > asian_range['high']: asian_sweep = True

            at_value = abs(latest_m5['close'] - poc) <= (0.5 * latest_m5['atr'])

            score_details = {
                'h1_aligned': True,
                'sweep_type': 'M15_SWEEP',
                'displaced': DisplacementAnalyzer.is_displaced(state_m15, direction),
                'pullback': True,
                'volatile': True,
                'asian_sweep': asian_sweep,
                'asian_quality': asian_quality,
                'adr_exhausted': adr_exhausted,
                'at_value': at_value,
                'ema_slope': ema_slope,
                'symbol': symbol,
                'direction': direction
            }
            confidence = ScoringEngine.calculate_score(score_details)
            if confidence < MIN_CONFIDENCE_SCORE: continue

            potential_batch.append({
                'symbol': symbol, 'pair': symbol.replace('=X','').replace('^',''),
                'direction': direction, 't': t, 'sweep_level': sweep_level,
                'atr': latest_m15['atr']
            })

        if not potential_batch: continue
        filtered = CorrelationAnalyzer.filter_signals(potential_batch)
        
        for sig in filtered:
            symbol = sig['symbol']
            m5_df = all_data[symbol]['m5']
            levels = EntryLogic.calculate_levels(m5_df[m5_df.index <= sig['t']], sig['direction'], sig['sweep_level'], sig['atr'])
            
            m5_start_idx = m5_df.index.get_indexer([sig['t']], method='nearest')[0]
            
            hit = None
            tp1_hit = False
            
            for j in range(m5_start_idx + 1, min(m5_start_idx + 288, len(m5_df))):
                fut = m5_df.iloc[j]
                if sig['direction'] == "BUY":
                    if fut['high'] >= levels['tp1']: tp1_hit = True
                    if tp1_hit and fut['low'] <= levels['entry']: hit = "BE"; break # Profit Guard
                    if fut['low'] <= levels['sl']: hit = "LOSS"; break
                    if fut['high'] >= levels['tp2']: hit = "WIN"; break
                else:
                    if fut['low'] <= levels['tp1']: tp1_hit = True
                    if tp1_hit and fut['high'] >= levels['entry']: hit = "BE"; break # Profit Guard
                    if fut['high'] >= levels['sl']: hit = "LOSS"; break
                    if fut['low'] <= levels['tp2']: hit = "WIN"; break
            
            if hit == "WIN": total_wins += 1
            elif hit == "LOSS": total_losses += 1
            elif hit == "BE": 
                total_breakevens += 1
                heartbreakers_saved += 1
            
            if hit: cooldowns[symbol] = t + timedelta(hours=6)

    print("\n" + "═"*40)
    print(f"🏁 V6 ANTI-TRAP RESULTS")
    print(f"Total Trades: {total_wins + total_losses + total_breakevens}")
    print(f"Wins: {total_wins}")
    print(f"Losses: {total_losses}")
    print(f"Profit Guard (BE): {total_breakevens}")
    print(f"Win Rate (Adjusted): {(total_wins/(total_wins+total_losses)*100) if (total_wins+total_losses)>0 else 0:.1f}%")
    print(f"Raw Win Rate: {(total_wins/(total_wins+total_losses+total_breakevens)*100) if (total_wins+total_losses+total_breakevens)>0 else 0:.1f}%")
    print(f"Heartbreakers Deflected: {heartbreakers_saved}")
    print("═"*40)

if __name__ == "__main__":
    asyncio.run(run_v6_backtest(58))
