import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from strategies.crt_strategy import CRTStrategy
from unittest.mock import patch, MagicMock

@pytest.fixture
def base_h1_data():
    """Create a baseline H1 dataframe with enough rows and required indicators."""
    dates = pd.date_range(end=datetime(2025, 1, 1, 12, 0), periods=30, freq='h')
    df = pd.DataFrame({
        'open': [1.1000] * 30,
        'high': [1.1010] * 30,
        'low': [1.0990] * 30,
        'close': [1.1000] * 30,
        'ema_fast': [1.1010] * 30,
        'ema_slow': [1.1005] * 30,
        'ema_trend': [1.1000] * 30,
        'atr': [0.0010] * 30
    }, index=dates)
    return df

@pytest.fixture
def base_m5_data():
    """Create a baseline M5 dataframe."""
    dates = pd.date_range(end=datetime(2025, 1, 1, 12, 0), periods=100, freq='5min')
    df = pd.DataFrame({
        'open': [1.1000] * 100,
        'high': [1.1005] * 100,
        'low': [1.0995] * 100,
        'close': [1.1000] * 100
    }, index=dates)
    return df

@pytest.mark.asyncio
async def test_crt_strategy_id():
    strat = CRTStrategy()
    assert strat.get_id() == "crt_h1"
    assert "Candle Range" in strat.get_name()

@pytest.mark.asyncio
async def test_crt_strategy_insufficient_data():
    strat = CRTStrategy()
    # H1 too short
    df_h1 = pd.DataFrame({'close': [1.1]*5})
    df_m5 = pd.DataFrame({'close': [1.1]*100})
    res = await strat.analyze("EURUSD", {'h1': df_h1, 'm5': df_m5}, [], {})
    assert res is None

@pytest.mark.asyncio
async def test_crt_strategy_bullish_signal(base_h1_data, base_m5_data):
    strat = CRTStrategy()
    
    # Setup Bullish Sweep on H1
    base_h1_data.iloc[-3, base_h1_data.columns.get_loc('low')] = 1.0990
    base_h1_data.iloc[-2, base_h1_data.columns.get_loc('low')] = 1.0985
    base_h1_data.iloc[-2, base_h1_data.columns.get_loc('open')] = 1.1000
    base_h1_data.iloc[-2, base_h1_data.columns.get_loc('close')] = 1.1005
    base_h1_data.iloc[-2, base_h1_data.columns.get_loc('high')] = 1.1010
    
    # Setup M5 MSS (Bullish) - strong close
    base_m5_data.iloc[-1, base_m5_data.columns.get_loc('high')] = 1.1020
    base_m5_data.iloc[-1, base_m5_data.columns.get_loc('low')] = 1.1010
    base_m5_data.iloc[-1, base_m5_data.columns.get_loc('close')] = 1.1019 
    base_m5_data['open'] = 1.1000 
    
    # Trend alignment (Bullish is default in fixture)
    
    data = {'h1': base_h1_data, 'm5': base_m5_data}
    
    with patch('strategies.crt_strategy.MacroFilter.is_macro_safe', return_value=True), \
         patch('strategies.crt_strategy.RiskManager.calculate_lot_size', return_value={'lot_size': 0.1}):
        res = await strat.analyze("EURUSD", data, [], {})
        assert res is not None
        assert res['direction'] == "BUY"

@pytest.mark.asyncio
async def test_crt_strategy_bearish_signal(base_h1_data, base_m5_data):
    strat = CRTStrategy()
    
    # Setup Bearish Sweep on H1
    base_h1_data.iloc[-3, base_h1_data.columns.get_loc('high')] = 1.1010
    base_h1_data.iloc[-2, base_h1_data.columns.get_loc('high')] = 1.1015
    base_h1_data.iloc[-2, base_h1_data.columns.get_loc('open')] = 1.1005
    base_h1_data.iloc[-2, base_h1_data.columns.get_loc('close')] = 1.1000
    
    # Setup M5 MSS (Bearish)
    base_m5_data.iloc[-1, base_m5_data.columns.get_loc('high')] = 1.0995
    base_m5_data.iloc[-1, base_m5_data.columns.get_loc('low')] = 1.0980
    base_m5_data.iloc[-1, base_m5_data.columns.get_loc('close')] = 1.0981 
    base_m5_data['open'] = 1.1000 
    
    # Trend alignment (Bearish)
    base_h1_data.iloc[-1, base_h1_data.columns.get_loc('ema_fast')] = 1.0980
    base_h1_data.iloc[-1, base_h1_data.columns.get_loc('ema_slow')] = 1.0990
    base_h1_data.iloc[-1, base_h1_data.columns.get_loc('ema_trend')] = 1.1000
    
    data = {'h1': base_h1_data, 'm5': base_m5_data}
    
    with patch('strategies.crt_strategy.MacroFilter.is_macro_safe', return_value=True), \
         patch('strategies.crt_strategy.RiskManager.calculate_lot_size', return_value={'lot_size': 0.1}):
        res = await strat.analyze("EURUSD", data, [], {})
        assert res is not None
        assert res['direction'] == "SELL"

@pytest.mark.asyncio
async def test_crt_strategy_small_risk_adjustment_bull(base_h1_data, base_m5_data):
    strat = CRTStrategy()
    # Bullish sweep
    base_h1_data.iloc[-3, base_h1_data.columns.get_loc('low')] = 1.1000
    base_h1_data.iloc[-2, base_h1_data.columns.get_loc('low')] = 1.0995 
    base_h1_data.iloc[-2, base_h1_data.columns.get_loc('open')] = 1.1005
    base_h1_data.iloc[-2, base_h1_data.columns.get_loc('close')] = 1.1006
    
    # Entry price very close to SL
    # SL = 1.0995 - 0.0001 = 1.0994
    # Entry = 1.0995 -> Risk 0.0001
    base_m5_data.iloc[-1, base_m5_data.columns.get_loc('high')] = 1.09951
    base_m5_data.iloc[-1, base_m5_data.columns.get_loc('low')] = 1.09945
    base_m5_data.iloc[-1, base_m5_data.columns.get_loc('close')] = 1.0995
    base_m5_data['open'] = 1.0990 
    
    # Trend alignment (Bullish) - Fixture is already bullish
    
    data = {'h1': base_h1_data, 'm5': base_m5_data}
    with patch('strategies.crt_strategy.MacroFilter.is_macro_safe', return_value=True):
        res = await strat.analyze("EURUSD", data, [], {})
        assert res is not None
        # SL adjusted to 1.0995 - 0.0002 = 1.0993
        assert res['sl'] == pytest.approx(1.0993, rel=1e-5)

@pytest.mark.asyncio
async def test_crt_strategy_small_risk_adjustment_bear(base_h1_data, base_m5_data):
    strat = CRTStrategy()
    # Bearish sweep
    base_h1_data.iloc[-3, base_h1_data.columns.get_loc('high')] = 1.1010
    base_h1_data.iloc[-2, base_h1_data.columns.get_loc('high')] = 1.1015
    base_h1_data.iloc[-2, base_h1_data.columns.get_loc('open')] = 1.1000
    base_h1_data.iloc[-2, base_h1_data.columns.get_loc('close')] = 1.0995
    
    # Entry price very close to SL
    # SL = 1.1015 + 0.0001 = 1.1016
    # Entry = 1.10155 -> Risk 0.00005
    base_m5_data.iloc[-1, base_m5_data.columns.get_loc('high')] = 1.10160
    base_m5_data.iloc[-1, base_m5_data.columns.get_loc('low')] = 1.10154
    base_m5_data.iloc[-1, base_m5_data.columns.get_loc('close')] = 1.10155
    base_m5_data['open'] = 1.1020 
    
    # Trend alignment (Bearish)
    base_h1_data.iloc[-1, base_h1_data.columns.get_loc('ema_fast')] = 1.0980
    base_h1_data.iloc[-1, base_h1_data.columns.get_loc('ema_slow')] = 1.0990
    base_h1_data.iloc[-1, base_h1_data.columns.get_loc('ema_trend')] = 1.1000
    
    data = {'h1': base_h1_data, 'm5': base_m5_data}
    with patch('strategies.crt_strategy.MacroFilter.is_macro_safe', return_value=True):
        res = await strat.analyze("EURUSD", data, [], {})
        assert res is not None
        # SL adjusted to 1.10155 + 0.0002 = 1.10175
        assert res['sl'] == pytest.approx(1.10175, rel=1e-5)

@pytest.mark.asyncio
async def test_crt_strategy_atr_range_limit(base_h1_data, base_m5_data):
    strat = CRTStrategy()
    # Range too small
    base_h1_data.iloc[-3, base_h1_data.columns.get_loc('low')] = 1.10005
    base_h1_data.iloc[-2, base_h1_data.columns.get_loc('low')] = 1.10000
    base_h1_data.iloc[-2, base_h1_data.columns.get_loc('high')] = 1.10010 
    
    data = {'h1': base_h1_data, 'm5': base_m5_data}
    res = await strat.analyze("EURUSD", data, [], {})
    assert res is None

@pytest.mark.asyncio
async def test_crt_strategy_macro_blocked(base_h1_data, base_m5_data):
    strat = CRTStrategy()
    base_h1_data.iloc[-3, base_h1_data.columns.get_loc('low')] = 1.0990
    base_h1_data.iloc[-2, base_h1_data.columns.get_loc('low')] = 1.0985
    base_h1_data.iloc[-2, base_h1_data.columns.get_loc('open')] = 1.1000
    base_h1_data.iloc[-2, base_h1_data.columns.get_loc('close')] = 1.1005
    
    # MSS
    base_m5_data.iloc[-1, base_m5_data.columns.get_loc('high')] = 1.1020
    base_m5_data.iloc[-1, base_m5_data.columns.get_loc('low')] = 1.1010
    base_m5_data.iloc[-1, base_m5_data.columns.get_loc('close')] = 1.1019 
    base_m5_data['open'] = 1.1000 

    data = {'h1': base_h1_data, 'm5': base_m5_data}
    with patch('strategies.crt_strategy.MacroFilter.is_macro_safe', return_value=False):
        res = await strat.analyze("EURUSD", data, [], {})
        assert res is None

@pytest.mark.asyncio
async def test_crt_strategy_news_blocked(base_h1_data, base_m5_data):
    strat = CRTStrategy()
    base_h1_data.iloc[-3, base_h1_data.columns.get_loc('low')] = 1.0990
    base_h1_data.iloc[-2, base_h1_data.columns.get_loc('low')] = 1.0985
    base_h1_data.iloc[-2, base_h1_data.columns.get_loc('open')] = 1.1000
    base_h1_data.iloc[-2, base_h1_data.columns.get_loc('close')] = 1.1005
    
    # MSS
    base_m5_data.iloc[-1, base_m5_data.columns.get_loc('high')] = 1.1020
    base_m5_data.iloc[-1, base_m5_data.columns.get_loc('low')] = 1.1010
    base_m5_data.iloc[-1, base_m5_data.columns.get_loc('close')] = 1.1019 
    base_m5_data['open'] = 1.1000 

    data = {'h1': base_h1_data, 'm5': base_m5_data}
    with patch('strategies.crt_strategy.MacroFilter.is_macro_safe', return_value=True), \
         patch('strategies.crt_strategy.NewsFilter.is_safe_to_trade', return_value=False):
        res = await strat.analyze("EURUSD", data, ["News"], {})
        assert res is None

@pytest.mark.asyncio
async def test_crt_strategy_exception_handling():
    strat = CRTStrategy()
    res = await strat.analyze("EURUSD", {}, [], {})
    assert res is None
