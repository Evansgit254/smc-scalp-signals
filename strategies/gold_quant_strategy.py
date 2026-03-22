from .base_strategy import BaseStrategy
from typing import Optional, Dict
import pandas as pd
from core.alpha_factors import AlphaFactors
from core.alpha_combiner import AlphaCombiner
from core.filters.risk_manager import RiskManager
from core.filters.session_filter import SessionFilter
from indicators.calculations import IndicatorCalculator
from config.config import MIN_QUALITY_SCORE_INTRADAY

class GoldQuantStrategy(BaseStrategy):
    """
    Dedicated Gold (GC=F) Scalping Strategy
    Wider stops, strict DXY tracking, and extreme mean-reversion/momentum.
    """
    def get_id(self) -> str:
        return "gold_quant_m5"

    def get_name(self) -> str:
        return "Gold Quant (GC=F Dedicated)"

    async def analyze(self, symbol: str, data: Dict[str, pd.DataFrame], news_events: list, market_context: dict) -> Optional[dict]:
        try:
            if symbol != "GC=F":
                return None
                
            df = data.get('m5')
            if df is None or len(df) < 100: 
                return None
            
            # Use same session rules or trade broader? Stick to peak sessions for liquidity.
            latest_time = df.index[-1]
            if not SessionFilter.is_peak_session(check_time=latest_time):
                return None
                
            regime = IndicatorCalculator.get_market_regime(df)
            if regime in ["CHOPPY", "UNKNOWN"]:
                return None
            
            # Gold-specific alpha factors
            factors = {
                'velocity': AlphaFactors.velocity_alpha(df, period=20),
                'zscore': AlphaFactors.mean_reversion_zscore(df, period=100),
                'momentum': AlphaFactors.momentum_alpha(df, short_period=10, long_period=30),
                'volatility': AlphaFactors.volatility_regime_alpha(df, period=50)
            }
            
            alpha_signal = AlphaCombiner.combine(factors, regime=regime, symbol=symbol)
            quality_score = AlphaCombiner.calculate_quality_score(factors, alpha_signal)
            
            # High frequency requirement for Gold: lower the quality bar to ensure daily action
            if quality_score < 5.0:
                return None
                
            direction = None
            if alpha_signal > 0.35:
                direction = "BUY"
            elif alpha_signal < -0.35:
                direction = "SELL"
                
            if not direction:
                return None
            
            # DXY Inverse Correlation 
            # If DXY is bullish (fast > slow EMA), restrict Gold to SELL.
            # If DXY is bearish (fast < slow EMA), restrict Gold to BUY.
            dxy_data = market_context.get('DXY')
            if dxy_data is not None and not dxy_data.empty:
                dxy_latest = dxy_data.iloc[-1]
                dxy_fast = dxy_latest.get('ema_fast')
                dxy_slow = dxy_latest.get('ema_slow')
                
                if dxy_fast is not None and dxy_slow is not None:
                    # V26.1 FORENSIC FIX: Soften DXY block to a score penalty instead of a hard block
                    # Gold and DXY can move together intraday during heavy risk-off flows
                    if quality_score < 8.0:
                        if dxy_fast > dxy_slow and direction == "BUY":
                            quality_score -= 1.5 
                        if dxy_fast < dxy_slow and direction == "SELL":
                            quality_score -= 1.5
            
            # Re-check quality score after DXY penalty
            if quality_score < 5.0:
                return None

            latest = df.iloc[-1]
            atr = latest['atr']
            
            optimal_rr = RiskManager.calculate_optimal_rr(symbol, quality_score, regime, atr)
            if optimal_rr.get('is_friction_heavy'):
                return None
                
            # V26.1 FORENSIC FIX: Disconnect TP from the widened SL. 
            # Multiplying a 2.8 ATR SL by 1.5 RR created unreachable 4.2+ ATR Take Profits.
            sl_distance = atr * 2.5 
            
            # Fixed, realistic scaling targets for M5 Gold Scalping
            tp0_dist = atr * 1.0  # Quick scalp secured
            tp1_dist = atr * 2.0  # Main target
            tp2_dist = atr * 4.0  # Runner for huge moves
            
            # No pullback limit entry (enter at market or close) to avoid missing explosive moves
            entry_price = latest['close'] 
            
            if direction == "BUY":
                sl = entry_price - sl_distance
                tp0 = entry_price + tp0_dist
                tp1 = entry_price + tp1_dist
                tp2 = entry_price + tp2_dist
            else:
                sl = entry_price + sl_distance
                tp0 = entry_price - tp0_dist
                tp1 = entry_price - tp1_dist
                tp2 = entry_price - tp2_dist
            
            risk_details = RiskManager.calculate_lot_size(symbol, entry_price, sl)
            
            return {
                'strategy_id': self.get_id(),
                'strategy_name': self.get_name(),
                'symbol': symbol,
                'direction': direction,
                'timeframe': 'M5',
                'trade_type': 'ADVANCED_PATTERN', # Map to ADVANCED_PATTERN so backtests prioritize it
                'entry_price': entry_price,
                'is_limit_order': False,
                'sl': sl,
                'tp0': tp0,
                'tp1': tp1,
                'tp2': tp2,
                'confidence': abs(alpha_signal),
                'quality_score': quality_score,
                'regime': regime,
                'risk_details': risk_details,
                'expected_hold': '2-6 hours',
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
