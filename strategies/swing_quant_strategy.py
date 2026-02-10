from .base_strategy import BaseStrategy
from typing import Optional, Dict
import pandas as pd
from core.alpha_factors import AlphaFactors
from core.alpha_combiner import AlphaCombiner
from core.filters.risk_manager import RiskManager
from core.filters.macro_filter import MacroFilter
from core.filters.news_filter import NewsFilter
from indicators.calculations import IndicatorCalculator
from config.config import ATR_MULTIPLIER, MIN_QUALITY_SCORE

class SwingQuantStrategy(BaseStrategy):
    """
    H1 Swing Position Strategy
    Targets: 5-10R average, 1-7 day holds
    Frequency: ~5-10 signals/day
    """
    def get_id(self) -> str:
        return "swing_quant_h1"

    def get_name(self) -> str:
        return "Swing Quant (H1 Position)"

    async def analyze(self, symbol: str, data: Dict[str, pd.DataFrame], news_events: list, market_context: dict) -> Optional[dict]:
        try:
            df = data.get('h1')
            if df is None or len(df) < 200: 
                return None
            
            # Detect market regime
            regime = IndicatorCalculator.get_market_regime(df)
            
            # Enhanced Swing Alpha Factors with momentum
            factors = {
                'velocity': AlphaFactors.velocity_alpha(df, period=50),
                'zscore': AlphaFactors.mean_reversion_zscore(df, period=200),
                'momentum': AlphaFactors.momentum_alpha(df, short_period=20, long_period=60),
                'volatility': AlphaFactors.volatility_regime_alpha(df, period=100)
            }
            
            # Regime-adaptive combination
            alpha_signal = AlphaCombiner.combine(factors, regime=regime)
            
            # Calculate quality score
            quality_score = AlphaCombiner.calculate_quality_score(factors, alpha_signal)
            
            # Adaptive thresholds - extra permissive for swing (higher timeframe)
            # We want to ensure H1 does generate trades over a month.
            thresholds = {
                "TRENDING": 0.3,   # Very permissive in trends
                "RANGING": 0.4,    # Moderate in ranges
                "CHOPPY": 0.5      # Still selective in choppy
            }
            threshold = thresholds.get(regime, 0.4)
            
            # Looser quality filter for swing: allow more setups
            # MIN_QUALITY_SCORE is typically 5.0 – we accept anything >= 3.0 here.
            if quality_score < 3.0:
                return None
            
            # Direction determination
            direction = None
            if alpha_signal > threshold:
                direction = "BUY"
            elif alpha_signal < -threshold:
                direction = "SELL"
                
            if not direction:
                return None
            
            # Macro filter: advisory only for swing (H1). Alpha/quality drive the signal.
            macro_bias = MacroFilter.get_macro_bias(market_context)
            
            # News filter check
            if news_events:
                if not NewsFilter.is_safe_to_trade(news_events, symbol):
                    return None
            
            latest = df.iloc[-1]
            atr = latest['atr']
            
            # Optimal R:R for swing (wider targets)
            optimal_rr = RiskManager.calculate_optimal_rr(quality_score, regime)
            # Swing uses wider stops
            sl_distance = atr * 2.5
            
            # Dynamic TP levels with swing-appropriate multipliers
            swing_rr_multiplier = 2.0  # Swing targets are wider
            if direction == "BUY":
                sl = latest['close'] - sl_distance
                tp0 = latest['close'] + (sl_distance * optimal_rr['tp1_rr'] * swing_rr_multiplier)
                tp1 = latest['close'] + (sl_distance * optimal_rr['tp2_rr'] * swing_rr_multiplier)
                tp2 = latest['close'] + (sl_distance * optimal_rr['tp3_rr'] * swing_rr_multiplier)
            else:
                sl = latest['close'] + sl_distance
                tp0 = latest['close'] - (sl_distance * optimal_rr['tp1_rr'] * swing_rr_multiplier)
                tp1 = latest['close'] - (sl_distance * optimal_rr['tp2_rr'] * swing_rr_multiplier)
                tp2 = latest['close'] - (sl_distance * optimal_rr['tp3_rr'] * swing_rr_multiplier)
            
            risk_details = RiskManager.calculate_lot_size(symbol, latest['close'], sl)
            
            # V11.0 Guidance-Based Risk (Signals are always sent with warnings)
            
            return {
                'strategy_id': self.get_id(),
                'strategy_name': self.get_name(),
                'symbol': symbol,
                'direction': direction,
                'timeframe': 'H1',
                'trade_type': 'SWING',
                'entry_price': latest['close'],
                'sl': sl,
                'tp0': tp0,
                'tp1': tp1,
                'tp2': tp2,
                'confidence': abs(alpha_signal),
                'quality_score': quality_score,
                'regime': regime,
                'macro_bias': macro_bias,
                'risk_details': risk_details,
                'expected_hold': '1-7 days',
                'score_details': {
                    'velocity': factors['velocity'],
                    'zscore': factors['zscore'],
                    'momentum': factors['momentum'],
                    'volatility': factors['volatility'],
                    'signal': alpha_signal,
                    'optimal_rr': optimal_rr
                }
            }
        except Exception as e:
            return None
