import asyncio
import pandas as pd
import joblib
import os
from datetime import datetime, timedelta, time
from config.config import (
    SYMBOLS, EMA_TREND, MIN_CONFIDENCE_SCORE, ATR_MULTIPLIER, 
    ADR_THRESHOLD_PERCENT, ASIAN_RANGE_MIN_PIPS, DXY_SYMBOL, LIQUIDITY_LOOKBACK,
    EMA_FAST, EMA_SLOW
)
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator
from structure.bias import BiasAnalyzer
from liquidity.sweep_detector import LiquidityDetector
from strategy.displacement import DisplacementAnalyzer
from strategy.entry import EntryLogic
from strategy.scoring import ScoringEngine
from filters.volatility_filter import VolatilityFilter
from filters.session_filter import SessionFilter
from filters.correlation import CorrelationAnalyzer
from filters.risk_manager import RiskManager

# Load ML Model
ML_MODEL = None
if os.path.exists("training/win_prob_model.joblib"):
    ML_MODEL = joblib.load("training/win_prob_model.joblib")

async def run_v9_backtest(days=58):
    print(f"🔥 V9.0 LIQUID REAPER PRO BACKTEST (Last {days} days)")
    print(f"Portfolio: {SYMBOLS}")
    print(f"V9 Features: Liquid Layering (40/40/20), Dual Sweep, DXY Confluence, POC Value, EMA Velocity")
    
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    all_data = {}
    valid_symbols = []
    
    print("Fetching data...")
    for symbol in SYMBOLS + [DXY_SYMBOL]:
        h1 = DataFetcher.fetch_range(symbol, "1h", start=start_date, end=end_date)
        m15 = DataFetcher.fetch_range(symbol, "15m", start=start_date, end=end_date)
        m5 = DataFetcher.fetch_range(symbol, "5m", start=start_date, end=end_date)
        
        if all(df is not None and not df.empty for df in [h1, m15, m5]):
            all_data[symbol] = {
                'h1': IndicatorCalculator.add_indicators(h1, "h1"),
                'm15': IndicatorCalculator.add_indicators(m15, "15m"),
                'm5': IndicatorCalculator.add_indicators(m5, "5m")
            }
            if symbol != DXY_SYMBOL:
                valid_symbols.append(symbol)
                # DEBUG: Check if EMAs are populated
                if not all_data[symbol]['h1'][f'ema_{EMA_TREND}'].dropna().empty:
                    print(f"✅ {symbol} H1 EMA_{EMA_TREND} populated.")
                else:
                    print(f"❌ {symbol} H1 EMA_{EMA_TREND} is all NaNs!")
    
    if not valid_symbols:
        print("Error: No valid data fetched.")
        return

    timeline = all_data[valid_symbols[0]]['m15'].index
    summary = {
        'total_signals': 0,
        'signals_per_symbol': {s: 0 for s in valid_symbols},
        'layer_hits': 0,
        'wins': 0,
        'losses': 0,
        'breakevens': 0,
        'profit_factor': 0.0,
        'points_gained': 0.0
    }
    
    cooldowns = {s: timeline[0] - timedelta(days=1) for s in SYMBOLS}
    
    rejections = {s: {'session': 0, 'bias': 0, 'sweep': 0, 'displaced': 0, 'pullback': 0, 'confidence': 0, 'volatile': 0} for s in valid_symbols}
    rejections['global'] = {'session': 0}
    
    print(f"Simulating {len(timeline)} bars...")
    
    for t in timeline:
        potential_batch = []
        for symbol in valid_symbols:
            if t < cooldowns[symbol]: continue
            
            m15_df_full = all_data[symbol]['m15']
            if t not in m15_df_full.index: continue
            
            idx_m15 = m15_df_full.index.get_loc(t)
            if idx_m15 < 100: continue
            
            # Slice data to simulate "now"
            h1_df = all_data[symbol]['h1'][all_data[symbol]['h1'].index <= t]
            m15_df = m15_df_full.iloc[:idx_m15+1]
            m5_df = all_data[symbol]['m5'][all_data[symbol]['m5'].index <= t]
            
            if h1_df.empty or m5_df.empty: continue

            # Mirrored V9.6 Logic: Hybrid Sessions
            is_gold = (symbol == "GC=F")
            if is_gold:
                # Gold: 06:00 to 22:00 UTC (Expanded)
                hour_utc = t.hour
                is_valid = (hour_utc >= 6) and (hour_utc <= 22)
            else:
                is_valid = SessionFilter.is_valid_session(t)

            if not is_valid: 
                rejections['global']['session'] += 1
                continue
            
            # Loosened Bias V9.3 (Gold = H1 Only)
            def get_bias_loose(h1_df, m15_df, is_gold=False):
                if h1_df.empty or m15_df.empty: return "NEUTRAL"
                h1_lat, m15_lat = h1_df.iloc[-1], m15_df.iloc[-1]
                h1_t = "BULLISH" if h1_lat['close'] > h1_lat[f'ema_{EMA_TREND}'] else "BEARISH"
                if is_gold: return h1_t # Gold: H1 only for maximum frequency
                m15_20, m15_50 = m15_lat[f'ema_{EMA_FAST}'], m15_lat[f'ema_{EMA_SLOW}']
                m15_b = "BULLISH" if m15_20 > m15_50 else ("BEARISH" if m15_20 < m15_50 else "NEUTRAL")
                return m15_b if h1_t == m15_b else "NEUTRAL"

            bias = get_bias_loose(h1_df, m15_df, is_gold=is_gold)
            if bias == "NEUTRAL": 
                rejections[symbol]['bias'] += 1
                continue
            
            h1_trend = BiasAnalyzer.get_h1_trend(h1_df)
            
            # Loosened Sweep detector V9.3 (Gold = 10% Wick, 15 Lookback)
            def detect_sweep_loose(df, bias, timeframe, is_gold=False):
                if df.empty or len(df) < 50: return None
                latest = df.iloc[-1]
                
                # Gold: Hyper-Local sweeps (Lookback 15)
                lb = 15 if is_gold else LIQUIDITY_LOOKBACK
                prev = df.iloc[-(lb+1):-1]
                
                lh, ll = prev['high'].max(), prev['low'].min()
                cr = latest['high'] - latest['low']
                if cr == 0: return None
                
                # V9.4 Gold-specific wick loosening (5%)
                wick_thresh = 0.05 if is_gold else 0.35

                if bias == "BEARISH":
                    if latest['high'] > lh and latest['close'] < lh:
                        uw = latest['high'] - max(latest['open'], latest['close'])
                        if uw / cr >= wick_thresh: return {'type': f'{timeframe.upper()}_BEARISH_SWEEP', 'level': lh}
                if bias == "BULLISH":
                    if latest['low'] < ll and latest['close'] > ll:
                        lw = min(latest['open'], latest['close']) - latest['low']
                        if lw / cr >= wick_thresh: return {'type': f'{timeframe.upper()}_BULLISH_SWEEP', 'level': ll}
                return None

            sweep = detect_sweep_loose(m15_df, bias, timeframe="m15", is_gold=is_gold)
            if not sweep:
                sweep = detect_sweep_loose(m5_df, bias, timeframe="m5", is_gold=is_gold)
                if not sweep: 
                    rejections[symbol]['sweep'] += 1
                    continue
            
            direction = "BUY" if bias == "BULLISH" else "SELL"
            
            # V9.5 Gold-specific Displacement Relaxation
            def is_displaced_loose(df, direction, is_gold=False):
                if len(df) < 5: return False
                last = df.iloc[-1]
                body = abs(last['close'] - last['open'])
                ran = last['high'] - last['low']
                if ran == 0: return False
                
                body_thresh = 0.30 if is_gold else 0.60
                atr_thresh = 0.2 if is_gold else 0.5
                
                is_strong = (body / ran) >= body_thresh
                is_expansive = body >= (atr_thresh * last['atr'])
                return is_strong and is_expansive

            displaced = is_displaced_loose(m5_df, direction, is_gold=is_gold)
            if not displaced:
                rejections[symbol]['displaced'] += 1
                continue
                
            entry_signal = EntryLogic.check_pullback(m5_df, direction)
            if not entry_signal:
                rejections[symbol]['pullback'] += 1
                continue
            
            # Session and Volatility
            if not VolatilityFilter.is_volatile(m5_df): 
                rejections[symbol]['volatile'] += 1
                continue
            
            # ADR & Asian Range
            adr = IndicatorCalculator.calculate_adr(h1_df)
            asian_range = IndicatorCalculator.get_asian_range(m15_df)
            
            today = t.date()
            today_data = h1_df[h1_df.index.date == today]
            current_range = today_data['high'].max() - today_data['low'].min() if not today_data.empty else 0
            # V9.1: Allowing 110% of ADR
            adr_exhausted = (adr > 0 and current_range >= (adr * 1.10))
            
            asian_sweep = False
            asian_quality = False
            if asian_range:
                raw_range = asian_range['high'] - asian_range['low']
                pips = raw_range * 100 if "JPY" in symbol else raw_range * 10000
                # V9.2: Lower Asian requirement for Gold (10 pips)
                min_pips = 10 if symbol == "GC=F" else ASIAN_RANGE_MIN_PIPS
                if pips >= min_pips: asian_quality = True
                if direction == "BUY" and m5_df.iloc[-1]['low'] < asian_range['low']: asian_sweep = True
                elif direction == "SELL" and m5_df.iloc[-1]['high'] > asian_range['high']: asian_sweep = True

            # Hyper-Quant POC & EMA
            poc = IndicatorCalculator.calculate_poc(m5_df)
            at_value = abs(m5_df.iloc[-1]['close'] - poc) <= (0.5 * m5_df.iloc[-1]['atr'])
            ema_slope = IndicatorCalculator.calculate_ema_slope(h1_df, f'ema_{EMA_TREND}')
            h1_dist = (h1_df.iloc[-1]['close'] - h1_df.iloc[-1][f'ema_{EMA_TREND}']) / h1_df.iloc[-1][f'ema_{EMA_TREND}']

            score_details = {
                'h1_aligned': h1_trend == direction.replace('BUY', 'BULLISH').replace('SELL', 'BEARISH'),
                'sweep_type': sweep['type'], 'displaced': displaced, 'pullback': entry_signal is not None,
                'session': "Backtest", 'volatile': True, 'asian_sweep': asian_sweep, 'asian_quality': asian_quality,
                'adr_exhausted': adr_exhausted, 'at_value': at_value, 'ema_slope': ema_slope,
                'h1_dist': h1_dist, 'symbol': symbol, 'direction': direction
            }
            confidence = ScoringEngine.calculate_score(score_details)
            # V9.4 Gold Floor 5.0, Others 6.5
            current_floor = 5.0 if symbol == "GC=F" else 6.5
            if confidence < current_floor: 
                rejections[symbol]['confidence'] += 1
                continue

            # DXY Confluence for Gold (V9.2 Hurdle Removed)
            # if "GC=F" in symbol and DXY_SYMBOL in all_data:
            #     dxy_trend = BiasAnalyzer.get_h1_trend(all_data[DXY_SYMBOL]['h1'][all_data[DXY_SYMBOL]['h1'].index <= t])
            #     if (direction == "BUY" and dxy_trend == "BULLISH") or (direction == "SELL" and dxy_trend == "BEARISH"):
            #         # Gold and DXY usually inverse. If they align, reduce confidence slightly
            #         confidence -= 0.5

            if confidence < MIN_CONFIDENCE_SCORE: continue

            potential_batch.append({
                'symbol': symbol, 'pair': symbol.replace('=X','').replace('^',''), 'direction': direction, 't': t, 'sweep_level': sweep['level'], 
                'atr': m5_df.iloc[-1]['atr'], 'confidence': confidence, 'price': m5_df.iloc[-1]['close']
            })

        if not potential_batch: continue
        filtered = CorrelationAnalyzer.filter_signals(potential_batch)
        
        for sig in filtered:
            summary['total_signals'] += 1
            summary['signals_per_symbol'][sig['symbol']] += 1
            symbol = sig['symbol']
            m5_df_full = all_data[symbol]['m5']
            
            # V9.0 Levels & Layers
            levels = EntryLogic.calculate_levels(m5_df_full[m5_df_full.index <= sig['t']], sig['direction'], sig['sweep_level'], sig['atr'])
            layers = RiskManager.calculate_layers(0.01, sig['price'], levels['sl'], sig['direction']) # Mocking 0.01 lot for layer calc
            
            m5_start_idx = m5_df_full.index.get_indexer([sig['t']], method='nearest')[0]
            
            # Simulate Outcome across all layers
            active_layers = [] # [{'lots': lot, 'price': p, 'hit': False, 'status': None}]
            for l in layers:
                active_layers.append({'lots': l['lots'], 'price': l['price'], 'entered': False, 'result': None})
            
            tp1_hit = False
            signal_finished = False
            
            for j in range(m5_start_idx + 1, min(m5_start_idx + 432, len(m5_df_full))): # Up to 36 hours
                bar = m5_df_full.iloc[j]
                
                for layer in active_layers:
                    if not layer['entered']:
                        if sig['direction'] == "BUY" and bar['low'] <= layer['price']: 
                            layer['entered'] = True; summary['layer_hits'] += 1
                        elif sig['direction'] == "SELL" and bar['high'] >= layer['price']: 
                            layer['entered'] = True; summary['layer_hits'] += 1
                    
                    if layer['entered'] and not layer['result']:
                        # Exit Logic: TP2, SL, or BE if TP1 hit
                        if sig['direction'] == "BUY":
                            if bar['high'] >= levels['tp1']: tp1_hit = True
                            if tp1_hit and bar['low'] <= sig['price']: # BE at original entry
                                layer['result'] = "BE"; break
                            if bar['low'] <= levels['sl']: 
                                layer['result'] = "LOSS"; break
                            if bar['high'] >= levels['tp2']: 
                                layer['result'] = "WIN"; break
                        else:
                            if bar['low'] <= levels['tp1']: tp1_hit = True
                            if tp1_hit and bar['high'] >= sig['price']:
                                layer['result'] = "BE"; break
                            if bar['high'] >= levels['sl']: 
                                layer['result'] = "LOSS"; break
                            if bar['low'] <= levels['tp2']: 
                                layer['result'] = "WIN"; break
                
                # Check if all entered layers are finished
                current_results = [l['result'] for l in active_layers if l['entered']]
                if current_results and all(r is not None for r in current_results):
                    signal_finished = True
                    break
            
            # Aggregate Results for the Signal
            results = [l['result'] for l in active_layers if l['entered']]
            if results:
                if "LOSS" in results: summary['losses'] += 1
                elif "WIN" in results: summary['wins'] += 1
                else: summary['breakevens'] += 1
                
                cooldowns[symbol] = t + timedelta(hours=8)

    # FINAL REPORT
    total = summary['wins'] + summary['losses']
    wr = (summary['wins'] / total * 100) if total > 0 else 0
    raw_wr = (summary['wins'] / (total + summary['breakevens']) * 100) if (total + summary['breakevens']) > 0 else 0
    
    report_lines = [
        "\n" + "═"*45,
        f"🏁 V9.6 HYBRID REAPER SUMMARY",
        f"Total Signals: {summary['total_signals']}",
        f"Layers Triggered: {summary['layer_hits']} (Avg {summary['layer_hits']/max(1,summary['total_signals']):.1f} per signal)",
        f"Wins (Portfolio): {summary['wins']}",
        f"Losses (Portfolio): {summary['losses']}",
        f"Breakevens (Protected): {summary['breakevens']}",
        f"Adjusted Win Rate: {wr:.1f}%",
        f"Raw Win Rate (inc. BE): {raw_wr:.1f}%",
        "-" * 20,
        "Signals per Symbol:",
    ]
    for s, count in summary['signals_per_symbol'].items():
        report_lines.append(f"• {s}: {count} trades")
    
    report_lines.append("-" * 20)
    report_lines.append("Rejection Reasons (Gold Only):")
    gold_rejections = rejections.get('GC=F', {})
    for reason, count in gold_rejections.items():
        report_lines.append(f"• {reason.capitalize()}: {count}")
    
    report_lines.append(f"• Global Session Block: {rejections['global']['session']}")
    report_lines.append("═"*45)

    full_report = "\n".join(report_lines)
    print(full_report)
    
    with open("research/v9_backtest_report.txt", "w") as f:
        f.write(full_report)
    print(f"\n✅ Report saved to research/v9_backtest_report.txt")

if __name__ == "__main__":
    asyncio.run(run_v9_backtest(58))
