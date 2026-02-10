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

async def run_v6_forensic_audit(days=58):
    print(f"🕵️ V6 FORENSIC LOSS ISOLATION (Last {days} days)")
    
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
            all_data[symbol] = {
                'h1': IndicatorCalculator.add_indicators(h1, "h1"),
                'm15': IndicatorCalculator.add_indicators(m15, "15m"),
                'm5': IndicatorCalculator.add_indicators(m5, "5m")
            }
            valid_symbols.append(symbol)
    
    if not valid_symbols: return

    timeline = all_data[valid_symbols[0]]['m15'].index
    forensic_records = []
    cooldowns = {s: timeline[0] - timedelta(days=1) for s in SYMBOLS}
    
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
            
            # V6 Calculations
            adr = IndicatorCalculator.calculate_adr(state_h1)
            asian_range = IndicatorCalculator.get_asian_range(state_m15)
            poc = IndicatorCalculator.calculate_poc(all_data[symbol]['m5'][all_data[symbol]['m5'].index <= t])
            ema_slope = IndicatorCalculator.calculate_ema_slope(state_h1, f'ema_{EMA_TREND}')
            
            today_data = state_h1[state_h1.index.date == t.date()]
            current_range = today_data['high'].max() - today_data['low'].min() if not today_data.empty else 0
            adr_util = (current_range / adr) if adr > 0 else 0
            
            h1_close = state_h1.iloc[-1]['close']
            h1_ema = state_h1.iloc[-1][f'ema_{EMA_TREND}']
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
                'h1_aligned': True, 'sweep_type': 'M15_SWEEP', 'displaced': DisplacementAnalyzer.is_displaced(state_m15, direction),
                'pullback': True, 'volatile': True, 'asian_sweep': asian_sweep, 'asian_quality': asian_quality,
                'adr_exhausted': adr_util >= ADR_THRESHOLD_PERCENT, 'at_value': at_value,
                'ema_slope': ema_slope, 'symbol': symbol, 'direction': direction
            }
            confidence = ScoringEngine.calculate_score(score_details)
            if confidence < MIN_CONFIDENCE_SCORE: continue

            potential_batch.append({
                'symbol': symbol, 'pair': symbol.replace('=X','').replace('^',''),
                'direction': direction, 't': t, 'sweep_level': sweep_level,
                'atr': latest_m15['atr'], 'confidence': confidence, 'ema_slope': ema_slope, 'h1_dist_ema': (h1_close - h1_ema)/h1_ema
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
            max_favorable = 0
            
            for j in range(m5_start_idx + 1, min(m5_start_idx + 288, len(m5_df))):
                fut = m5_df.iloc[j]
                if sig['direction'] == "BUY":
                    move = (fut['high'] - levels['entry']) / (levels['tp2'] - levels['entry']) if (levels['tp2'] - levels['entry']) else 0
                    max_favorable = max(max_favorable, move)
                    if fut['high'] >= levels['tp1']: tp1_hit = True
                    if tp1_hit and fut['low'] <= levels['entry']: hit = "BE"; break
                    if fut['low'] <= levels['sl']: hit = "LOSS"; break
                    if fut['high'] >= levels['tp2']: hit = "WIN"; break
                else:
                    move = (levels['entry'] - fut['low']) / (levels['entry'] - levels['tp2']) if (levels['entry'] - levels['tp2']) else 0
                    max_favorable = max(max_favorable, move)
                    if fut['low'] <= levels['tp1']: tp1_hit = True
                    if tp1_hit and fut['high'] >= levels['entry']: hit = "BE"; break
                    if fut['high'] >= levels['sl']: hit = "LOSS"; break
                    if fut['low'] <= levels['tp2']: hit = "WIN"; break
            
            forensic_records.append({
                'time': sig['t'], 'symbol': symbol, 'outcome': hit, 'confidence': sig['confidence'],
                'ema_slope': sig['ema_slope'], 'h1_dist': sig['h1_dist_ema'], 'max_fav': round(max_favorable, 3),
                'direction': sig['direction']
            })
            cooldowns[symbol] = t + timedelta(hours=6)

    df = pd.DataFrame(forensic_records)
    df.to_csv("forensic_audit_v6.csv", index=False)
    
    print("\n📊 V6 LOSS ANALYSIS (Outcome == 'LOSS')")
    losses = df[df['outcome'] == 'LOSS']
    if not losses.empty:
        print("\n1. Average H1 EMA Distance on Losses:")
        print(losses['h1_dist'].describe())
        
        print("\n2. Losses by Symbol:")
        print(losses['symbol'].value_counts())
        
        print("\n3. Max Favorable Move on Losses (Before SL):")
        # How many reached 50% of the way to TP1?
        print(f"Reached >50% of TP1: {len(losses[losses['max_fav'] > 0.5])} / {len(losses)}")

if __name__ == "__main__":
    asyncio.run(run_v6_forensic_audit(58))
