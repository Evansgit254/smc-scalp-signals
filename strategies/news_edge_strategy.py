"""
News Edge Strategy (V1.0)
==========================
Enters trades IN THE DIRECTION of statistically-verified post-news biases.

Unlike the Pre-News Rubber Band strategy (which fades pre-event drift), this
strategy fires AFTER the event, riding the documented institutional flow direction
that has been observed in 2024 data across 12–15 samples per event type.

Methodology:
  1. Detect that a High-impact event fired in the last 5–30 minutes.
  2. Look up the (event_type, symbol, window) record in database/news_edge.json.
  3. Only enter if the forensic hit_rate >= MIN_HIT_RATE (default: 0.65).
  4. Confirm entry with a momentum check: the first M5 bar AFTER the event
     must close in the edge direction (avoids entering on the wrong side of
     the initial spike reversal).
  5. Size entry normally; SL = 1.5×ATR, TP = 2.5×ATR (or 2×ATR for 75%+ edges).

Top Edges (from 2024 forensics):
  - USDJPY / NFP   / 15min  → BUY  91.7% hit rate
  - GBPUSD / NFP   / 30min  → BUY  75.0%
  - EURUSD / FOMC  / 30min  → BUY  75.0%
  - GBPUSD / FOMC  / 30min  → BUY  75.0%
  - USDJPY / FOMC  / 5min   → BUY  75.0%
  - Gold   / FOMC  / 30min  → BUY  75.0%
"""

import json
import os
from .base_strategy import BaseStrategy
from typing import Optional, Dict, Tuple
import pandas as pd
from datetime import datetime, timezone, timedelta
from core.filters.risk_manager import RiskManager
from indicators.calculations import IndicatorCalculator
from data.news_fetcher import NewsFetcher

# ── Configuration ──────────────────────────────────────────────────────────────
MIN_HIT_RATE     = 0.65   # Minimum forensic hit rate to qualify for entry
MIN_SAMPLES      = 8      # Ignore edge if backed by fewer than N samples
LOOKBACK_MINUTES = 45     # How many minutes post-event we still consider 'active'
SL_ATR           = 1.0    # Tighter SL — post-news moves are fast and precise
MOMENTUM_CONFIRM = True   # Require post-event candle to close in edge direction

# Whitelist: only fire on forensically-confirmed profitable event/symbol combos.
# Updated after V2 backtest (+6.9R / 50% WR / PF 1.29 over 56 trades).
WHITELIST = {
    ("NFP",  "GBPUSD=X"),   # +3.47R, 58.3% WR
    ("NFP",  "GBPJPY=X"),   # +1.90R, 41.7% WR
    ("NFP",  "USDJPY=X"),   # +2.68R (combined w/ FOMC), 50% WR
    ("FOMC", "USDJPY=X"),   # +0.689R/trade, 50% WR, PF 2.84
    ("FOMC", "GBPJPY=X"),   # Strong forensic score, expanding
    ("CPI",  "EURUSD=X"),   # Borderline (-1.14R), keep for data collection
}

# Event title → canonical key mapping
EVENT_KEY_MAP = {
    "non-farm": "NFP",  "nonfarm": "NFP", "nfp": "NFP",
    "cpi": "CPI",   "consumer price": "CPI", "inflation": "CPI",
    "fomc": "FOMC", "federal reserve": "FOMC", "fed rate": "FOMC",
    "interest rate": "FOMC",
}

# Path to the forensic edge database
DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "database", "news_edge.json"
)


class NewsEdgeStrategy(BaseStrategy):
    """
    Post-event directional strategy: rides statistically-proven institutional
    news flow in the 5–30 min window after high-impact events fire.
    """

    def __init__(self):
        self._edge_db: Optional[dict] = None
        self._db_mtime: Optional[float] = None

    def get_id(self) -> str:
        return "news_edge_v1"

    def get_name(self) -> str:
        return "News Edge (Post-Event Flow)"

    async def analyze(
        self,
        symbol: str,
        data: Dict[str, pd.DataFrame],
        news_events: list,
        market_context: dict,
    ) -> Optional[dict]:
        try:
            df = data.get('m5')
            if df is None or len(df) < 10:
                return None

            # 1. Find a recently-fired high-impact event
            event_info = self._get_recent_event(symbol, news_events)
            if event_info is None:
                return None

            event_key, event_title, minutes_since = event_info

            # 2. Determine which window to use (5min / 15min / 30min)
            window = self._pick_window(minutes_since)

            # 3. Look up the forensic edge
            edge = self._lookup_edge(event_key, symbol, window)
            if edge is None:
                return None

            hit_rate  = edge.get("hit_rate", 0.0)
            direction = edge.get("direction", "")
            n_samples = edge.get("n", 0)

            if hit_rate < MIN_HIT_RATE or n_samples < MIN_SAMPLES or not direction:
                return None

            # 3b. Whitelist filter — only fire on proven profitable combos
            event_whitelist_key = (event_key, symbol)
            if event_whitelist_key not in WHITELIST:
                return None

            # 4. Momentum confirmation — candle after event must close in edge direction
            if MOMENTUM_CONFIRM:
                if not self._momentum_confirms(df, direction):
                    return None

            # 5. ATR-based sizing with forensic avg_win% anchored TP
            latest = df.iloc[-1]
            atr    = latest.get('atr', 0.001)
            if atr == 0:
                return None

            entry    = latest['close']
            sl_dist  = atr * SL_ATR
            # TP anchored to the forensic avg_win % for realistic targets
            avg_win  = edge.get('avg_win', 0.0)
            tp_dist_pct = avg_win / 100.0
            if tp_dist_pct <= 0:
                tp_dist = sl_dist * 1.5  # fallback
            else:
                tp_dist = entry * tp_dist_pct

            if direction == "BUY":
                sl  = entry - sl_dist
                tp0 = entry + tp_dist * 0.6
                tp1 = entry + tp_dist
                tp2 = entry + tp_dist * 1.4
            else:
                sl  = entry + sl_dist
                tp0 = entry - tp_dist * 0.6
                tp1 = entry - tp_dist
                tp2 = entry - tp_dist * 1.4

            risk_details = RiskManager.calculate_lot_size(symbol, entry, sl)

            quality_score = round(5.0 + (hit_rate - 0.5) * 10, 2)  # 6.5–10.0

            return {
                'strategy_id':    self.get_id(),
                'strategy_name':  self.get_name(),
                'symbol':         symbol,
                'direction':      direction,
                'timeframe':      'M5',
                'trade_type':     'NEWS_EDGE',
                'entry_price':    entry,
                'sl':             sl,
                'tp0':            tp0,
                'tp1':            tp1,
                'tp2':            tp2,
                'confidence':     round(hit_rate, 3),
                'quality_score':  quality_score,
                'risk_details':   risk_details,
                'expected_hold':  f"{window} post-event",
                'score_details':  {
                    'event':         event_key,
                    'event_title':   event_title,
                    'window':        window,
                    'hit_rate':      hit_rate,
                    'n_samples':     n_samples,
                    'minutes_since': minutes_since,
                    'avg_pct':       edge.get('avg_pct', 0),
                }
            }

        except Exception:
            return None

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _get_recent_event(
        self, symbol: str, news_events: list
    ) -> Optional[Tuple[str, str, int]]:
        """
        Checks if a High-impact event fired in the last LOOKBACK_MINUTES.
        Returns (event_key, event_title, minutes_since) or None.
        """
        if not news_events:
            return None

        relevant_currencies = NewsFetcher._get_relevant_currencies(symbol)
        if not relevant_currencies:
            return None

        now_utc = datetime.now(timezone.utc)
        best: Optional[Tuple[str, str, int]] = None

        for event in news_events:
            impact = event.get('impact', '').lower()
            if impact not in ('high', 'red'):
                continue

            currency = event.get('country', '').upper()
            if currency not in relevant_currencies:
                continue

            event_time = NewsFetcher._parse_ff_time(event, now_utc)
            if event_time is None:
                continue

            event_utc    = event_time.astimezone(timezone.utc)
            delta_minutes = (now_utc - event_utc).total_seconds() / 60

            # Event must have already fired and be within lookback window
            if 2 <= delta_minutes <= LOOKBACK_MINUTES:
                title     = event.get('title', '')
                event_key = self._classify_event(title)
                if event_key:
                    minutes_since = int(delta_minutes)
                    # Prefer the most recently fired event
                    if best is None or minutes_since < best[2]:
                        best = (event_key, title, minutes_since)

        return best

    def _classify_event(self, title: str) -> Optional[str]:
        """Maps ForexFactory event title to NFP/CPI/FOMC."""
        title_lower = title.lower()
        for keyword, key in EVENT_KEY_MAP.items():
            if keyword in title_lower:
                return key
        return None

    def _pick_window(self, minutes_since: int) -> str:
        """Selects the forensic window that best matches how much time has passed."""
        if minutes_since <= 8:
            return "5min"
        elif minutes_since <= 20:
            return "15min"
        else:
            return "30min"

    def _lookup_edge(
        self, event_key: str, symbol: str, window: str
    ) -> Optional[dict]:
        """Loads the edge database (with lazy caching) and returns the edge record."""
        db = self._load_db()
        if not db:
            return None

        event_data  = db.get(event_key, {})
        symbol_data = event_data.get(symbol, {})
        return symbol_data.get(window)

    def _load_db(self) -> dict:
        """Loads news_edge.json, caching until the file changes on disk."""
        try:
            mtime = os.path.getmtime(DB_PATH)
            if self._edge_db is None or mtime != self._db_mtime:
                with open(DB_PATH) as f:
                    self._edge_db = json.load(f)
                self._db_mtime = mtime
            return self._edge_db
        except Exception:
            return {}

    def _momentum_confirms(self, df: pd.DataFrame, direction: str) -> bool:
        """
        Checks that the most recent M5 candle closed in the edge direction.
        This filters out entries where we'd be bucking the initial post-event move.
        """
        if len(df) < 2:
            return True  # no data to contradict, allow

        latest = df.iloc[-1]
        prev   = df.iloc[-2]

        if direction == "BUY":
            return float(latest['close']) > float(prev['close'])
        else:
            return float(latest['close']) < float(prev['close'])
