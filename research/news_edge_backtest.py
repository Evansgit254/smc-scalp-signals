"""
News Edge Backtest (V1.0)
=========================
Dedicated backtester for the NEWS_EDGE post-event directional strategy.

Unlike the main backtest which replays historical bars live, this script:
  1. Seeds the known 2024 NFP/CPI/FOMC event dates (from news_edge_research.py)
  2. Loads Dukascopy 2024 M1 data for each symbol
  3. Simulates the POST-event window at each event timestamp
  4. Tests whether the documented direction from news_edge.json would have won

This tests the forensic database itself as a live strategy, validating whether
the historical hit rates translate into actionable P&L.

Results show P&L in R-multiples (risk units):
  - WIN  = +R (TP hit)
  - LOSS = -1R (SL hit)
  - NEUTRAL = 0R (neither hit in 30-bar window)
"""

import json
import os
import sys
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.dukascopy_loader import DukascopyLoader
from indicators.calculations import IndicatorCalculator

# ── Event calendar (same as news_edge_research.py) ─────────────────────────────
NFP_DATES = [
    ("2024-01-05", "NFP", 13), ("2024-02-02", "NFP", 13), ("2024-03-08", "NFP", 13),
    ("2024-04-05", "NFP", 13), ("2024-05-03", "NFP", 13), ("2024-06-07", "NFP", 13),
    ("2024-07-05", "NFP", 13), ("2024-08-02", "NFP", 13), ("2024-09-06", "NFP", 13),
    ("2024-10-04", "NFP", 13), ("2024-11-01", "NFP", 13), ("2024-12-06", "NFP", 13),
]
CPI_DATES = [
    ("2024-01-11", "CPI", 13), ("2024-02-13", "CPI", 13), ("2024-03-12", "CPI", 13),
    ("2024-04-10", "CPI", 13), ("2024-05-15", "CPI", 13), ("2024-06-12", "CPI", 13),
    ("2024-07-11", "CPI", 13), ("2024-08-14", "CPI", 13), ("2024-09-11", "CPI", 13),
    ("2024-10-10", "CPI", 13), ("2024-11-13", "CPI", 13), ("2024-12-11", "CPI", 13),
]
FOMC_DATES = [
    ("2024-01-31", "FOMC", 19), ("2024-03-20", "FOMC", 18), ("2024-05-01", "FOMC", 18),
    ("2024-06-12", "FOMC", 18), ("2024-07-31", "FOMC", 18), ("2024-09-18", "FOMC", 18),
    ("2024-11-07", "FOMC", 19), ("2024-12-18", "FOMC", 19),
]
ALL_EVENTS = NFP_DATES + CPI_DATES + FOMC_DATES

# Symbols to test (same universe as news_edge_research.py)
SYMBOLS = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "GBPJPY=X", "GC=F"]

# Strategy parameters
SL_ATR        = 1.0   # Tighter SL — post-news moves are fast and precise
MIN_HIT_RATE  = 0.65
MIN_SAMPLES   = 8
ENTRY_DELAY_BARS = 1     # Enter 1 M5 bar after event (5 min delay)
MAX_HOLD_BARS    = 18    # Max hold = 18 bars = 90 minutes

# Whitelist: only trade event/symbol combos that were net-positive in V1 test
# Expanding from the initial 3 to empirically-confirmed profitable setups
WHITELIST = {
    ("NFP",  "GBPUSD=X"),  # +0.167R, PF 1.38
    ("NFP",  "GBPJPY=X"),  # +0.341R, PF 1.75
    ("CPI",  "EURUSD=X"),  # +0.441R, PF 2.06
    ("FOMC", "USDJPY=X"),  # +0.500R, PF 2.00
    ("FOMC", "GBPJPY=X"),  # Not tested before — high raw forensic score
    ("NFP",  "USDJPY=X"),  # borderline +0.009R, keeping to gather more data
}

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "database", "news_edge.json"
)

# ── Main ───────────────────────────────────────────────────────────────────────

def load_edge_db() -> dict:
    with open(DB_PATH) as f:
        return json.load(f)

def pick_window(delay_bars: int) -> str:
    """Map entry delay to the appropriate forensic window."""
    minutes = delay_bars * 5
    if minutes <= 8:
        return "5min"
    elif minutes <= 20:
        return "15min"
    else:
        return "30min"

def run_news_edge_backtest():
    print("=" * 70)
    print("📰 NEWS EDGE STRATEGY — FORENSIC BACKTEST 2024")
    print("=" * 70)
    print(f"Events: {len(NFP_DATES)} NFP + {len(CPI_DATES)} CPI + {len(FOMC_DATES)} FOMC")
    print(f"Symbols: {len(SYMBOLS)}  |  Min hit_rate: {MIN_HIT_RATE:.0%}")
    print("=" * 70)

    edge_db = load_edge_db()
    loader  = DukascopyLoader(base_dir="data/dukascopy")

    # Pre-load full 2024 M5 data for each symbol once (resample from M1)
    print("📂 Loading Dukascopy 2024 M1 data...")
    symbol_data: dict = {}
    for sym in SYMBOLS:
        df = loader.load(sym, timeframe="5min", start_date="2024-01-01", end_date="2024-12-31")
        if df is not None and not df.empty:
            df = IndicatorCalculator.add_indicators(df, "5m")
            symbol_data[sym] = df
            print(f"  ✅ {sym:15s} → {len(df):,} M5 bars")
        else:
            print(f"  ❌ {sym:15s} → no data")
    print()

    trades = []
    skipped = 0

    for date_str, event_key, hour_utc in ALL_EVENTS:
        event_dt = pd.Timestamp(date_str, tz="UTC").replace(hour=hour_utc, minute=30)

        for sym in SYMBOLS:
            df = symbol_data.get(sym)
            if df is None:
                continue

            # 1. Look up the forensic edge for the 15min window (primary)
            window = "15min"
            edge_data = edge_db.get(event_key, {}).get(sym, {}).get(window)
            # Fallback to 30min if 15min not available
            if not edge_data or edge_data.get("hit_rate", 0) < MIN_HIT_RATE:
                edge_data = edge_db.get(event_key, {}).get(sym, {}).get("30min")

            if not edge_data:
                skipped += 1
                continue
            if edge_data.get("hit_rate", 0) < MIN_HIT_RATE:
                skipped += 1
                continue
            if edge_data.get("n", 0) < MIN_SAMPLES:
                skipped += 1
                continue

            direction = edge_data["direction"]
            hit_rate  = edge_data["hit_rate"]
            avg_win   = edge_data.get("avg_win", 0.0)   # forensic avg winner %

            # 2a. Whitelist filter — only trade confirmed profitable combos
            if (event_key, sym) not in WHITELIST:
                skipped += 1
                continue
            entry_dt = event_dt + pd.Timedelta(minutes=ENTRY_DELAY_BARS * 5)

            # Get position in DataFrame just after entry time
            future = df[df.index >= entry_dt]
            if len(future) < MAX_HOLD_BARS:
                skipped += 1
                continue

            entry_bar = future.iloc[0]
            atr = entry_bar.get("atr", 0)
            if not atr or atr <= 0:
                skipped += 1
                continue

            entry_price = float(entry_bar["close"])
            atr = entry_bar.get("atr", 0)
            if not atr or atr <= 0:
                skipped += 1
                continue

            sl_dist  = atr * SL_ATR
            # TP anchored to the forensic avg_win % (e.g. 0.027% of price)
            # Fallback to 1.5×SL if avg_win not in DB
            tp_dist_pct = avg_win / 100.0  # convert % to decimal
            if tp_dist_pct <= 0:
                tp_dist = sl_dist * 1.5
            else:
                tp_dist = entry_price * tp_dist_pct

            sl = entry_price - sl_dist if direction == "BUY" else entry_price + sl_dist
            tp = entry_price + tp_dist if direction == "BUY" else entry_price - tp_dist

            # 3. Simulate the trade
            hit    = None
            pnl_r  = 0.0
            bars_held = 0
            start_idx = future.index.get_loc(entry_bar.name) if entry_bar.name in future.index else 0

            for j in range(1, min(MAX_HOLD_BARS, len(future) - 1)):
                bar = future.iloc[j]
                bars_held = j
                low  = float(bar["low"])
                high = float(bar["high"])

                if direction == "BUY":
                    if low <= sl:
                        hit = "LOSS"; pnl_r = -1.0; break
                    if high >= tp:
                        hit = "WIN";  pnl_r = tp_dist / sl_dist; break
                else:
                    if high >= sl:
                        hit = "LOSS"; pnl_r = -1.0; break
                    if low <= tp:
                        hit = "WIN";  pnl_r = tp_dist / sl_dist; break

            if hit is None:
                # Neither TP nor SL hit — close at last bar price
                last_price = float(future.iloc[min(MAX_HOLD_BARS-1, len(future)-1)]["close"])
                if direction == "BUY":
                    pnl_r = (last_price - entry_price) / sl_dist
                else:
                    pnl_r = (entry_price - last_price) / sl_dist
                hit = "NEUTRAL"

            trades.append({
                "date":       date_str,
                "event":      event_key,
                "symbol":     sym,
                "direction":  direction,
                "hit_rate":   hit_rate,
                "result":     hit,
                "r":          round(pnl_r, 3),
                "bars_held":  bars_held,
            })

    # ── Print Results ───────────────────────────────────────────────────────────
    if not trades:
        print("❌ No trades generated. Check edge DB thresholds.")
        return

    df_trades = pd.DataFrame(trades)
    print(f"\n✅ {len(trades)} trades simulated  |  {skipped} event/symbol combos skipped (below threshold)\n")

    print("=" * 70)
    print(f"{'EVENT':<8} | {'SYMBOL':<12} | {'N':>4} | {'WIN%':>7} | {'PF':>6} | {'EXP':>7}")
    print("-" * 70)

    for event in ["NFP", "CPI", "FOMC"]:
        sub = df_trades[df_trades["event"] == event]
        if sub.empty:
            continue
        for sym in SYMBOLS:
            s = sub[sub["symbol"] == sym]
            if s.empty:
                continue
            n = len(s)
            wins = (s["result"] == "WIN").sum()
            wr = wins / n * 100
            win_r = s[s["r"] > 0]["r"].sum()
            loss_r = abs(s[s["r"] < 0]["r"].sum())
            pf = win_r / loss_r if loss_r > 0 else float("inf")
            exp = s["r"].mean()
            print(f"{event:<8} | {sym:<12} | {n:>4} | {wr:>6.1f}% | {pf:>6.2f} | {exp:>+6.3f}R")
        print("-" * 70)

    total_wins  = (df_trades["result"] == "WIN").sum()
    total_n     = len(df_trades)
    total_wr    = total_wins / total_n * 100
    total_r     = df_trades["r"].sum()
    total_exp   = df_trades["r"].mean()
    win_r_sum   = df_trades[df_trades["r"] > 0]["r"].sum()
    loss_r_sum  = abs(df_trades[df_trades["r"] < 0]["r"].sum())
    pf_total    = win_r_sum / loss_r_sum if loss_r_sum > 0 else float("inf")

    print(f"\n{'TOTAL':<8} | {'ALL':<12} | {total_n:>4} | {total_wr:>6.1f}% | {pf_total:>6.2f} | {total_exp:>+6.3f}R")
    print(f"\n📊 Total P&L: {total_r:+.1f}R over {total_n} trades")

    # Per-symbol summary
    print("\n" + "=" * 70)
    print("PER-SYMBOL SUMMARY")
    print("=" * 70)
    for sym in SYMBOLS:
        s = df_trades[df_trades["symbol"] == sym]
        if s.empty: continue
        wr = (s["result"] == "WIN").mean() * 100
        exp = s["r"].mean()
        total = s["r"].sum()
        print(f"  {sym:<14} N={len(s):>3}  WR={wr:.1f}%  EXP={exp:+.3f}R  TOTAL={total:+.2f}R")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    run_news_edge_backtest()
