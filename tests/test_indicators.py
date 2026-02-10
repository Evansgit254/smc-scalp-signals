"""
Unit tests for IndicatorCalculator
Tests actual existing methods: add_indicators, calculate_adr, get_market_regime
"""
import pytest
import pandas as pd
import numpy as np
from indicators.calculations import IndicatorCalculator

class TestIndicators:
    
    @pytest.fixture
    def sample_df(self):
        """Create sample market data"""
        dates = pd.date_range('2024-01-01', periods=200, freq='1h')
        close = np.linspace(100, 200, 200) + np.random.randn(200)
        
        df = pd.DataFrame({
            'open': close - 1,
            'high': close + 2,
            'low': close - 2,
            'close': close,
            'volume': np.random.randint(100, 1000, 200)
        }, index=dates)
        return df

    def test_add_indicators_basic(self, sample_df):
        """Test add_indicators adds expected columns"""
        df = IndicatorCalculator.add_indicators(sample_df, timeframe="1h")
        
        # Check standard indicators
        expected_cols = ['ema_20', 'rsi', 'atr', 'atr_avg']
        for col in expected_cols:
            assert col in df.columns
            
        # Check no widespread NaNs (after startup period)
        assert not df['ema_20'].iloc[50:].isnull().any()

    def test_add_indicators_h1_logic(self, sample_df):
        """Test H1 specific logic like ADR"""
        df = IndicatorCalculator.add_indicators(sample_df, timeframe="h1")
        assert 'adr' in df.columns
        
    def test_add_indicators_empty(self):
        """Test empty dataframe handling"""
        df = pd.DataFrame()
        result = IndicatorCalculator.add_indicators(df, timeframe="5m")
        assert result.empty

    def test_calculate_adr(self, sample_df):
        """Test ADR calculation"""
        adr = IndicatorCalculator.calculate_adr(sample_df)
        assert isinstance(adr, pd.Series)
        assert len(adr) == len(sample_df)
        # ADR should be positive
        assert (adr.iloc[50:] >= 0).all()

    def test_calculate_ema_slope(self, sample_df):
        """Test slope calculation"""
        # Create a df with an EMA column
        sample_df['ema_50'] = sample_df['close'].rolling(50).mean()
        slope = IndicatorCalculator.calculate_ema_slope(sample_df, 'ema_50')
        assert isinstance(slope, float)
        assert -100 < slope < 100

    def test_get_market_regime(self, sample_df):
        """Test regime detection logic"""
        # Prepare DF with necessary columns for regime detection
        # It needs 'atr' and 'ema_50' (EMA_TREND)
        sample_df['atr'] = pd.Series(np.random.randn(200) + 10, index=sample_df.index).abs()
        sample_df['ema_50'] = sample_df['close'] # Fake EMA for slope
        
        regime = IndicatorCalculator.get_market_regime(sample_df)
        assert regime in ["TRENDING", "RANGING", "CHOPPY"]

    def test_calculate_h4_levels(self, sample_df):
        """Test H4 level pre-calculation"""
        df = IndicatorCalculator.calculate_h4_levels(sample_df)
        assert 'h4_high' in df.columns
        assert 'h4_low' in df.columns
        assert not df.empty
