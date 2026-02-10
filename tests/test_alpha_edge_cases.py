"""
Additional edge case tests to achieve 100% coverage
"""
import pytest
import pandas as pd
from core.alpha_factors import AlphaFactors

def test_mean_reversion_missing_column():
    """Test mean reversion when ema column doesn't exist"""
    df = pd.DataFrame({
        'close': [1.0, 1.1, 1.2] * 50
    })
    
    zscore = AlphaFactors.mean_reversion_zscore(df, period=100)
    assert zscore == 0.0

def test_mean_reversion_empty_df():
    """Test mean reversion with empty dataframe"""
    df = pd.DataFrame()
    zscore = AlphaFactors.mean_reversion_zscore(df, period=100)
    assert zscore == 0.0
