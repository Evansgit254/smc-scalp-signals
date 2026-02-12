import pytest
import pandas as pd
from strategies.quant_core_strategy import QuantCoreStrategy
from unittest.mock import patch

@pytest.mark.asyncio
async def test_quant_core_id():
    strat = QuantCoreStrategy()
    assert strat.get_id() == "alpha_core_v1"

@pytest.mark.asyncio
async def test_quant_core_risk_skip():
    strat = QuantCoreStrategy()
    df = pd.DataFrame({'close': [100]*100, 'atr': [1.0]*100})
    data = {'m5': df}
    
    with patch('strategies.quant_core_strategy.AlphaCombiner.combine', return_value=2.0), \
         patch('strategies.quant_core_strategy.RiskManager.calculate_lot_size', return_value={'skip_trade': True}):
        res = await strat.analyze("EURUSD", data, [], {})
        assert res is None

@pytest.mark.asyncio
async def test_quant_core_exception():
    strat = QuantCoreStrategy()
    res = await strat.analyze("EURUSD", {}, [], {})
    assert res is None
