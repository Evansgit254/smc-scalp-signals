from typing import Dict, Optional
from .alpha_factors import AlphaFactors

class AlphaCombiner:
    @staticmethod
    def combine(factors: Dict[str, float], regime: str = "NORMAL", symbol: Optional[str] = None) -> float:
        """
        Pure Mathematical Aggregator with Regime + Symbol Adaptation.
        Uses per-symbol IC-derived weights when available (V22.2).
        Falls back to global regime weights otherwise.
        """
        from config.config import SYMBOL_ALPHA_WEIGHTS

        # 1. Try per-symbol weights for this regime
        sym_weights = SYMBOL_ALPHA_WEIGHTS.get(symbol, {}).get(regime) if symbol else None

        if sym_weights:
            weights = sym_weights
        else:
            # Global regime-adaptive weights (fallback)
            if regime == "TRENDING":
                weights = {
                    'velocity': 0.7,      # V22.1: Increased from 0.5 (Strongest Factor)
                    'zscore': 0.1,        # V22.1: Decreased from 0.3 (Negative Edge in Trends)
                    'momentum': 0.2,      # Momentum matters in trends
                    'volatility': 0.0
                }
            elif regime == "RANGING":
                weights = {
                    'velocity': 0.3,
                    'zscore': 0.5,        # Mean reversion matters more
                    'momentum': 0.1,
                    'volatility': 0.1
                }
            else:  # NORMAL/CHOPPY
                weights = {
                    'velocity': 0.4,
                    'zscore': 0.5,
                    'momentum': 0.05,
                    'volatility': 0.05
                }

        total_signal = 0.0
        for name, value in factors.items():
            weight = weights.get(name, 0.0)
            # Standardizing input: clip factors at 4.0 std devs
            clipped_value = max(min(value, 4.0), -4.0)
            total_signal += clipped_value * weight

        return round(total_signal, 4)

    
    @staticmethod
    def calculate_quality_score(factors: Dict[str, float], signal: float) -> float:
        """
        Calculates signal quality score (0-10) based on factor alignment.
        Higher quality = better R:R potential.
        """
        # Factor alignment: all factors pointing same direction = higher quality
        factor_values = [v for v in factors.values() if v != 0]
        if not factor_values:
            return 0.0
        
        # Check alignment (all same sign = high quality)
        signs = [1 if v > 0 else -1 for v in factor_values]
        alignment = 1.0 if len(set(signs)) == 1 else 0.5
        
        # Signal strength component
        signal_strength = min(abs(signal) / 2.0, 1.0)  # Normalize to 0-1
        
        # Combined quality score (0-10)
        quality = (alignment * 0.6 + signal_strength * 0.4) * 10.0
        return round(quality, 2)