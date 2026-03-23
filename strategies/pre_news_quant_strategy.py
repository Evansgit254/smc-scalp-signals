"""
Pre-News Quant Strategy (V1.0)
==============================
Predicts the most probable price direction BEFORE a high-impact economic event fires.

Logic:
  Instead of blindly blocking news events, this strategy identifies when an asset
  is over-extended (rubber band effect) relative to its short-term mean.

  The "Drift and Fade" model:
    - In the hours leading up to NFP/CPI/FOMC, institutional traders pre-position.
    - This causes the asset to drift strongly in one direction (high Z-Score).
    - When the news hits, the overcrowded side gets flushed — the rubber band snaps.
    - DXY divergence is used as the confirming signal: if the asset is fighting the Dollar,
      the divergence compression creates an explosive price coil.

Entry Logic (30 min before event):
  1. Check Forex Factory calendar for upcoming High-impact events within next 60 minutes.
  2. Calculate M5 Z-Score of the asset (zscore_20).
  3. Check DXY vs asset divergence (are they moving in the same direction or opposite?).
  4. Issue a counter-directional trade against the drift:
     - Z-Score > +2.0  →  SELL  (too stretched up, expect snap-back or bearish shock)
     - Z-Score < -2.0  →  BUY   (too stretched down, expect bounce or bullish shock)
  5. Exit target: 2.0 ATR from entry (medium-distance target for fast news reaction).

Filters:
  - Minimum absolute Z-Score of 2.0 (rubber band must be meaningfully stretched)
  - DXY divergence bonus: adds 1.5 to quality score when Dollar fights the asset
  - Must have an imminent high-impact event (within 30-60 min, from news_events list)
  - Regime filter: Only fire in RANGING or TRENDING, not CHOPPY
"""

from .base_strategy import BaseStrategy
from typing import Optional, Dict
import pandas as pd
from datetime import datetime, timezone, timedelta
from core.filters.risk_manager import RiskManager
from indicators.calculations import IndicatorCalculator
from core.filters.macro_filter import MacroFilter
from data.news_fetcher import NewsFetcher

# ── Configuration ──────────────────────────────────────────────────────────────
ZSCORE_THRESHOLD = 1.8       # Minimum Z-score stretch to consider entry
SL_ATR = 1.5                 # Stop Loss — tight because news moves are fast
TP_ATR = 2.5                 # Target — news moves tend to be sharp
MIN_EVENT_MINUTES = 10       # Don't enter if event is < 10 min away (too late)
MAX_EVENT_MINUTES = 90       # Don't enter if event is > 90 min away (too early)

# Symbols relevant to USD events (NFP, CPI, FOMC)
USD_SENSITIVE = {"EURUSD=X", "GBPUSD=X", "AUDUSD=X", "NZDUSD=X", "GC=F", "CL=F", "BTC-USD"}
JPY_SENSITIVE = {"USDJPY=X", "GBPJPY=X"}


class PreNewsQuantStrategy(BaseStrategy):
    """
    Pre-positions trades before high-impact economic events using Z-score
    rubber band detection and DXY divergence as the confirming signal.
    """

    def get_id(self) -> str:
        return "pre_news_v1"

    def get_name(self) -> str:
        return "Pre-News Quant (Rubber Band)"

    async def analyze(
        self,
        symbol: str,
        data: Dict[str, pd.DataFrame],
        news_events: list,
        market_context: dict,
    ) -> Optional[dict]:
        try:
            # 1. Need M5 data for Z-score and ATR
            df = data.get('m5')
            if df is None or len(df) < 25:
                return None

            # 2. Check for an imminent High-impact event for this symbol
            event_info = self._get_imminent_event(symbol, news_events)
            if event_info is None:
                return None

            event_label, minutes_until = event_info

            # 3. Get Z-score — the rubber band reading
            latest = df.iloc[-1]
            zscore = latest.get('zscore_20')
            if zscore is None or abs(zscore) < ZSCORE_THRESHOLD:
                return None  # Rubber band not stretched enough

            # 4. Determine trade direction — fade the stretch
            direction = "SELL" if zscore > 0 else "BUY"

            # 5. DXY divergence check — bonus quality filter
            quality_score = 6.0
            dxy_df = market_context.get('DXY')
            divergence_bonus = 0.0
            dxy_bias = None

            if dxy_df is not None and len(dxy_df) >= 1:
                dxy_latest = dxy_df.iloc[-1]
                dxy_close = dxy_latest.get('close', 0)
                dxy_ema = dxy_latest.get('ema_20', dxy_close)
                dxy_bias = "BULLISH" if dxy_close > dxy_ema else "BEARISH"

                # For USD-quote assets (EURUSD, Gold, etc.): DXY and asset should move inversely
                # If DXY is BULLISH but asset is also BULLISH (high Z-score) → DIVERGENCE exists
                if symbol in USD_SENSITIVE:
                    if dxy_bias == "BULLISH" and zscore > 0:
                        # DXY rising, asset also rising → asset is being propped up artificially
                        # Divergence = high probability snap-back SELL when news hits
                        divergence_bonus = 1.5
                    elif dxy_bias == "BEARISH" and zscore < 0:
                        # DXY falling, asset also falling → asset is under-reacting
                        # Divergence = high probability bounce BUY when news hits
                        divergence_bonus = 1.5

            quality_score += divergence_bonus

            # 6. Regime filter — don't enter in choppy/unknown markets
            regime = IndicatorCalculator.get_market_regime(df)
            if regime in ["CHOPPY", "UNKNOWN"]:
                return None

            # 7. Quality gate — minimum score required
            if quality_score < 6.5:
                return None

            # 8. Calculate SL / TP
            atr = latest.get('atr', 0.001)
            if atr == 0:
                return None

            entry = latest['close']
            sl_dist = atr * SL_ATR
            tp_dist = atr * TP_ATR

            if direction == "BUY":
                sl = entry - sl_dist
                tp0 = entry + tp_dist * 0.8
                tp1 = entry + tp_dist
                tp2 = entry + tp_dist * 1.5
            else:
                sl = entry + sl_dist
                tp0 = entry - tp_dist * 0.8
                tp1 = entry - tp_dist
                tp2 = entry - tp_dist * 1.5

            risk_details = RiskManager.calculate_lot_size(symbol, entry, sl)

            return {
                'strategy_id':   self.get_id(),
                'strategy_name': self.get_name(),
                'symbol':        symbol,
                'direction':     direction,
                'timeframe':     'M5',
                'trade_type':    'PRE_NEWS',
                'entry_price':   entry,
                'sl':            sl,
                'tp0':           tp0,
                'tp1':           tp1,
                'tp2':           tp2,
                'confidence':    round(abs(zscore), 2),
                'quality_score': quality_score,
                'regime':        regime,
                'macro_bias':    f"DXY:{dxy_bias or 'N/A'}",
                'risk_details':  risk_details,
                'expected_hold': '15-45 minutes',
                'score_details': {
                    'zscore':           round(float(zscore), 3),
                    'zscore_threshold': ZSCORE_THRESHOLD,
                    'event':            event_label,
                    'minutes_until':    minutes_until,
                    'divergence_bonus': divergence_bonus,
                }
            }

        except Exception as e:
            return None

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _get_imminent_event(self, symbol: str, news_events: list) -> Optional[tuple]:
        """
        Checks if there is a High-impact event imminent for this symbol's currency.
        Returns (event_title, minutes_until) or None.
        """
        if not news_events:
            return None

        relevant_currencies = NewsFetcher._get_relevant_currencies(symbol)
        if not relevant_currencies:
            return None

        now_utc = datetime.now(timezone.utc)

        for event in news_events:
            impact = event.get('impact', '').lower()
            if impact not in ('high', 'red'):
                continue

            event_currency = event.get('country', '').upper()
            if event_currency not in relevant_currencies:
                continue

            event_time = NewsFetcher._parse_ff_time(event, now_utc)
            if event_time is None:
                continue

            event_utc = event_time.astimezone(timezone.utc)
            delta_minutes = (event_utc - now_utc).total_seconds() / 60

            if MIN_EVENT_MINUTES <= delta_minutes <= MAX_EVENT_MINUTES:
                return (event.get('title', 'High Impact'), int(delta_minutes))

        return None
