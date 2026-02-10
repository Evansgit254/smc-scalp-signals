import pandas as pd
import numpy as np
from typing import Dict

class AlphaFactors:
    @staticmethod
    def velocity_alpha(df: pd.DataFrame, period: int = 20) -> float:
        """
        Mathematical Alpha: Normalized Linear Regression Slope.
        Measures the velocity of price movement relative to volatility.
        """
        if len(df) < period:
            return 0.0
        
        y = df['close'].tail(period).values
        x = np.arange(len(y))
        slope, intercept = np.polyfit(x, y, 1)
        
        # Normalize slope by ATR to get unitless velocity
        atr = df['atr'].iloc[-1]
        if atr == 0: return 0.0
        
        velocity = slope / atr
        return velocity

    @staticmethod
    def mean_reversion_zscore(df: pd.DataFrame, period: int = 100) -> float:
        """
        Mathematical Alpha: Z-Score distance from mean (EMA).
        Quantifies overextension for reversal potential.
        """
        if len(df) < period:
            return 0.0
            
        ema_col = f'ema_{period}'
        if ema_col not in df.columns:
            return 0.0
            
        distance = df['close'].iloc[-1] - df[ema_col].iloc[-1]
        std_dev = df['close'].tail(period).std()
        
        if std_dev == 0: return 0.0
        
        z_score = distance / std_dev
        return z_score

    @staticmethod
    def relative_strength_alpha(symbol_df: pd.DataFrame, benchmark_df: pd.DataFrame) -> float:
        """
        Mathematical Alpha: Relative performance ratio.
        Identifies leading vs lagging assets mathematically.
        """
        # Align indices
        common_idx = symbol_df.index.intersection(benchmark_df.index)
        if len(common_idx) < 20:
            return 0.0
            
        s_prices = symbol_df.loc[common_idx, 'close']
        b_prices = benchmark_df.loc[common_idx, 'close']
        
        ratio = s_prices / b_prices
        # Return slope of the ratio
        x = np.arange(len(ratio.tail(20)))
        slope, _ = np.polyfit(x, ratio.tail(20).values, 1)
        return slope
    
    @staticmethod
    def momentum_alpha(df: pd.DataFrame, short_period: int = 10, long_period: int = 30) -> float:
        """
        Mathematical Alpha: Momentum divergence.
        Measures acceleration in price movement.
        """
        if len(df) < long_period:
            return 0.0
        
        short_roc = (df['close'].iloc[-1] / df['close'].iloc[-short_period] - 1) * 100
        long_roc = (df['close'].iloc[-1] / df['close'].iloc[-long_period] - 1) * 100
        
        # Normalize by ATR
        atr = df['atr'].iloc[-1]
        if atr == 0: return 0.0
        
        momentum = (short_roc - long_roc) / (atr * 10000)  # Normalize
        return momentum
    
    @staticmethod
    def volatility_regime_alpha(df: pd.DataFrame, period: int = 50) -> float:
        """
        Mathematical Alpha: Volatility regime detection.
        Identifies expansion/compression cycles for regime-adaptive trading.
        """
        if len(df) < period:
            return 0.0
        
        current_atr = df['atr'].iloc[-1]
        avg_atr = df['atr'].tail(period).mean()
        
        if avg_atr == 0: return 0.0
        
        # Volatility ratio: >1 = expanding, <1 = compressing
        vol_ratio = current_atr / avg_atr
        
        # Return normalized regime signal (-1 to 1)
        # 1.0 = high expansion, -1.0 = high compression
        regime_signal = np.tanh((vol_ratio - 1.0) * 2.0)
        return regime_signal
