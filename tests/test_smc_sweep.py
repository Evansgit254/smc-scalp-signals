import pytest
import pandas as pd
from datetime import datetime, timezone
from strategies.smc_liquidity_sweep import SMCLiquiditySweepStrategy
from unittest.mock import patch

@pytest.fixture
def sweep_data():
    # 30 hours of data ending at 12:00 UTC
    dates = pd.date_range(end=datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc), periods=30, freq='h')
    df = pd.DataFrame({
        'open': [1.1000] * 30,
        'high': [1.1010] * 30,
        'low': [1.0990] * 30,
        'close': [1.1000] * 30,
        'atr': [0.0010] * 30
    }, index=dates)
    return df

@pytest.mark.asyncio
async def test_smc_sweep_id():
    strat = SMCLiquiditySweepStrategy()
    assert strat.get_id() == "smc_sweep_v1"
    assert "Asian" in strat.get_name()

@pytest.mark.asyncio
async def test_smc_sweep_banned_symbol():
    strat = SMCLiquiditySweepStrategy()
    res = await strat.analyze("CL=F", {}, [], {})
    assert res is None

@pytest.mark.asyncio
async def test_smc_sweep_insufficient_data():
    strat = SMCLiquiditySweepStrategy()
    res = await strat.analyze("EURUSD", {'h1': pd.DataFrame()}, [], {})
    assert res is None

@pytest.mark.asyncio
async def test_smc_sweep_off_hours(sweep_data):
    strat = SMCLiquiditySweepStrategy()
    # 22:00 is off hours (> 20:00)
    sweep_data.index = pd.date_range(end=datetime(2025, 1, 1, 22, 0, tzinfo=timezone.utc), periods=30, freq='h')
    res = await strat.analyze("EURUSD", {'h1': sweep_data}, [], {})
    assert res is None

@pytest.mark.asyncio
async def test_smc_sweep_banned_hour(sweep_data):
    strat = SMCLiquiditySweepStrategy()
    # 14:00 is banned
    sweep_data.index = pd.date_range(end=datetime(2025, 1, 1, 14, 0, tzinfo=timezone.utc), periods=30, freq='h')
    res = await strat.analyze("EURUSD", {'h1': sweep_data}, [], {})
    assert res is None

@pytest.mark.asyncio
async def test_smc_sweep_high_v1(sweep_data):
    strat = SMCLiquiditySweepStrategy()
    # Asian session: 00:00 to 07:59.
    # Let's set Asian High at 1.1020 (at 04:00)
    sweep_data.loc[sweep_data.index.hour == 4, 'high'] = 1.1020
    
    # Latest candle (12:00): sweep high
    # high > 1.1020, close < 1.1020, wick_top > body
    sweep_data.iloc[-1, sweep_data.columns.get_loc('open')] = 1.1010
    sweep_data.iloc[-1, sweep_data.columns.get_loc('close')] = 1.1015
    sweep_data.iloc[-1, sweep_data.columns.get_loc('high')] = 1.1025
    sweep_data.iloc[-1, sweep_data.columns.get_loc('low')] = 1.1010
    
    with patch('strategies.smc_liquidity_sweep.RiskManager.calculate_lot_size', return_value={}):
        res = await strat.analyze("EURUSD", {'h1': sweep_data}, [], {})
        assert res is not None
        assert res['direction'] == "SELL"

@pytest.mark.asyncio
async def test_smc_sweep_low_v1(sweep_data):
    strat = SMCLiquiditySweepStrategy()
    # Asian Low at 1.0980 (at 02:00)
    sweep_data.loc[sweep_data.index.hour == 2, 'low'] = 1.0980
    
    # Latest candle (12:00): sweep low
    # low < 1.0980, close > 1.0980, wick_bot > body
    sweep_data.iloc[-1, sweep_data.columns.get_loc('open')] = 1.0990
    sweep_data.iloc[-1, sweep_data.columns.get_loc('close')] = 1.0985
    sweep_data.iloc[-1, sweep_data.columns.get_loc('low')] = 1.0970
    sweep_data.iloc[-1, sweep_data.columns.get_loc('high')] = 1.0990
    
    with patch('strategies.smc_liquidity_sweep.RiskManager.calculate_lot_size', return_value={}):
        res = await strat.analyze("EURUSD", {'h1': sweep_data}, [], {})
        assert res is not None
        assert res['direction'] == "BUY"

@pytest.mark.asyncio
async def test_smc_sweep_no_signal(sweep_data):
    strat = SMCLiquiditySweepStrategy()
    # No sweep occurs
    res = await strat.analyze("EURUSD", {'h1': sweep_data}, [], {})
    assert res is None

@pytest.mark.asyncio
async def test_smc_sweep_exception():
    strat = SMCLiquiditySweepStrategy()
    res = await strat.analyze("EURUSD", None, [], {})
    assert res is None
