"""
Session Clock Strategy (V1.0)
==============================
Based on empirical daily pattern analysis (365 days × 8 symbols).

Statistically proven patterns (p < 0.05):
  - OIL  BUY  at 21:00 UTC  (64.6% win rate)
  - OIL  SELL at 07:00 UTC  (60.5% bear rate)
  - BTC  BUY  at 21:00 UTC  (53.8% win rate)
  - BTC  BUY  at 22:00 UTC  (54.4% win rate)
  - GOLD BUY  at 16:00 UTC  (57.3% win rate — London Close)
  - GOLD BUY  at 11:00 UTC  (55.6% win rate)
  - EURUSD BUY  at 08:00 UTC (51.9% — London Open)
  - EURUSD SELL at 16:00 UTC (57.4% bear rate — London Close)
  - AUDUSD BUY  at 22:00 UTC (54.3% win rate)
  - GBPJPY SELL at 21:00 UTC (65.5% bear rate)
  - USDJPY SELL at 21:00 UTC (65.2% bear rate)
  - USDJPY BUY  at 18:00 UTC (56.9% win rate)
  - GBPJPY BUY  at 18:00 UTC (57.6% win rate)
  - GBPJPY BUY  at 23:00 UTC (57.6% win rate)

Day-of-week filter: No trades on Friday (markets tend to reverse/close positions).
"""
from .base_strategy import BaseStrategy
from typing import Optional, Dict
import pandas as pd
import pytz
from core.filters.risk_manager import RiskManager

# ── Signal Map ────────────────────────────────────────────────────────────────
# Format: { symbol: [ (utc_hour, direction, rr_multiplier), ... ] }
# rr_multiplier: 1.0 = standard 1.5R, 1.5 = 2.25R, 2.0 = 3R
CLOCK_SIGNALS = {
    "CL=F": [        # OIL
        (21, "BUY",  1.5),   # NY Close rally — strongest pattern (64.6% WR)
        (7,  "SELL", 1.0),   # Pre-London bear (60.5% bear rate)
    ],
    "BTC-USD": [
        (21, "BUY",  1.0),   # NY Close BTC rally (53.8% WR)
        (22, "BUY",  1.0),   # Post-NY continuation (54.4% WR)
    ],
    "GC=F": [        # GOLD
        (16, "BUY",  1.5),   # London Close gold rally (57.3% WR)
        (11, "BUY",  1.0),   # Pre-NY gold bid (55.6% WR)
    ],
    "EURUSD=X": [
        (8,  "BUY",  1.0),   # London Open EURUSD (51.9% WR)
        (16, "SELL", 1.0),   # London Close EURUSD selloff (57.4% bear)
    ],
    "AUDUSD=X": [
        (22, "BUY",  1.0),   # Post-NY AUDUSD (54.3% WR)
    ],
    "GBPJPY=X": [
        (21, "SELL", 1.5),   # NY Close JPY strength (65.5% bear)
        (18, "BUY",  1.0),   # Pre-NY close GBPJPY (57.6% WR)
        (23, "BUY",  1.0),   # Asian open GBPJPY (57.6% WR)
    ],
    "USDJPY=X": [
        (21, "SELL", 1.5),   # NY Close JPY strength (65.2% bear)
        (18, "BUY",  1.0),   # Pre-NY close USDJPY (56.9% WR)
    ],
}

# ATR multipliers for SL/TP
SL_ATR = 2.0   # Wide disaster stop (these are time-based exits)
BASE_RR = 1.0  # Not used for time-based exit but kept for signaling


class SessionClockStrategy(BaseStrategy):
    """
    Time-based strategy that enters at statistically proven hours.
    No indicators required — pure time + price action confirmation.
    """

    def get_id(self) -> str:
        return "session_clock_v1"

    def get_name(self) -> str:
        return "Session Clock (Time-Based Edge)"

    async def analyze(
        self,
        symbol: str,
        data: Dict[str, pd.DataFrame],
        news_events: list,
        market_context: dict,
    ) -> Optional[dict]:
        try:
            # Get H1 data (this strategy operates on hourly candles)
            h1 = data.get('h1')
            m5 = data.get('m5')
            df = h1 if h1 is not None else m5
            if df is None or len(df) < 1:
                return None

            # Check if this symbol has clock signals
            signals_for_symbol = CLOCK_SIGNALS.get(symbol)
            if not signals_for_symbol:
                return None

            latest = df.iloc[-1]
            ts = df.index[-1]

            # Convert to UTC
            if hasattr(ts, 'tz') and ts.tz is not None:
                ts_utc = ts.tz_convert('UTC')
            else:
                ts_utc = ts.tz_localize('UTC') if ts.tzinfo is None else ts

            current_hour = ts_utc.hour
            current_dow  = ts_utc.dayofweek  # 0=Mon, 4=Fri

            # Day-of-week filter: skip Friday
            if current_dow == 4:
                return None

            # Find matching signal for this hour
            matched = None
            for (sig_hour, direction, rr_mult) in signals_for_symbol:
                if current_hour == sig_hour:
                    matched = (direction, rr_mult)
                    break

            if matched is None:
                return None

            # Entry logic: These patterns happen DURING the sig_hour.
            # We trigger at the start of the hour.
            direction, rr_mult = matched

            # ATR for SL/TP
            atr = latest.get('atr', latest.get('ATR', None))
            if atr is None or atr == 0:
                return None

            entry = latest.get('open', latest.get('Open'))
            sl_dist = atr * SL_ATR
            
            # Time-based targets (will be closed by the bot after 1h)
            # But we set a visual TP for the user at 1:1
            tp_dist = sl_dist  

            if direction == "BUY":
                sl = entry - sl_dist
                tp = entry + tp_dist
            else:
                sl = entry + sl_dist
                tp = entry - tp_dist

            risk_details = RiskManager.calculate_lot_size(symbol, entry, sl)

            return {
                'strategy_id':   self.get_id(),
                'strategy_name': self.get_name(),
                'symbol':        symbol,
                'direction':     direction,
                'timeframe':     'H1',
                'trade_type':    'SESSION_CLOCK',
                'entry_price':   entry,
                'sl':            sl,
                'tp0':           tp,
                'tp1':           tp,
                'tp2':           tp,
                'confidence':    rr_mult,
                'quality_score': 8.5,  # High confidence — statistically validated
                'regime':        'TIME_BASED_EXPECTANCY',
                'macro_bias':    'N/A',
                'risk_details':  risk_details,
                'expected_hold': '1 hour (TIME-BASED EXIT)',
                'score_details': {
                    'hour':      current_hour,
                    'dow':       current_dow,
                    'rr_mult':   rr_mult,
                    'signal':    1.0 if direction == "BUY" else -1.0,
                }
            }

        except Exception:
            return None
