import asyncio
import pandas as pd
import joblib
import os
from datetime import datetime, timedelta
from config.config import SYMBOLS, EMA_TREND, MIN_CONFIDENCE_SCORE, ATR_MULTIPLIER
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

async def run_v3_backtest(days=30):
    print(f"📡 V3 CORRELATION PORTFOLIO BACKTEST (Last {days} days)")
    print(f"Config: EMA_Trend={EMA_TREND}, ATR_Mult={ATR_MULTIPLIER}, Score>={MIN_CONFIDENCE_SCORE}")
    print(f"ML Filter: {'ACTIVE' if ML_MODEL else 'INACTIVE'}")
    
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
            h1 = IndicatorCalculator.add_indicators(h1, "h1")
            m15 = IndicatorCalculator.add_indicators(m15, "15m")
            m5 = IndicatorCalculator.add_indicators(m5, "5m")
            all_data[symbol] = {'h1': h1, 'm15': m15, 'm5': m5}
            valid_symbols.append(symbol)
            print(f"✔️ {symbol} data ready.")
    
    if not valid_symbols:
        print("❌ No valid data found for any symbol.")
        return

    # Use M15 of first valid symbol as timeline
    timeline = all_data[valid_symbols[0]]['m15'].index
    
    total_wins = 0
    total_losses = 0
    total_rejected_correlation = 0
    
    # 2. ITERATE THROUGH TIME
    print(f"Simulating {len(timeline)} bars across {len(valid_symbols)} symbols...")
    
    # Check if timeline is aware
    is_aware = timeline[0].tzinfo is not None if not timeline.empty else False
    default_min = datetime.min.replace(tzinfo=timeline[0].tzinfo) if is_aware else datetime.min
    
    # Track cooling down per symbol to avoid overlapping trades
    cooldowns = {s: default_min for s in SYMBOLS}
    
    for t in timeline:
        potential_batch = []
        
        for symbol in valid_symbols:
            if symbol not in all_data: continue
            if t < cooldowns[symbol]: continue
            
            m15_df = all_data[symbol]['m15']
            if t not in m15_df.index: continue
            
            idx = m15_df.index.get_loc(t)
            if idx < 100: continue
            
            latest_m15 = m15_df.iloc[idx]
            state_m15 = m15_df.iloc[:idx+1]
            
            # H1 Trend
            h1_df = all_data[symbol]['h1']
            state_h1 = h1_df[h1_df.index <= t]
            if state_h1.empty: continue
            h1_trend_val = 1 if state_h1.iloc[-1]['close'] > state_h1.iloc[-1][f'ema_{EMA_TREND}'] else -1
            h1_trend = "BULLISH" if h1_trend_val == 1 else "BEARISH"
            
            # Sweep Logic (Simplified for backtest speed)
            prev_low = state_m15.iloc[-21:-1]['low'].min()
            prev_high = state_m15.iloc[-21:-1]['high'].max()
            
            direction = None
            sweep_level = None
            if h1_trend_val == 1 and latest_m15['low'] < prev_low < latest_m15['close']:
                direction = "BUY"; sweep_level = prev_low
            elif h1_trend_val == -1 and latest_m15['high'] > prev_high > latest_m15['close']:
                direction = "SELL"; sweep_level = prev_high
                
            if not direction: continue
            
            # Scoring
            displaced = DisplacementAnalyzer.is_displaced(state_m15, direction)
            score = ScoringEngine.calculate_score({
                'h1_aligned': True,
                'sweep_type': 'M15_SWEEP',
                'displaced': displaced,
                'pullback': True,
                'volatile': True
            })
            
            if score < MIN_CONFIDENCE_SCORE: continue
            
            # ML Filter (Optional but recommended)
            win_prob = 0.5
            if ML_MODEL:
                body_ratio = abs(latest_m15['close'] - latest_m15['open']) / (latest_m15['high'] - latest_m15['low']) if (latest_m15['high'] - latest_m15['low']) else 0
                features = pd.DataFrame([[latest_m15['rsi'], body_ratio, latest_m15['atr']/latest_m15['close'], 1 if displaced else 0, h1_trend_val]],
                                        columns=['rsi', 'body_ratio', 'atr_norm', 'displaced', 'h1_trend'])
                win_prob = ML_MODEL.predict_proba(features)[0][1]
                if win_prob < 0.40: continue

            potential_batch.append({
                'pair': symbol.replace('=X', ''),
                'direction': direction,
                'win_prob': win_prob,
                'symbol': symbol,
                't': t,
                'sweep_level': sweep_level,
                'atr': latest_m15['atr']
            })

        if not potential_batch: continue
        
        # 3. APPLY CORRELATION FILTER
        filtered_batch = CorrelationAnalyzer.filter_signals(potential_batch)
        total_rejected_correlation += (len(potential_batch) - len(filtered_batch))
        
        # 4. SIMULATE OUTCOMES
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
                cooldowns[symbol] = t + timedelta(hours=6) # 6h cooldown on symbol
            elif hit == "LOSS":
                total_losses += 1
                cooldowns[symbol] = t + timedelta(hours=6)

    print("\n" + "═"*40)
    print(f"🏁 V3 PORTFOLIO RESULTS")
    print(f"Total Trades Taken: {total_wins + total_losses}")
    print(f"Total Wins: {total_wins}")
    print(f"Total Losses: {total_losses}")
    print(f"Correlation Filter Rejections: {total_rejected_correlation}")
    win_rate = (total_wins / (total_wins + total_losses)) * 100 if (total_wins + total_losses) > 0 else 0
    print(f"V3 Portfolio Win Rate: {win_rate:.1f}%")
    print("═"*40)

if __name__ == "__main__":
    asyncio.run(run_v3_backtest(30))
