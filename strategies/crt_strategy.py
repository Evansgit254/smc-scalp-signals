from .base_strategy import BaseStrategy
from typing import Optional, Dict
import pandas as pd
from core.filters.risk_manager import RiskManager
from core.filters.macro_filter import MacroFilter
from core.filters.news_filter import NewsFilter
from indicators.calculations import IndicatorCalculator
from config.config import ATR_MULTIPLIER, MIN_QUALITY_SCORE


class CRTStrategy(BaseStrategy):
    """
    Candle Range Theory (CRT) Strategy — V1.0
    ==========================================
    Logic:
      1. Identify a "Reference Candle" on H1 — a candle that sweeps a prior high/low
         (i.e., its wick exceeds the previous candle's high/low but its body closes INSIDE).
      2. Wait for the NEXT candle to BREAK OUT of the Reference Candle's full range.
      3. On the CLOSE of that breakout candle, enter in the direction of the break.
      4. Stop Loss: Beyond the Reference Candle's opposite wick extreme.
      5. Take Profit: 2R (TP1) and 3R (TP2) from entry.

    Timeframe: H1 (identifies swing-precision setups with intraday timing)
    Trade Type: CRT
    Expected Hold: 4–24 hours
    """

    def get_id(self) -> str:
        return "crt_h1"

    def get_name(self) -> str:
        return "Candle Range Theory (H1)"

    async def analyze(
        self,
        symbol: str,
        data: Dict[str, pd.DataFrame],
        news_events: list,
        market_context: dict,
    ) -> Optional[dict]:
        try:
            df_h1 = data.get("h1")
            df_m5 = data.get("m5")
            
            if df_h1 is None or len(df_h1) < 20 or df_m5 is None or len(df_m5) < 50:
                return None

            # ─── 1. Identify Reference Candle (index -2 on H1) ─────────────────
            ref_h1  = df_h1.iloc[-2]   # Reference candle (previous, confirmed close)
            prev_h1 = df_h1.iloc[-3]   # The candle before the reference candle
            curr_h1 = df_h1.iloc[-1]   # Current H1 candle (currently developing)

            timestamp = curr_h1.name if hasattr(curr_h1, 'name') else None
            
            ref_high  = ref_h1["high"]
            ref_low   = ref_h1["low"]
            ref_body_high = max(ref_h1["open"], ref_h1["close"])
            ref_body_low  = min(ref_h1["open"], ref_h1["close"])

            prev_high = prev_h1["high"]
            prev_low  = prev_h1["low"]

            # ─── 2. H1 Sweep Condition (ICT PO3 Manipulation) ──────────────────
            # Bullish CRT: Sweeps the previous wick low but body closes inside.
            bullish_sweep = (ref_low < prev_low) and (ref_body_low >= prev_low)
            # Bearish CRT: Sweeps the previous wick high but body closes inside.
            bearish_sweep = (ref_high > prev_high) and (ref_body_high <= prev_high)

            if not bullish_sweep and not bearish_sweep:
                return None

            # ─── 3. M5 Confirmation (Market Structure Shift) ───────────────────
            # Get only M5 candles that belong to the current H1 formation
            # We want to see if the developing H1 candle has shown a strong reversal on M5
            
            # The current H1 candle started 0-55 mins ago.
            # We look at the last 12 M5 candles (representing the last 60 minutes)
            m5_recent = df_m5.tail(12)
            
            direction = None
            entry_price = None
            mss_confirmed = False

            curr_m5 = df_m5.iloc[-1]
            m5_close = curr_m5['close']

            if bullish_sweep:
                # Need an M5 MSS: Price must break above a recent M5 swing high with strong closing momentum
                recent_high = m5_recent['high'].max()
                # A strong M5 bullish close near its high
                candle_range = curr_m5['high'] - curr_m5['low']
                strong_close = candle_range > 0 and (curr_m5['high'] - m5_close) / candle_range < 0.3
                
                # Simple MSS Proxy: The current M5 candle is strong bullish and breaking recent structure
                if strong_close and m5_close > m5_recent['open'].mean():
                    direction = "BUY"
                    entry_price = m5_close
                    mss_confirmed = True
                    
            elif bearish_sweep:
                # Need an M5 MSS: Price must break below a recent M5 swing low with strong closing momentum
                recent_low = m5_recent['low'].min()
                # A strong M5 bearish close near its low
                candle_range = curr_m5['high'] - curr_m5['low']
                strong_close = candle_range > 0 and (m5_close - curr_m5['low']) / candle_range < 0.3
                
                # Simple MSS Proxy: The current M5 candle is strong bearish and breaking recent structure
                if strong_close and m5_close < m5_recent['open'].mean():
                    direction = "SELL"
                    entry_price = m5_close
                    mss_confirmed = True

            if not mss_confirmed or not direction or not entry_price:
                return None

            # ─── 4. Trend Alignment (Don't trade counter-trend CRT sweeps) ─────
            ema_fast = curr_h1.get("ema_fast")
            ema_slow = curr_h1.get("ema_slow")
            ema_trend = curr_h1.get("ema_trend")
            
            if ema_fast and ema_slow and ema_trend:
                # Medium trend requirement (relaxed slightly since M5 confirms)
                if direction == "BUY" and not (ema_fast >= ema_slow >= ema_trend * 0.998):
                    return None
                if direction == "SELL" and not (ema_fast <= ema_slow <= ema_trend * 1.002):
                    return None

            # ─── 5. Session Filter (Active Volume Only) ────────────────────────
            if timestamp and hasattr(timestamp, 'hour'):
                hour = timestamp.hour
                # Avoid the dead Asian session (22:00 - 06:00 UTC) where breakouts fail
                if hour >= 22 or hour < 6:
                    return None

            # ─── 6. ATR & Quality Filtering ────────────────────────────────────
            atr_h1 = curr_h1.get("atr")
            if atr_h1 is None or atr_h1 <= 0:
                return None

            range_size = ref_high - ref_low
            # Tighter range limits to avoid massive stops
            if range_size < atr_h1 * 0.4 or range_size > atr_h1 * 2.5:
                return None

            regime = IndicatorCalculator.get_market_regime(df_h1)

            quality_score = min(10.0, round((range_size / atr_h1) * 5.0, 1))
            if quality_score < MIN_QUALITY_SCORE:
                return None

            # ─── 7. SL / TP Calculation (Tight Risk -> High Reward) ────────────
            # The stop loss is placed beyond the absolute H1 sweep extreme.
            # Entry is the M5 confirmation close.
            if direction == "BUY":
                sl = ref_low - (atr_h1 * 0.1)  # Stop just below the H1 sweep wick
                risk = entry_price - sl
                
                # Prevent microscopic stops if M5 entry was too close to H1 bottom
                if risk < (atr_h1 * 0.2):
                    risk = atr_h1 * 0.2
                    sl = entry_price - risk
                    
                tp1 = entry_price + risk * 2.0
                tp2 = entry_price + risk * 4.0
            else:
                sl = ref_high + (atr_h1 * 0.1) # Stop just above the H1 sweep wick
                risk = sl - entry_price
                
                if risk < (atr_h1 * 0.2):
                    risk = atr_h1 * 0.2
                    sl = entry_price + risk
                    
                tp1 = entry_price - risk * 2.0
                tp2 = entry_price - risk * 4.0

            if risk <= 0:
                return None

            # ─── 8. Macro & News Filters ───────────────────────────────────────
            macro_bias = MacroFilter.get_macro_bias(market_context)
            if not MacroFilter.is_macro_safe(symbol, direction, macro_bias):
                return None

            if news_events and not NewsFilter.is_safe_to_trade(news_events, symbol):
                return None

            risk_details = RiskManager.calculate_lot_size(symbol, entry_price, sl)

            return {
                "strategy_id":   self.get_id(),
                "strategy_name": self.get_name(),
                "symbol":        symbol,
                "direction":     direction,
                "timeframe":     "H1",
                "trade_type":    "CRT",
                "entry_price":   round(entry_price, 5),
                "sl":            round(sl, 5),
                "tp0":           round(tp1, 5),   # TP1 mapped to tp0 (first target)
                "tp1":           round(tp2, 5),   # TP2 mapped to tp1 (runner)
                "tp2":           round(entry_price + (risk * 6.0), 5),  # tp2 = 6R stretch
                "confidence":    round(quality_score / 10, 3) if isinstance(quality_score, (int, float)) else 0.5,
                "quality_score": quality_score,
                "regime":        regime,
                "macro_bias":    macro_bias,
                "risk_details":  risk_details,
                "expected_hold": "4-24 hours",
                "score_details": {
                    "ref_high":    round(ref_high, 5),
                    "ref_low":     round(ref_low, 5),
                    "range_size":  round(range_size, 5),
                    "atr":         round(atr_h1, 5),
                    "breakout":    direction,
                    "sweep_type":  "BULLISH_SWEEP" if bullish_sweep else "BEARISH_SWEEP",
                },
            }

        except Exception as e:
            print(f"CRT Error: {e}")
            return None
