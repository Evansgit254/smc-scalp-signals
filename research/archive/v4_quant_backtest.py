import asyncio
import pandas as pd
import joblib
import os
from datetime import datetime, timedelta, time
from config.config import SYMBOLS, EMA_TREND, MIN_CONFIDENCE_SCORE, ATR_MULTIPLIER, ADR_THRESHOLD_PERCENT
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

async def run_v4_backtest(days=30):
    print(f"🚀 V4 ULTRA-QUANT PORTFOLIO BACKTEST (Last {days} days)")
    print(f"Config: EMA_Trend={EMA_TREND}, ATR_Mult={ATR_MULTIPLIER}, Score>={MIN_CONFIDENCE_SCORE}")
    print(f"Filters: Asian Sweep Bonus, ADR Exhaustion Penalty, ML Filter")
    
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    all_data = {}
    valid_symbols = []
    
    # 1. PRE-FETCH DATA
    print("Fetching data for all symbols...")
    for symbol in SYMBOLS:
        h1 = DataFetcher.fetch_range(symbol, "1h", start=start_date, end=end_date)
        m15 = DataFetcher.fetch_range(symbol, "15m", start=start_date, end=end_date)
        m5 = DataFetcher.fetch_range(symbol, "5m", start=start_date, end=end_date)
        
        if all(df is not None and not df.empty for df in [h1, m15, m5]):
            # Indicators are already added in fetcher now (as of latest edits)
            # But let's be safe and re-calculate if needed
            h1 = IndicatorCalculator.add_indicators(h1, "h1")
            m15 = IndicatorCalculator.add_indicators(m15, "15m")
            m5 = IndicatorCalculator.add_indicators(m5, "5m")
            all_data[symbol] = {'h1': h1, 'm15': m15, 'm5': m5}
            valid_symbols.append(symbol)
            print(f"✔️ {symbol} data ready.")
    
    if not valid_symbols:
        print("❌ No valid data found for any symbol.")
        return

    timeline = all_data[valid_symbols[0]]['m15'].index
    total_wins = 0
    total_losses = 0
    adr_blocked = 0
    asian_sweep_trades = 0
    asian_sweep_wins = 0
    
    cooldowns = {s: timeline[0] - timedelta(days=1) for s in SYMBOLS}
    
    # 2. ITERATE THROUGH TIME
    print(f"Simulating {len(timeline)} bars across {len(valid_symbols)} symbols...")
    
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
            
            # V4 Calculations
            adr = IndicatorCalculator.calculate_adr(state_h1)
            asian_range = IndicatorCalculator.get_asian_range(state_m15)
            
            today_data = state_h1[state_h1.index.date == t.date()]
            current_range = today_data['high'].max() - today_data['low'].min() if not today_data.empty else 0
            
            adr_exhausted = False
            if adr > 0 and current_range >= (adr * ADR_THRESHOLD_PERCENT):
                adr_exhausted = True
            
            h1_trend_val = 1 if state_h1.iloc[-1]['close'] > state_h1.iloc[-1][f'ema_{EMA_TREND}'] else -1
            h1_trend = "BULLISH" if h1_trend_val == 1 else "BEARISH"
            
            prev_low = state_m15.iloc[-21:-1]['low'].min()
            prev_high = state_m15.iloc[-21:-1]['high'].max()
            
            direction = None
            sweep_level = None
            if h1_trend_val == 1 and latest_m15['low'] < prev_low < latest_m15['close']:
                direction = "BUY"; sweep_level = prev_low
            elif h1_trend_val == -1 and latest_m15['high'] > prev_high > latest_m15['close']:
                direction = "SELL"; sweep_level = prev_high
            
            if not direction: continue
            
            asian_sweep = False
            if asian_range:
                if direction == "BUY" and latest_m5['low'] < asian_range['low']: asian_sweep = True
                elif direction == "SELL" and latest_m5['high'] > asian_range['high']: asian_sweep = True

            # Scoring Engine V4.0
            score_details = {
                'h1_aligned': True,
                'sweep_type': 'M15_SWEEP',
                'displaced': DisplacementAnalyzer.is_displaced(state_m15, direction),
                'pullback': True,
                'volatile': True,
                'asian_sweep': asian_sweep,
                'adr_exhausted': adr_exhausted
            }
            confidence = ScoringEngine.calculate_score(score_details)
            
            if adr_exhausted: adr_blocked += 1
            if confidence < MIN_CONFIDENCE_SCORE: continue
            
            # ML Filter
            win_prob = 0.5
            if ML_MODEL:
                body_ratio = abs(latest_m15['close'] - latest_m15['open']) / (latest_m15['high'] - latest_m15['low']) if (latest_m15['high'] - latest_m15['low']) else 0
                features = pd.DataFrame([[latest_m15['rsi'], body_ratio, latest_m15['atr']/latest_m15['close'], 1 if score_details['displaced'] else 0, h1_trend_val]],
                                        columns=['rsi', 'body_ratio', 'atr_norm', 'displaced', 'h1_trend'])
                win_prob = ML_MODEL.predict_proba(features)[0][1]
                if win_prob < 0.40: continue

            potential_batch.append({
                'pair': symbol.replace('=X', '').replace('^', ''),
                'symbol': symbol,
                'direction': direction,
                't': t,
                'sweep_level': sweep_level,
                'atr': latest_m15['atr'],
                'win_prob': win_prob,
                'asian_sweep': asian_sweep
            })

        if not potential_batch: continue
        
        filtered_batch = CorrelationAnalyzer.filter_signals(potential_batch)
        
        for sig in filtered_batch:
            symbol = sig['symbol']
            m5_df = all_data[symbol]['m5']
            levels = EntryLogic.calculate_levels(m15_df.iloc[:all_data[symbol]['m15'].index.get_loc(sig['t'])+1], sig['direction'], sig['sweep_level'], sig['atr'])
            
            m5_start_idx = m5_df.index.get_indexer([sig['t']], method='nearest')[0]
            
            hit = None
            for j in range(m5_start_idx + 1, min(m5_start_idx + 288, len(m5_df))):
                fut = m5_df.iloc[j]
                if sig['direction'] == "BUY":
                    if fut['low'] <= levels['sl']: hit = "LOSS"; break
                    if fut['high'] >= levels['tp2']: hit = "WIN"; break
                else:
                    if fut['high'] >= levels['sl']: hit = "LOSS"; break
                    if fut['low'] <= levels['tp2']: hit = "WIN"; break
            
            if hit == "WIN":
                total_wins += 1
                if sig['asian_sweep']: asian_sweep_wins += 1
            elif hit == "LOSS":
                total_losses += 1
            
            if hit:
                if sig['asian_sweep']: asian_sweep_trades += 1
                cooldowns[symbol] = t + timedelta(hours=6)

    print("\n" + "═"*40)
    print(f"🏁 V4 ULTRA-QUANT RESULTS")
    print(f"Total Trades Taken: {total_wins + total_losses}")
    print(f"Total Wins: {total_wins}")
    print(f"Total Losses: {total_losses}")
    print(f"Win Rate: {(total_wins/(total_wins+total_losses)*100) if (total_wins+total_losses)>0 else 0:.1f}%")
    print(f"ADR Filter Blocked: {adr_blocked} signals")
    print(f"Asian Sweep Success: {asian_sweep_wins}/{asian_sweep_trades} ({(asian_sweep_wins/asian_sweep_trades*100) if asian_sweep_trades>0 else 0:.1f}%)")
    print("═"*40)

if __name__ == "__main__":
    asyncio.run(run_v4_backtest(30))
