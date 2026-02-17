from .base_strategy import BaseStrategy
from typing import Optional, Dict
import pandas as pd
from core.alpha_factors import AlphaFactors
from core.alpha_combiner import AlphaCombiner
from core.filters.risk_manager import RiskManager
from core.filters.macro_filter import MacroFilter
from core.filters.news_filter import NewsFilter
from core.filters.session_filter import SessionFilter
from indicators.calculations import IndicatorCalculator
from config.config import ATR_MULTIPLIER, MIN_QUALITY_SCORE_INTRADAY

class IntradayQuantStrategy(BaseStrategy):
    """
    Intraday M5 Scalping Strategy
    Targets: 2-3R average, 4-8 hour holds
    Frequency: ~10-15 signals/day
    """
    def get_id(self) -> str:
        return "intraday_quant_m5"

    def get_name(self) -> str:
        return "Intraday Quant (M5 Scalp)"

    async def analyze(self, symbol: str, data: Dict[str, pd.DataFrame], news_events: list, market_context: dict) -> Optional[dict]:
        try:
            df = data.get('m5')
            if df is None or len(df) < 100: 
                return None
            
            # V14.1 Session Hardening: Only trade during London/NY Open
            latest_time = df.index[-1]
            if not SessionFilter.is_valid_session(check_time=latest_time):
                return None
            regime = IndicatorCalculator.get_market_regime(df)
            
            # Enhanced Alpha Factors (added momentum and volatility)
            factors = {
                'velocity': AlphaFactors.velocity_alpha(df, period=20),
                'zscore': AlphaFactors.mean_reversion_zscore(df, period=100),
                'momentum': AlphaFactors.momentum_alpha(df, short_period=10, long_period=30),
                'volatility': AlphaFactors.volatility_regime_alpha(df, period=50)
            }
            
            # Regime-adaptive signal combination
            alpha_signal = AlphaCombiner.combine(factors, regime=regime)
            
            # Calculate quality score
            quality_score = AlphaCombiner.calculate_quality_score(factors, alpha_signal)
            
            # Adaptive thresholds
            # V15.0 Balanced Scalp Thresholds
            thresholds = {
                "TRENDING": 0.65, # Relaxed from 0.7
                "RANGING": 0.80, # Relaxed from 0.85
                "CHOPPY": 1.0
            }
            threshold = thresholds.get(regime, 0.72)
            
            # Quality filter
            if quality_score < MIN_QUALITY_SCORE_INTRADAY:
                return None
            
            # Direction determination with adaptive threshold
            direction = None
            if alpha_signal > threshold:
                direction = "BUY"
            elif alpha_signal < -threshold:
                direction = "SELL"
                
            if not direction:
                return None
            
            # Macro filter check - advisory for high quality signals
            # Only block if there's a conflict AND quality is below 8.0
            # Macro filter check - V13.0 Hardened: No direct contradictions allowed
            macro_bias = MacroFilter.get_macro_bias(market_context)
            macro_safe = MacroFilter.is_macro_safe(symbol, direction, macro_bias)
            
            # Reject if direct conflict (e.g., BUYing when macro is BEARISH on that asset class)
            if not macro_safe:
                return None
            
            # News filter check
            if news_events:
                if not NewsFilter.is_safe_to_trade(news_events, symbol):
                    return None
            
            latest = df.iloc[-1]
            atr = latest['atr']
            
            # Optimal R:R calculation based on quality, regime, and friction (SATP)
            optimal_rr = RiskManager.calculate_optimal_rr(symbol, quality_score, regime, atr)
            
            if optimal_rr.get('is_friction_heavy'):
                return None
                
            sl_distance = atr * 1.6 # Reduced from 1.8 for V15.0 (Restoring Win Rate)
            
            # Dynamic TP levels based on optimal R:R
            if direction == "BUY":
                sl = latest['close'] - sl_distance
                tp0 = latest['close'] + (sl_distance * optimal_rr['tp1_rr'])
                tp1 = latest['close'] + (sl_distance * optimal_rr['tp2_rr'])
                tp2 = latest['close'] + (sl_distance * optimal_rr['tp3_rr'])
            else:
                sl = latest['close'] + sl_distance
                tp0 = latest['close'] - (sl_distance * optimal_rr['tp1_rr'])
                tp1 = latest['close'] - (sl_distance * optimal_rr['tp2_rr'])
                tp2 = latest['close'] - (sl_distance * optimal_rr['tp3_rr'])
            
            risk_details = RiskManager.calculate_lot_size(symbol, latest['close'], sl)
            
            # V11.0 Guidance-Based Risk (Signals are always sent with warnings)
            
            return {
                'strategy_id': self.get_id(),
                'strategy_name': self.get_name(),
                'symbol': symbol,
                'direction': direction,
                'timeframe': 'M5',
                'trade_type': 'SCALP',
                'entry_price': latest['close'],
                'sl': sl,
                'tp0': tp0,
                'tp1': tp1,
                'tp2': tp2,
                'confidence': abs(alpha_signal),
                'quality_score': quality_score,
                'regime': regime,
                'risk_details': risk_details,
                'expected_hold': '4-8 hours',
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
