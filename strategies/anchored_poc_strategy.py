from .base_strategy import BaseStrategy
from typing import Optional, Dict
import pandas as pd
import numpy as np
from core.filters.risk_manager import RiskManager
from indicators.calculations import IndicatorCalculator

class AnchoredPOCStrategy(BaseStrategy):
    """
    Calculates a proxy Volume Point of Control (POC) over the last 120 candles (Weekly).
    If price deviates significantly from the Weekly POC but loses momentum,
    it triggers a mean-reversion trade back to the most traded price block.
    
    FORENSIC AUDIT FIXES:
    - Added time filter: only profitable hours (0, 3, 6, 12, 21, 22) allowed
    - Added regime filter: block trades in TRENDING regime (trend fights reversion)
    - Added momentum exhaustion: RSI must confirm exhaustion (>70 for sells, <30 for buys)
    - Banned toxic symbols: CL=F (7.1% WR), EURUSD=X (12.2%), GC=F (15.8%)
    - Reduced TP to POC halfway point (lower RR, higher WR)
    - Increased cooldown via stricter deviation threshold (4.0 ATR)
    """

    # Symbols with <16% WR in audit — statistically proven losers for mean reversion
    BANNED_SYMBOLS = {"CL=F", "EURUSD=X", "GC=F"}
    # Only trade during hours with positive expectancy in audit
    PROFITABLE_HOURS = {0, 3, 6, 12, 21, 22}

    def get_id(self) -> str:
        return "poc_edge_v1"

    def get_name(self) -> str:
        return "Anchored Volume POC Reversion"

    async def analyze(
        self,
        symbol: str,
        data: Dict[str, pd.DataFrame],
        news_events: list,
        market_context: dict,
    ) -> Optional[dict]:
        try:
            # Forensic ban: skip proven losers
            if symbol in self.BANNED_SYMBOLS:
                return None

            df = data.get('h1')
            if df is None or len(df) < 120:
                return None

            # Time filter: only trade profitable hours
            ts = df.index[-1]
            hour = ts.hour if hasattr(ts, 'hour') else 0
            if hour not in self.PROFITABLE_HOURS:
                return None

            # Regime filter: don't mean-revert in a trending market
            regime = IndicatorCalculator.get_market_regime(df)
            if regime == 'TRENDING':
                return None

            # Last 5 days of hourly candles (~120 bars)
            recent_df = df.tail(120)
            
            # Simple POC Proxy: Bin the closing prices and find the mode
            prices = recent_df['close'].values
            hist, bin_edges = np.histogram(prices, bins=20)
            max_bin_index = hist.argmax()
            poc_price = (bin_edges[max_bin_index] + bin_edges[max_bin_index+1]) / 2.0
            
            latest = recent_df.iloc[-1]
            entry = latest['close']
            atr = latest.get('atr', 0.001)
            rsi = latest.get('rsi', 50.0)
            
            # Deviation distance
            dist_to_poc = entry - poc_price
            
            # FORENSIC FIX: Increased threshold to 4.0 ATR (was 3.0, producing 16.5 signals/day)
            direction = None
            if dist_to_poc > (atr * 4.0) and rsi > 70:
                direction = "SELL"  # Exhausted & overbought, revert to POC
            elif dist_to_poc < -(atr * 4.0) and rsi < 30:
                direction = "BUY"   # Exhausted & oversold, revert to POC
                
            if not direction:
                return None

            # FORENSIC FIX: Target halfway to POC instead of full POC (higher WR)
            sl_dist = atr * 1.5
            sl = entry - sl_dist if direction == "BUY" else entry + sl_dist
            tp_dist = abs(dist_to_poc) * 0.5  # Halfway reversion
            tp = entry + tp_dist if direction == "BUY" else entry - tp_dist
            
            # Require minimum 1:1 RR
            if direction == "BUY" and (tp - entry) < (entry - sl): return None
            if direction == "SELL" and (entry - tp) < (sl - entry): return None
            
            risk_details = RiskManager.calculate_lot_size(symbol, entry, sl)

            return {
                'strategy_id': self.get_id(),
                'strategy_name': self.get_name(),
                'symbol': symbol,
                'direction': direction,
                'timeframe': 'H1',
                'trade_type': 'POC_EDGE',
                'entry_price': entry,
                'sl': sl,
                'tp0': tp,
                'tp1': tp,
                'tp2': tp,
                'confidence': 1.8,
                'quality_score': 7.5,
                'regime': 'MEAN_REVERSION',
                'macro_bias': 'NEUTRAL',
                'risk_details': risk_details,
                'expected_hold': '12-24 hours',
                'score_details': {
                    'poc_price': float(poc_price),
                    'deviation_atr': float(abs(dist_to_poc) / atr)
                }
            }
        except Exception:
            return None
