import pytest
import pandas as pd
import numpy as np
from strategies.intraday_quant_strategy import IntradayQuantStrategy
from strategies.swing_quant_strategy import SwingQuantStrategy
from unittest.mock import patch, MagicMock

@pytest.fixture
def sample_data():
    dates = pd.date_range('2024-01-01', periods=300, freq='5min')
    close = np.linspace(1.1000, 1.1100, 300) # Trending up
    df = pd.DataFrame({
        'open': close - 0.0001,
        'high': close + 0.0002,
        'low': close - 0.0002,
        'close': close,
        'atr': [0.0010] * 300,
        'atr_avg': [0.0010] * 300
    }, index=dates)
    # Add indicators for regime etc
    from indicators.calculations import IndicatorCalculator
    df = IndicatorCalculator.add_indicators(df, "5m")
    return {'m5': df, 'h1': df} # Simple mock

@pytest.mark.asyncio
async def test_intraday_strategy_buy_signal(sample_data):
    strategy = IntradayQuantStrategy()
    # Mock alpha factors to force a BUY signal
    # Mock alpha factors to force a strong BUY signal (must exceed 0.8 threshold in RANGING)
    with patch('core.alpha_factors.AlphaFactors.velocity_alpha', return_value=3.0), \
         patch('core.alpha_factors.AlphaFactors.mean_reversion_zscore', return_value=4.0), \
         patch('core.alpha_factors.AlphaFactors.momentum_alpha', return_value=2.0), \
         patch('core.alpha_factors.AlphaFactors.volatility_regime_alpha', return_value=1.0), \
         patch('core.filters.news_filter.NewsFilter.is_safe_to_trade', return_value=True), \
         patch('core.filters.macro_filter.MacroFilter.is_macro_safe', return_value=True):
        
        res = await strategy.analyze("EURUSD=X", sample_data, [], {})
        assert res is not None
        assert res['direction'] == "BUY"
        assert 'quality_score' in res

@pytest.mark.asyncio
async def test_intraday_strategy_news_block(sample_data):
    strategy = IntradayQuantStrategy()
    with patch('core.filters.news_filter.NewsFilter.is_safe_to_trade', return_value=False):
        res = await strategy.analyze("EURUSD=X", sample_data, ["NewsEvent"], {})
        assert res is None

@pytest.mark.asyncio
async def test_swing_strategy_buy_signal(sample_data):
    strategy = SwingQuantStrategy()
    with patch('core.alpha_factors.AlphaFactors.velocity_alpha', return_value=0.9), \
         patch('core.alpha_factors.AlphaFactors.mean_reversion_zscore', return_value=2.0), \
         patch('core.filters.news_filter.NewsFilter.is_safe_to_trade', return_value=True):
        
        res = await strategy.analyze("EURUSD=X", sample_data, [], {})
        assert res is not None
        assert res['direction'] == "BUY"
        assert res['timeframe'] == "H1"

@pytest.mark.asyncio
async def test_swing_strategy_exception(sample_data):
    strategy = SwingQuantStrategy()
    # Mock something to raise exception
    with patch('indicators.calculations.IndicatorCalculator.get_market_regime', side_effect=Exception("Test Exception")):
        res = await strategy.analyze("EURUSD=X", sample_data, [], {})
        assert res is None
