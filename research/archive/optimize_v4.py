import asyncio
import pandas as pd
import joblib
import os
from datetime import datetime, timedelta
from config import config
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator
from strategy.displacement import DisplacementAnalyzer
from strategy.entry import EntryLogic
from strategy.scoring import ScoringEngine
from filters.correlation import CorrelationAnalyzer

async def optimize_v4():
    print("🧪 V4 HYPER-PARAMETER OPTIMIZER")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    all_data = {}
    for symbol in config.SYMBOLS:
        h1 = DataFetcher.fetch_range(symbol, "1h", start=start_date, end=end_date)
        m15 = DataFetcher.fetch_range(symbol, "15m", start=start_date, end=end_date)
        m5 = DataFetcher.fetch_range(symbol, "5m", start=start_date, end=end_date)
        if all(df is not None and not df.empty for df in [h1, m15, m5]):
            all_data[symbol] = {
                'h1': IndicatorCalculator.add_indicators(h1, "h1"),
                'm15': IndicatorCalculator.add_indicators(m15, "15m"),
                'm5': IndicatorCalculator.add_indicators(m5, "5m")
            }

    results = []
    
    # Grid Search
    adr_thresholds = [0.85, 0.90, 0.95, 1.10] # 1.10 effectively disables it
    asian_bonuses = [1.0, 1.5, 2.0]
    
    timeline = all_data[config.SYMBOLS[0]]['m15'].index
    
    for adr_t in adr_thresholds:
        for asian_b in asian_bonuses:
            print(f"Testing: ADR={adr_t}, AsianBonus={asian_b}...")
            
            wins = 0
            losses = 0
            cooldowns = {s: timeline[0] - timedelta(days=1) for s in config.SYMBOLS}
            
            for t in timeline:
                potential_batch = []
                for symbol, data in all_data.items():
                    if t < cooldowns[symbol]: continue
                    m15_df = data['m15']
                    if t not in m15_df.index: continue
                    idx = m15_df.index.get_loc(t)
                    if idx < 100: continue
                    
                    # Logic extraction... (abbreviated for speed)
                    latest_m15 = m15_df.iloc[idx]
                    state_h1 = data['h1'][data['h1'].index <= t]
                    adr = IndicatorCalculator.calculate_adr(state_h1)
                    today_data = state_h1[state_h1.index.date == t.date()]
                    current_range = today_data['high'].max() - today_data['low'].min() if not today_data.empty else 0
                    adr_exhausted = (adr > 0 and current_range >= (adr * adr_t))
                    
                    h1_trend = 1 if state_h1.iloc[-1]['close'] > state_h1.iloc[-1][f'ema_{config.EMA_TREND}'] else -1
                    prev_low = m15_df.iloc[idx-20:idx]['low'].min()
                    prev_high = m15_df.iloc[idx-20:idx]['high'].max()
                    
                    direction = None
                    sweep_level = None
                    if h1_trend == 1 and latest_m15['low'] < prev_low < latest_m15['close']:
                        direction = "BUY"; sweep_level = prev_low
                    elif h1_trend == -1 and latest_m15['high'] > prev_high > latest_m15['close']:
                        direction = "SELL"; sweep_level = prev_high
                    
                    if not direction: continue
                    
                    asian_range = IndicatorCalculator.get_asian_range(m15_df.iloc[:idx+1])
                    asian_sweep = False
                    if asian_range:
                        latest_m5 = data['m5'][data['m5'].index <= t].iloc[-1]
                        if direction == "BUY" and latest_m5['low'] < asian_range['low']: asian_sweep = True
                        elif direction == "SELL" and latest_m5['high'] > asian_range['high']: asian_sweep = True

                    # Custom score for this test
                    score = 7.5 # Base
                    if asian_sweep: score += asian_b
                    if adr_exhausted: score -= 3.0
                    
                    if score >= 9.0:
                        potential_batch.append({'symbol': symbol, 'pair': symbol.replace('=X',''), 'direction': direction, 't': t, 'sweep_level': sweep_level, 'atr': latest_m15['atr']})

                if not potential_batch: continue
                filtered = CorrelationAnalyzer.filter_signals(potential_batch)
                
                for sig in filtered:
                    m5_df = all_data[sig['symbol']]['m5']
                    levels = EntryLogic.calculate_levels(all_data[sig['symbol']]['m15'].iloc[:all_data[sig['symbol']]['m15'].index.get_loc(sig['t'])+1], sig['direction'], sig['sweep_level'], sig['atr'])
                    m5_start = m5_df.index.get_indexer([sig['t']], method='nearest')[0]
                    
                    hit = None
                    for j in range(m5_start + 1, min(m5_start + 288, len(m5_df))):
                        fut = m5_df.iloc[j]
                        if sig['direction'] == "BUY":
                            if fut['low'] <= levels['sl']: hit = "LOSS"; break
                            if fut['high'] >= levels['tp2']: hit = "WIN"; break
                        else:
                            if fut['high'] >= levels['sl']: hit = "LOSS"; break
                            if fut['low'] <= levels['tp2']: hit = "WIN"; break
                    
                    if hit == "WIN": wins += 1; cooldowns[sig['symbol']] = t + timedelta(hours=6)
                    elif hit == "LOSS": losses += 1; cooldowns[sig['symbol']] = t + timedelta(hours=6)

            wr = (wins/(wins+losses)*100) if (wins+losses)>0 else 0
            results.append({'adr_t': adr_t, 'asian_b': asian_b, 'trades': wins+losses, 'win_rate': wr})
            print(f"   Done: WR={wr:.1f}%, Trades={wins+losses}")

    df_res = pd.DataFrame(results)
    print("\n📊 OPTIMIZATION RESULTS:")
    print(df_res.sort_values(by='win_rate', ascending=False).to_string())

if __name__ == "__main__":
    asyncio.run(optimize_v4())
