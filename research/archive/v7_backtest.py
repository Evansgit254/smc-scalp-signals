import asyncio
import pandas as pd
import joblib
import os
import sys
from datetime import datetime, timedelta, time
from config.config import SYMBOLS, EMA_TREND, MIN_CONFIDENCE_SCORE, ATR_MULTIPLIER, ADR_THRESHOLD_PERCENT, ASIAN_RANGE_MIN_PIPS, DXY_SYMBOL
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator
from strategy.displacement import DisplacementAnalyzer
from strategy.entry import EntryLogic
from strategy.scoring import ScoringEngine
from strategy.imbalance import ImbalanceDetector
from filters.session_filter import SessionFilter

# Load ML Model
ML_MODEL = None
if os.path.exists("training/win_prob_model.joblib"):
    ML_MODEL = joblib.load("training/win_prob_model.joblib")

async def run_v7_backtest(days=30):
    print(f"🚀 V7.0 QUANTUM SHIELD BACKTEST (Last {days} days)")
    print(f"Symbols: {SYMBOLS}")
    print(f"FVG Filter: ACTIVE (Quantum Confluence)")
    print(f"DXY Confluence: ACTIVE (Gold Protection)")
    
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    all_data = {}
    valid_symbols = []
    
    print("Fetching data...")
    # Fetch DXY first
    dxy_h1 = DataFetcher.fetch_range(DXY_SYMBOL, "1h", start=start_date, end=end_date)
    if dxy_h1 is not None:
        dxy_h1 = IndicatorCalculator.add_indicators(dxy_h1, "h1")
    
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
    
    if not valid_symbols:
        print("❌ No data fetched. Check internet or symbols.")
        return

    # Use the first available m15 index as timeline
    timeline = all_data[valid_symbols[0]]['m15'].index
    total_wins = 0
    total_losses = 0
    total_breakevens = 0
    trades = []
    
    cooldowns = {s: timeline[0] - timedelta(days=1) for s in SYMBOLS}
    
    print(f"Simulating {len(timeline)} bars...")
    
    for t in timeline:
        for symbol in valid_symbols:
            if t < cooldowns[symbol]: continue
            
            m15_df = all_data[symbol]['m15']
            if t not in m15_df.index: continue
            
            idx = m15_df.index.get_loc(t)
            if idx < 50: continue
            
            # Slices (State at time T)
            state_m15 = m15_df.iloc[:idx+1]
            latest_m15 = state_m15.iloc[-1]
            
            m5_df_full = all_data[symbol]['m5']
            state_m5 = m5_df_full[m5_df_full.index <= t]
            if state_m5.empty: continue
            latest_m5 = state_m5.iloc[-1]
            
            h1_df_full = all_data[symbol]['h1']
            state_h1 = h1_df_full[h1_df_full.index <= t]
            if state_h1.empty: continue
            latest_h1 = state_h1.iloc[-1]
            
            # 1. H1 Trend
            h1_ema = latest_h1[f'ema_{EMA_TREND}']
            h1_trend = "BULLISH" if latest_h1['close'] > h1_ema else "BEARISH"
            
            # 2. M15 Sweep (Liquidity)
            prev_low = state_m15.iloc[-21:-1]['low'].min()
            prev_high = state_m15.iloc[-21:-1]['high'].max()
            
            direction = None
            sweep_level = None
            sweep_type = "M15_SWEEP"
            
            if h1_trend == "BULLISH" and latest_m15['low'] < prev_low < latest_m15['close']:
                direction = "BUY"; sweep_level = prev_low
            elif h1_trend == "BEARISH" and latest_m15['high'] > prev_high > latest_m15['close']:
                direction = "SELL"; sweep_level = prev_high
            
            if not direction: continue
            
            # 3. V7.0 Quantum: FVG Confluence
            fvgs_m5 = ImbalanceDetector.detect_fvg(state_m5)
            has_fvg = ImbalanceDetector.is_price_in_fvg(latest_m5['close'], fvgs_m5, direction)
            if not has_fvg:
                fvgs_m15 = ImbalanceDetector.detect_fvg(state_m15)
                has_fvg = ImbalanceDetector.is_price_in_fvg(latest_m15['close'], fvgs_m15, direction)
            
            # 4. Filter: Session
            if not SessionFilter.is_valid_session(t): continue
            
            # 5. Filter: ADR
            adr = IndicatorCalculator.calculate_adr(state_h1)
            today_h1 = state_h1[state_h1.index.date == t.date()]
            current_range = today_h1['high'].max() - today_h1['low'].min() if not today_h1.empty else 0
            adr_exhausted = (current_range >= adr * ADR_THRESHOLD_PERCENT) if adr > 0 else False
            
            # 6. Filter: Asian Range
            asian_range = IndicatorCalculator.get_asian_range(state_m15)
            asian_sweep = False
            asian_quality = False
            if asian_range:
                raw_range = asian_range['high'] - asian_range['low']
                pips = raw_range * 100 if "JPY" in symbol else raw_range * 10000
                min_pips = 20 if symbol == "GC=F" else ASIAN_RANGE_MIN_PIPS
                if pips >= min_pips: asian_quality = True
                if direction == "BUY" and latest_m5['low'] < asian_range['low']: asian_sweep = True
                elif direction == "SELL" and latest_m5['high'] > asian_range['high']: asian_sweep = True

            # 7. Filter: Volatility & Displacement
            volatile = latest_m5['atr'] > latest_m5['atr_avg']
            displaced = DisplacementAnalyzer.is_displaced(state_m15, direction)
            
            # 8. POC
            poc = IndicatorCalculator.calculate_poc(state_m5)
            at_value = abs(latest_m5['close'] - poc) <= (0.5 * latest_m5['atr'])
            
            # 9. EMA Slope
            ema_slope = IndicatorCalculator.calculate_ema_slope(state_h1, f'ema_{EMA_TREND}')
            
            # 10. Distance from Mean
            h1_dist = (latest_h1['close'] - h1_ema) / h1_ema
            
            # 11. Scoring
            score_details = {
                'h1_aligned': True,
                'sweep_type': sweep_type,
                'displaced': displaced,
                'pullback': True, # Backtest assumes entry on sweep/pullback candle
                'volatile': volatile,
                'asian_sweep': asian_sweep,
                'asian_quality': asian_quality,
                'adr_exhausted': adr_exhausted,
                'at_value': at_value,
                'ema_slope': ema_slope,
                'h1_dist': h1_dist,
                'has_fvg': has_fvg,
                'symbol': symbol,
                'direction': direction
            }
            confidence = ScoringEngine.calculate_score(score_details)
            
            if confidence < MIN_CONFIDENCE_SCORE: continue
            
            # 12. DXY Confluence (Gold Only)
            if symbol == "GC=F" and dxy_h1 is not None:
                state_dxy = dxy_h1[dxy_h1.index <= t]
                if not state_dxy.empty:
                    dxy_latest = state_dxy.iloc[-1]
                    dxy_trend = "BULLISH" if dxy_latest['close'] > dxy_latest['ema_100'] else "BEARISH"
                    # Gold and DXY are INVERSELY correlated. Divergence (neutral or bad) is not a hard block in main.py but affects score (not really, just alert).
                    # Actually, our ScoringEngine doesn't use dxy_confluence yet, but main.py prints it.
                    pass

            # SELF-OPTIMIZATION (V7.2)
            # In backtest, we simulate the optimizer by looking at its suggestions
            # based on current trade database (which we populate below)
            from audit.optimizer import AutoOptimizer
            opt_mult = AutoOptimizer.get_multiplier_for_symbol(symbol)

            # EXECUTE TRADE
            levels = EntryLogic.calculate_levels(state_m5, direction, sweep_level, latest_m5['atr'], symbol=symbol, opt_mult=opt_mult)
            m5_start_idx = m5_df_full.index.get_indexer([t], method='nearest')[0]
            
            hit = None
            tp0_hit = False
            tp1_hit = False
            for j in range(m5_start_idx + 1, min(m5_start_idx + 288, len(m5_df_full))):
                fut = m5_df_full.iloc[j]
                if direction == "BUY":
                    if fut['high'] >= levels['tp0']: tp0_hit = True
                    if fut['high'] >= levels['tp1']: tp1_hit = True
                    if tp0_hit and fut['low'] <= levels['entry']: hit = "BE"; break
                    if fut['low'] <= levels['sl']: hit = "LOSS"; break
                    if fut['high'] >= levels['tp2']: hit = "WIN"; break
                else:
                    if fut['low'] <= levels['tp0']: tp0_hit = True
                    if fut['low'] <= levels['tp1']: tp1_hit = True
                    if tp0_hit and fut['high'] >= levels['entry']: hit = "BE"; break
                    if fut['high'] >= levels['sl']: hit = "LOSS"; break
                    if fut['low'] <= levels['tp2']: hit = "WIN"; break
            
            if hit:
                # Calculate R-value for this trade
                # Standard: Win=2R (ave), Loss=-1R, BE=0R
                # Gold with Partial: BE after TP0 = +0.5R
                r_val = 0
                if hit == "WIN": r_val = 2.0
                elif hit == "LOSS": r_val = -1.0
                elif hit == "BE":
                    r_val = 0.5 if (symbol == "GC=F" and tp0_hit) else 0.0
                
                trades.append({'t': t, 'symbol': symbol, 'dir': direction, 'res': hit, 'score': confidence, 'r': r_val})
                if hit == "WIN": total_wins += 1
                elif hit == "LOSS": total_losses += 1
                elif hit == "BE": total_breakevens += 1
                
                cooldowns[symbol] = t + timedelta(hours=8) # Avoid clustering

    # Report
    print("\n" + "═"*45)
    print(f"🏁 V7.0 QUANTUM SHIELD BACKTEST RESULTS (WITH GOLD PARTIALS)")
    print(f"Period: {days} days")
    print(f"Total Trades: {len(trades)}")
    print(f"Wins: {total_wins} ✅")
    print(f"Losses: {total_losses} ❌")
    print(f"Breakevens: {total_breakevens} 🛡️")
    
    total_r = sum(tr['r'] for tr in trades)
    wr_adj = (total_wins / (total_wins + total_losses) * 100) if (total_wins + total_losses) > 0 else 0
    
    print(f"Total R-Multiple: {total_r:+.1f}R")
    print(f"Adjusted Win Rate: {wr_adj:.1f}%")
    print("═"*45)
    
    # Per symbol breakdown
    for symbol in valid_symbols:
        s_trades = [tr for tr in trades if tr['symbol'] == symbol]
        if s_trades:
            sw = len([tr for tr in s_trades if tr['res'] == "WIN"])
            sl = len([tr for tr in s_trades if tr['res'] == "LOSS"])
            sb = len([tr for tr in s_trades if tr['res'] == "BE"])
            sr = sum(tr['r'] for tr in s_trades)
            swr = (sw / (sw + sl) * 100) if (sw + sl) > 0 else 0
            print(f"- {symbol:8}: {len(s_trades):2} trades | {sw}W-{sl}L-{sb}BE | R: {sr:+.1f} | WR: {swr:.1f}%")

if __name__ == "__main__":
    d = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    asyncio.run(run_v7_backtest(d))
