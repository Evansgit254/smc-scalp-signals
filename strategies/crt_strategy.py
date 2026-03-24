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
            df = data.get("h1")
            if df is None or len(df) < 20:
                return None

            # ─── 1. Identify Reference Candle (index -2, confirmed) ────────────
            ref  = df.iloc[-2]   # Reference candle (previous, confirmed close)
            prev = df.iloc[-3]   # The candle before the reference candle
            curr = df.iloc[-1]   # Current candle (breakout candidate)

            ref_high  = ref["high"]
            ref_low   = ref["low"]
            ref_body_high = max(ref["open"], ref["close"])
            ref_body_low  = min(ref["open"], ref["close"])

            prev_high = prev["high"]
            prev_low  = prev["low"]

            # ─── 2. Sweep Condition ────────────────────────────────────────────
            #  A bullish CRT reference candle SWEEPS the previous low with its wick
            #  but closes ABOVE the previous low (body inside prior range).
            #  A bearish CRT reference candle SWEEPS the previous high with its wick
            #  but closes BELOW the previous high (body inside prior range).
            bullish_sweep = (ref_low < prev_low) and (ref_body_low >= prev_low)
            bearish_sweep = (ref_high > prev_high) and (ref_body_high <= prev_high)

            if not bullish_sweep and not bearish_sweep:
                return None

            # ─── 3. Breakout Condition (current candle closes outside ref range) ─
            curr_close = curr["close"]
            curr_low   = curr["low"]
            curr_high  = curr["high"]

            direction = None
            if bullish_sweep and curr_close > ref_high:
                direction = "BUY"   # Price broke above reference high → bullish CRT
            elif bearish_sweep and curr_close < ref_low:
                direction = "SELL"  # Price broke below reference low → bearish CRT

            if not direction:
                return None

            # ─── 4. ATR & Quality Filtering ────────────────────────────────────
            atr = curr.get("atr")
            if atr is None or atr <= 0:
                return None

            range_size = ref_high - ref_low
            # Avoid micro-candles (noise) and overly wide ranges (news spikes)
            if range_size < atr * 0.3 or range_size > atr * 4.0:
                return None

            # Regime check
            regime = IndicatorCalculator.get_market_regime(df)

            # Simple quality score: ratio of range to ATR (larger, cleaner candle = better)
            quality_score = min(10.0, round((range_size / atr) * 5, 1))
            if quality_score < MIN_QUALITY_SCORE:
                return None

            # ─── 5. SL / TP Calculation ────────────────────────────────────────
            entry = curr_close
            if direction == "BUY":
                sl = ref_low - (atr * 0.2)   # Just below the reference candle low
                risk = entry - sl
                tp1 = entry + risk * 2.0
                tp2 = entry + risk * 3.0
            else:
                sl = ref_high + (atr * 0.2)  # Just above the reference candle high
                risk = sl - entry
                tp1 = entry - risk * 2.0
                tp2 = entry - risk * 3.0

            if risk <= 0:
                return None

            # ─── 6. Macro & News Filters ───────────────────────────────────────
            macro_bias = MacroFilter.get_macro_bias(market_context)
            if not MacroFilter.is_macro_safe(symbol, direction, macro_bias):
                return None

            if news_events and not NewsFilter.is_safe_to_trade(news_events, symbol):
                return None

            risk_details = RiskManager.calculate_lot_size(symbol, entry, sl)

            return {
                "strategy_id":   self.get_id(),
                "strategy_name": self.get_name(),
                "symbol":        symbol,
                "direction":     direction,
                "timeframe":     "H1",
                "trade_type":    "CRT",
                "entry_price":   round(entry, 5),
                "sl":            round(sl, 5),
                "tp0":           round(tp1, 5),   # TP1 mapped to tp0 (first target)
                "tp1":           round(tp2, 5),   # TP2 mapped to tp1 (runner)
                "tp2":           round(entry + (risk * 4.0), 5),  # tp2 = 4R stretch
                "confidence":    round(quality_score / 10, 3),
                "quality_score": quality_score,
                "regime":        regime,
                "macro_bias":    macro_bias,
                "risk_details":  risk_details,
                "expected_hold": "4-24 hours",
                "score_details": {
                    "ref_high":    round(ref_high, 5),
                    "ref_low":     round(ref_low, 5),
                    "range_size":  round(range_size, 5),
                    "atr":         round(atr, 5),
                    "breakout":    direction,
                    "sweep_type":  "BULLISH_SWEEP" if bullish_sweep else "BEARISH_SWEEP",
                },
            }

        except Exception:
            return None
