import pytest
import pandas as pd
from datetime import datetime, time
import pytz
from strategies.advanced_pattern_strategy import AdvancedPatternStrategy
from unittest.mock import patch

@pytest.mark.asyncio
async def test_v23_dow_hourly_jpy_wed():
    strategy = AdvancedPatternStrategy()
    # Wednesday (2) at 21:00 UTC
    bt = datetime(2026, 2, 18, 21, 0, tzinfo=pytz.UTC)
    df = pd.DataFrame({
        'open': [150.0] * 30,
        'high': [150.5] * 30,
        'low': [149.5] * 30,
        'close': [150.0] * 30,
    }, index=pd.date_range(end=bt, periods=30, freq='h'))
    
    data = {'h1': df}
    # Mock RiskManager to avoid env var issues
    with patch('strategies.advanced_pattern_strategy.RiskManager.calculate_lot_size', return_value={'lots': 0.1}):
        res = await strategy.analyze('USDJPY=X', data, [], {})
        assert res is not None
        assert res['direction'] == 'SELL'
        assert res['quality_score'] == 9.5
        assert 'DOW-WED-BEAR' in res['expected_hold']

@pytest.mark.asyncio
async def test_v23_stop_hunt_oil():
    strategy = AdvancedPatternStrategy()
    # Any Tuesday (1) at 14:00 UTC
    bt = datetime(2026, 2, 17, 14, 0, tzinfo=pytz.UTC)
    
    # Create a "Top Pin" bar
    # open=100, high=105, low=99.5, close=100.5
    # Body = 0.5, High Wick = 105 - 100.5 = 4.5
    # ATR estimate will be calculated from range
    df = pd.DataFrame({
        'open': [100.0] * 29 + [100.0],
        'high': [101.0] * 29 + [105.0], # Spike high
        'low':  [99.0]  * 29 + [99.5],
        'close':[100.5] * 29 + [100.5],
    }, index=pd.date_range(end=bt, periods=30, freq='h'))
    
    data = {'h1': df}
    with patch('strategies.advanced_pattern_strategy.RiskManager.calculate_lot_size', return_value={'lots': 0.1}):
        res = await strategy.analyze('CL=F', data, [], {})
        assert res is not None
        assert res['direction'] == 'SELL'
        assert res['regime'] == 'PA_REVERSAL'
        assert 'STOP_HUNT_REVERSAL' in res['expected_hold']

@pytest.mark.asyncio
async def test_v23_no_signal():
    strategy = AdvancedPatternStrategy()
    # Tuesday at 10:00 UTC -> No signal defined
    bt = datetime(2026, 2, 17, 10, 0, tzinfo=pytz.UTC)
    df = pd.DataFrame({
        'open': [100.0] * 30,
        'high': [101.0] * 30,
        'low': [99.0] * 30,
        'close': [100.5] * 30,
    }, index=pd.date_range(end=bt, periods=30, freq='h'))
    
    data = {'h1': df}
    res = await strategy.analyze('EURUSD=X', data, [], {})
    assert res is None
