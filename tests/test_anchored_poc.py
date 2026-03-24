import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from strategies.anchored_poc_strategy import AnchoredPOCStrategy
from unittest.mock import patch

@pytest.fixture
def poc_data():
    # 150 hours of data ending at 12:00 UTC (12:00 is a profitable hour)
    dates = pd.date_range(end=datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc), periods=150, freq='h')
    df = pd.DataFrame({
        'close': [1.1000] * 150,
        'atr': [0.0010] * 150,
        'rsi': [50.0] * 150
    }, index=dates)
    return df

@pytest.mark.asyncio
async def test_poc_strategy_id():
    strat = AnchoredPOCStrategy()
    assert strat.get_id() == "poc_edge_v1"

@pytest.mark.asyncio
async def test_poc_strategy_banned_symbol():
    strat = AnchoredPOCStrategy()
    res = await strat.analyze("EURUSD=X", {}, [], {})
    assert res is None

@pytest.mark.asyncio
async def test_poc_strategy_insufficient_data():
    strat = AnchoredPOCStrategy()
    res = await strat.analyze("GBPUSD=X", {'h1': pd.DataFrame()}, [], {})
    assert res is None

@pytest.mark.asyncio
async def test_poc_strategy_unprofitable_hour(poc_data):
    strat = AnchoredPOCStrategy()
    # 13:00 is not in {0, 3, 6, 12, 21, 22}
    poc_data.index = pd.date_range(end=datetime(2025, 1, 1, 13, 0, tzinfo=timezone.utc), periods=150, freq='h')
    res = await strat.analyze("GBPUSD=X", {'h1': poc_data}, [], {})
    assert res is None

@pytest.mark.asyncio
async def test_poc_strategy_daily_loss_circuit_breaker(poc_data):
    strat = AnchoredPOCStrategy()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    strat._daily_losses[f"GBPUSD=X:{today}"] = 2
    res = await strat.analyze("GBPUSD=X", {'h1': poc_data}, [], {})
    assert res is None
    # Clear for other tests
    strat._daily_losses = {}

@pytest.mark.asyncio
async def test_poc_strategy_trending_blocked(poc_data):
    strat = AnchoredPOCStrategy()
    strat._daily_losses = {} # Reset
    with patch('strategies.anchored_poc_strategy.IndicatorCalculator.get_market_regime', return_value='TRENDING'):
        res = await strat.analyze("GBPUSD=X", {'h1': poc_data}, [], {})
        assert res is None

@pytest.mark.asyncio
async def test_poc_strategy_sell_signal(poc_data):
    strat = AnchoredPOCStrategy()
    strat._daily_losses = {} # Reset
    # Set POC at 1.1000
    # Entry at 1.1045 (deviation 0.0045 > 4 * 0.0010)
    poc_data.iloc[-1, poc_data.columns.get_loc('close')] = 1.1045
    poc_data.iloc[-1, poc_data.columns.get_loc('rsi')] = 75.0
    
    with patch('strategies.anchored_poc_strategy.IndicatorCalculator.get_market_regime', return_value='RANGING'), \
         patch('strategies.anchored_poc_strategy.RiskManager.calculate_lot_size', return_value={}):
        res = await strat.analyze("GBPUSD=X", {'h1': poc_data}, [], {})
        assert res is not None
        assert res['direction'] == "SELL"

@pytest.mark.asyncio
async def test_poc_strategy_buy_signal(poc_data):
    strat = AnchoredPOCStrategy()
    strat._daily_losses = {} # Reset
    # Entry at 1.0955 (deviation -0.0045 < -4 * 0.0010)
    poc_data.iloc[-1, poc_data.columns.get_loc('close')] = 1.0955
    poc_data.iloc[-1, poc_data.columns.get_loc('rsi')] = 25.0
    
    with patch('strategies.anchored_poc_strategy.IndicatorCalculator.get_market_regime', return_value='RANGING'), \
         patch('strategies.anchored_poc_strategy.RiskManager.calculate_lot_size', return_value={}):
        res = await strat.analyze("GBPUSD=X", {'h1': poc_data}, [], {})
        assert res is not None
        assert res['direction'] == "BUY"

@pytest.mark.asyncio
async def test_poc_strategy_rr_blocked(poc_data):
    strat = AnchoredPOCStrategy()
    strat._daily_losses = {} # Reset
    # Large ATR makes risk > reward gain
    poc_data.iloc[-1, poc_data.columns.get_loc('close')] = 1.1045
    poc_data.iloc[-1, poc_data.columns.get_loc('atr')] = 0.0100 
    poc_data.iloc[-1, poc_data.columns.get_loc('rsi')] = 75.0
    
    with patch('strategies.anchored_poc_strategy.IndicatorCalculator.get_market_regime', return_value='RANGING'):
        res = await strat.analyze("GBPUSD=X", {'h1': poc_data}, [], {})
        assert res is None

@pytest.mark.asyncio
async def test_poc_strategy_exception():
    strat = AnchoredPOCStrategy()
    res = await strat.analyze("GBPUSD=X", None, [], {})
    assert res is None
