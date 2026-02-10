import asyncio
import pandas as pd
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator
from liquidity.sweep_detector import LiquidityDetector
from strategy.entry import EntryLogic

async def validate_outcomes():
    print("🚀 VALIDATING SIGNAL ACCURACY (USDJPY Replay)...")
    fetcher = DataFetcher()
    market_data = fetcher.get_latest_data(symbols=["USDJPY=X"])
    
    if "USDJPY=X" not in market_data:
        print("Error: Could not fetch USDJPY data.")
        return

    data = market_data["USDJPY=X"]
    m1 = IndicatorCalculator.add_indicators(data['m1'], "m1")
    
    # We found sweeps at these approximate times: 21:29, 21:36, 21:59 (UTC) on 2026-01-02
    target_times = [
        "2026-01-02 21:29:00+00:00",
        "2026-01-02 21:36:00+00:00",
        "2026-01-02 21:59:00+00:00"
    ]
    
    for t_str in target_times:
        try:
            t = pd.to_datetime(t_str)
            if t not in m1.index:
                # Find near match
                nearby = m1.index[abs(m1.index - t) < pd.Timedelta(minutes=1)]
                if not nearby.empty:
                    t = nearby[0]
                else:
                    print(f"\n❌ Could not find exact bars for {t_str}")
                    continue

            # Get setup details at that time
            idx = m1.index.get_loc(t)
            setup_bar = m1.iloc[idx]
            atr = setup_bar['atr']
            
            # Logic: Bullish sweep of Low
            sweep_level = m1.iloc[idx-20:idx]['low'].min()
            levels = EntryLogic.calculate_levels(m1.iloc[:idx+1], "BUY", sweep_level, atr)
            
            sl = levels['sl']
            tp1 = levels['tp1']
            tp2 = levels['tp2']
            entry_price = setup_bar['close']

            print(f"\n📡 ANALYZING SIGNAL at {t}")
            print(f"   Entry: {entry_price:.5f} | SL: {sl:.5f} | TP1: {tp1:.5f} | TP2: {tp2:.5f}")

            # Track outcome for next 30 bars (30 minutes)
            outcome_found = False
            for forward_idx in range(idx + 1, min(idx + 31, len(m1))):
                test_bar = m1.iloc[forward_idx]
                curr_t = m1.index[forward_idx]
                
                # Check SL first
                if test_bar['low'] <= sl:
                    print(f"   🔴 RESULT: STOP LOSS HIT at {curr_t} (Loss)")
                    outcome_found = True
                    break
                
                # Check TP2
                if test_bar['high'] >= tp2:
                    print(f"   🟢 RESULT: TP2 HIT at {curr_t} (Big Win!)")
                    outcome_found = True
                    break

                # Check TP1
                if test_bar['high'] >= tp1:
                    print(f"   🟡 RESULT: TP1 HIT at {curr_t} (Partial Win)")
                    # We don't break here, we wait to see if it hits TP2 or SL
            
            if not outcome_found:
                final_price = m1.iloc[min(idx + 30, len(m1)-1)]['close']
                pnl = final_price - entry_price
                result_str = "PROFIT" if pnl > 0 else "LOSS"
                print(f"   🔵 RESULT: TIME EXPIRED. Final PnL: {pnl:.5f} ({result_str})")

        except Exception as e:
            print(f"Error validating {t_str}: {e}")

if __name__ == "__main__":
    asyncio.run(validate_outcomes())
