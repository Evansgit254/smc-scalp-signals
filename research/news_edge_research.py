"""
News Reaction Edge Research Framework (V1.0)
=============================================
Forensic analysis of price reactions to high-impact economic events.

Methodology:
 1. Load known event dates for NFP, CPI, and FOMC (2024-2025)
 2. For each event, fetch M5 price data from yfinance
 3. Measure the price move in the 5m, 15m, and 30m windows AFTER the event
 4. Calculate directional hit rates (BUY vs SELL tendency) per symbol per event type
 5. Store results in database/news_edge.json for live strategy consumption

Output:
  database/news_edge.json — maps (event_type, symbol, window) -> { direction, hit_rate, avg_pct }
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.fetcher import DataFetcher

# ── 1. Known Event Calendar ────────────────────────────────────────────────────
# Format: (date_string "YYYY-MM-DD", event_type, hour_utc, expected_direction_hint)
# expected_direction_hint: None = no prior, "BUY"/"SELL" = common institutional reaction
# Source: BLS, Federal Reserve, ForexFactory historical records (2024-2025)

NFP_DATES = [
    # Non-Farm Payrolls — First Friday of each month, 13:30 UTC
    ("2024-01-05", "NFP", 13), ("2024-02-02", "NFP", 13), ("2024-03-08", "NFP", 13),
    ("2024-04-05", "NFP", 13), ("2024-05-03", "NFP", 13), ("2024-06-07", "NFP", 13),
    ("2024-07-05", "NFP", 13), ("2024-08-02", "NFP", 13), ("2024-09-06", "NFP", 13),
    ("2024-10-04", "NFP", 13), ("2024-11-01", "NFP", 13), ("2024-12-06", "NFP", 13),
    ("2025-01-10", "NFP", 13), ("2025-02-07", "NFP", 13), ("2025-03-07", "NFP", 13),
]

CPI_DATES = [
    # US CPI — Usually 2nd or 3rd Wednesday, 13:30 UTC
    ("2024-01-11", "CPI", 13), ("2024-02-13", "CPI", 13), ("2024-03-12", "CPI", 13),
    ("2024-04-10", "CPI", 13), ("2024-05-15", "CPI", 13), ("2024-06-12", "CPI", 13),
    ("2024-07-11", "CPI", 13), ("2024-08-14", "CPI", 13), ("2024-09-11", "CPI", 13),
    ("2024-10-10", "CPI", 13), ("2024-11-13", "CPI", 13), ("2024-12-11", "CPI", 13),
    ("2025-01-15", "CPI", 13), ("2025-02-12", "CPI", 13), ("2025-03-12", "CPI", 13),
]

FOMC_DATES = [
    # FOMC Rate Decisions — 8 per year, 19:00 UTC (statement release)
    ("2024-01-31", "FOMC", 19), ("2024-03-20", "FOMC", 18), ("2024-05-01", "FOMC", 18),
    ("2024-06-12", "FOMC", 18), ("2024-07-31", "FOMC", 18), ("2024-09-18", "FOMC", 18),
    ("2024-11-07", "FOMC", 19), ("2024-12-18", "FOMC", 19),
    ("2025-01-29", "FOMC", 19), ("2025-03-19", "FOMC", 18),
]

# Symbols to analyze — our full trading universe
SYMBOLS = [
    "EURUSD=X",   # Inverse DXY → high NFP/CPI sensitivity
    "GBPUSD=X",   # Similar to EURUSD but with BoE overlay
    "USDJPY=X",   # Safe-haven flight → high FOMC sensitivity
    "GBPJPY=X",   # Risk-on / risk-off proxy
    "GC=F",       # Gold → inverse yields, high CPI sensitivity
    "BTC-USD",    # Crypto → macro fear/greed gauge
]

# Measurement windows (in 5-minute bars after event)
WINDOWS = {
    "5min":  1,   # 1 bar = 5 minutes
    "15min": 3,   # 3 bars = 15 minutes
    "30min": 6,   # 6 bars = 30 minutes
}

# ── 2. Analysis Engine ─────────────────────────────────────────────────────────

async def fetch_event_price_window(
    symbol: str,
    event_date: str,
    event_hour_utc: int,
    fetcher: DataFetcher,
    bars_before: int = 3,
    bars_after: int = 12
) -> Optional[pd.DataFrame]:
    """
    Fetch M5 price data centred around the event time.
    Returns a dataframe of bars or None if unavailable.
    """
    event_dt = datetime.strptime(event_date, "%Y-%m-%d").replace(
        hour=event_hour_utc, minute=0, tzinfo=timezone.utc
    )
    
    # Fetch the full day's 5m data
    start = (event_dt - timedelta(hours=1)).strftime("%Y-%m-%d")
    end   = (event_dt + timedelta(days=1)).strftime("%Y-%m-%d")
    
    df = fetcher.fetch_range(symbol, "5m", start, end)
    if df is None or df.empty:
        return None
    
    # Slice to the event window
    event_ts = pd.Timestamp(event_dt)
    mask = (df.index >= event_ts - timedelta(minutes=bars_before * 5)) & \
           (df.index <= event_ts + timedelta(minutes=bars_after * 5))
    window = df[mask]
    
    return window if len(window) >= bars_after else None


def measure_reaction(
    df: pd.DataFrame,
    event_hour_utc: int,
    windows: Dict[str, int]
) -> Optional[Dict]:
    """
    Measures price percentage change in each window after the event candle.
    Returns dict like { "5min": +0.23, "15min": -0.11, "30min": +0.42 }
    """
    try:
        # Find the candle at or just after the event time
        event_mask = df.index.hour == event_hour_utc
        event_candles = df[event_mask]
        
        if event_candles.empty:
            return None
        
        event_bar = event_candles.iloc[0]
        event_idx = df.index.get_loc(event_candles.index[0])
        entry_price = event_bar['open']
        
        reactions = {}
        for label, n_bars in windows.items():
            target_idx = event_idx + n_bars
            if target_idx >= len(df):
                reactions[label] = None
                continue
            exit_price = df.iloc[target_idx]['close']
            pct_change = ((exit_price - entry_price) / entry_price) * 100
            reactions[label] = round(pct_change, 4)
        
        return reactions
    except Exception:
        return None


async def run_news_edge_research(all_events: List[Tuple], symbols: List[str]) -> Dict:
    """
    Main research loop. For each (date, event_type, hour) × symbol,
    measure the post-event price reaction and compile statistics.
    """
    fetcher = DataFetcher()
    
    # Structure: results[event_type][symbol][window] = list of pct changes
    results = {}
    
    total = len(all_events) * len(symbols)
    done = 0
    
    for (date_str, event_type, hour_utc) in all_events:
        if event_type not in results:
            results[event_type] = {}
        
        for symbol in symbols:
            if symbol not in results[event_type]:
                results[event_type][symbol] = {w: [] for w in WINDOWS}
            
            done += 1
            print(f"  [{done}/{total}] {event_type} {date_str} → {symbol}")
            
            window_df = await fetch_event_price_window(symbol, date_str, hour_utc, fetcher)
            if window_df is None:
                continue
            
            reactions = measure_reaction(window_df, hour_utc, WINDOWS)
            if reactions is None:
                continue
            
            for w_label, pct in reactions.items():
                if pct is not None:
                    results[event_type][symbol][w_label].append(pct)
    
    return results


def compile_edge_database(raw_results: Dict) -> Dict:
    """
    Converts raw reaction lists into hit rates and direction biases.
    Output: { event_type: { symbol: { window: { direction, hit_rate, avg_pct, n } } } }
    """
    edge_db = {}
    
    for event_type, sym_data in raw_results.items():
        edge_db[event_type] = {}
        
        for symbol, window_data in sym_data.items():
            edge_db[event_type][symbol] = {}
            
            for window_label, reactions in window_data.items():
                if len(reactions) < 3:  # Need minimum data
                    continue
                
                arr = np.array(reactions)
                n_buy  = (arr > 0).sum()
                n_sell = (arr < 0).sum()
                n_total = len(arr)
                
                buy_rate  = n_buy  / n_total
                sell_rate = n_sell / n_total
                
                # Direction: the bias with the stronger hit rate
                if buy_rate >= sell_rate:
                    direction = "BUY"
                    hit_rate  = buy_rate
                else:
                    direction = "SELL"
                    hit_rate  = sell_rate
                
                # Only record if there is a meaningful edge (>= 55% hit rate)
                if hit_rate >= 0.55:
                    edge_db[event_type][symbol][window_label] = {
                        "direction":  direction,
                        "hit_rate":   round(float(hit_rate), 3),
                        "avg_pct":    round(float(arr.mean()), 4),
                        "avg_win":    round(float(arr[arr > 0].mean()), 4) if n_buy else 0,
                        "avg_loss":   round(float(arr[arr < 0].mean()), 4) if n_sell else 0,
                        "n":          int(n_total),
                        "last_updated": datetime.utcnow().strftime("%Y-%m-%d")
                    }
    
    return edge_db


def print_edge_report(edge_db: Dict):
    print("\n" + "=" * 80)
    print("📰 NEWS REACTION EDGE DATABASE — RESULTS")
    print("=" * 80)
    
    for event_type, sym_data in edge_db.items():
        print(f"\n{'─' * 60}")
        print(f"  EVENT: {event_type}")
        print(f"{'─' * 60}")
        print(f"  {'SYMBOL':<15} {'WINDOW':<10} {'DIR':<6} {'HIT%':<8} {'AVG%':<10} {'N'}")
        
        for symbol, window_data in sym_data.items():
            for window_label, stats in window_data.items():
                flag = "🔥" if stats['hit_rate'] >= 0.65 else ("✅" if stats['hit_rate'] >= 0.55 else "")
                print(
                    f"  {symbol:<15} {window_label:<10} {stats['direction']:<6} "
                    f"{stats['hit_rate']*100:.1f}%   {stats['avg_pct']:+.3f}%   "
                    f"{stats['n']}   {flag}"
                )
    
    print("\n" + "=" * 80)


# ── 3. Main Entry Point ────────────────────────────────────────────────────────

async def main():
    print("=" * 70)
    print("📰 NEWS REACTION EDGE RESEARCH FRAMEWORK V1.0")
    print("=" * 70)
    print(f"Events: {len(NFP_DATES)} NFP + {len(CPI_DATES)} CPI + {len(FOMC_DATES)} FOMC")
    print(f"Symbols: {len(SYMBOLS)}")
    print(f"Windows: {list(WINDOWS.keys())}")
    print(f"Total lookups: {(len(NFP_DATES) + len(CPI_DATES) + len(FOMC_DATES)) * len(SYMBOLS)}")
    print("=" * 70)
    
    all_events = NFP_DATES + CPI_DATES + FOMC_DATES
    
    print("\n🔍 Fetching price reactions around each event...\n")
    raw_results = await run_news_edge_research(all_events, SYMBOLS)
    
    print("\n📊 Compiling edge database...")
    edge_db = compile_edge_database(raw_results)
    
    # Save to database/
    os.makedirs("database", exist_ok=True)
    output_path = "database/news_edge.json"
    with open(output_path, "w") as f:
        json.dump(edge_db, f, indent=2)
    
    print(f"✅ Saved to {output_path}")
    print_edge_report(edge_db)


if __name__ == "__main__":
    asyncio.run(main())
