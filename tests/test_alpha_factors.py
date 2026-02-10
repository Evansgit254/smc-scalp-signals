"""
Comprehensive unit tests for Alpha Factors
100% coverage target
"""
import pytest
import pandas as pd
import numpy as np
from core.alpha_factors import AlphaFactors

class TestAlphaFactors:
    """Test suite for alpha factor calculations"""
    
    @pytest.fixture
    def sample_df(self):
        """Create sample market data for testing"""
        dates = pd.date_range('2024-01-01', periods=250, freq='5min')
        np.random.seed(42)
        
        # Create realistic price data
        close_prices = 1.0850 + np.cumsum(np.random.randn(250) * 0.0001)
        high_prices = close_prices + np.abs(np.random.randn(250) * 0.0002)
        low_prices = close_prices - np.abs(np.random.randn(250) * 0.0002)
        
        # Create series first for rolling
        close_series = pd.Series(close_prices, index=dates)
        
        df = pd.DataFrame({
            'close': close_prices,
            'high': high_prices,
            'low': low_prices,
            'atr': np.abs(np.random.randn(250) * 0.0005) + 0.0003,
            'ema_100': close_series.rolling(100).mean().fillna(close_prices[0]),
            'volume': np.random.randint(1000, 50000, 250)
        }, index=dates)
        
        return df
    
    def test_velocity_alpha_basic(self, sample_df):
        """Test velocity alpha calculation returns valid output"""
        velocity = AlphaFactors.velocity_alpha(sample_df, period=20)
        
        assert isinstance(velocity, (float, np.floating))
        assert not np.isnan(velocity)
        assert not np.isinf(velocity)
        
    def test_velocity_alpha_range(self, sample_df):
        """Test velocity alpha stays within reasonable bounds"""
        velocity = AlphaFactors.velocity_alpha(sample_df, period=20)
        
        # Should be normalized, typically between -5 and +5
        assert -10.0 <= velocity <= 10.0
        
    def test_velocity_alpha_empty_df(self):
        """Test velocity alpha handles empty dataframe"""
        empty_df = pd.DataFrame()
        velocity = AlphaFactors.velocity_alpha(empty_df, period=20)
        
        assert velocity == 0.0
        
    def test_velocity_alpha_insufficient_data(self):
        """Test velocity alpha with less data than period"""
        short_df = pd.DataFrame({
            'close': [1.0, 1.1, 1.2],
            'atr': [0.001, 0.001, 0.001]
        })
        
        velocity = AlphaFactors.velocity_alpha(short_df, period=20)
        assert velocity == 0.0
        
    def test_mean_reversion_zscore_basic(self, sample_df):
        """Test mean reversion z-score calculation"""
        zscore = AlphaFactors.mean_reversion_zscore(sample_df, period=100)
        
        assert isinstance(zscore, (float, np.floating))
        assert not np.isnan(zscore)
        assert not np.isinf(zscore)
        
    def test_mean_reversion_zscore_range(self, sample_df):
        """Test z-score stays within statistical bounds"""
        zscore = AlphaFactors.mean_reversion_zscore(sample_df, period=100)
        
        # Z-scores beyond ±4 are extremely rare
        assert -5.0 <= zscore <= 5.0
        
    def test_mean_reversion_zero_stddev(self):
        """Test z-score handles zero standard deviation"""
        flat_df = pd.DataFrame({
            'close': [1.0] * 150,
            'ema_100': [1.0] * 150
        })
        
        zscore = AlphaFactors.mean_reversion_zscore(flat_df, period=100)
        assert zscore == 0.0
        
    def test_relative_strength_alpha_basic(self, sample_df):
        """Test relative strength alpha calculation"""
        # Create benchmark data
        benchmark_df = sample_df.copy()
        benchmark_df['close'] = benchmark_df['close'] * 1.001
        
        rs_alpha = AlphaFactors.relative_strength_alpha(sample_df, benchmark_df)
        
        assert isinstance(rs_alpha, (float, np.floating))
        assert not np.isnan(rs_alpha)
        
    def test_relative_strength_insufficient_overlap(self, sample_df):
        """Test relative strength with minimal data overlap"""
        # Create non-overlapping benchmark
        benchmark_df = pd.DataFrame({
            'close': [1.0] * 10
        }, index=pd.date_range('2025-01-01', periods=10, freq='5min'))
        
        rs_alpha = AlphaFactors.relative_strength_alpha(sample_df, benchmark_df)
        assert rs_alpha == 0.0
