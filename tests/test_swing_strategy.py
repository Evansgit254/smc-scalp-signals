import pytest
import pandas as pd
from strategies.swing_quant_strategy import SwingQuantStrategy
from unittest.mock import patch

@pytest.mark.asyncio
async def test_swing_strategy_id():
    strat = SwingQuantStrategy()
    assert strat.get_id() == "swing_quant_h1"

@pytest.mark.asyncio
async def test_swing_strategy_logic_variation():
    strat = SwingQuantStrategy()
    df = pd.DataFrame({'close': [100]*200, 'high': [101]*200, 'low': [99]*200, 'atr': [1.0]*200})
    data = {'h1': df}
    
    # Test low quality skip
    with patch('strategies.swing_quant_strategy.AlphaCombiner.calculate_quality_score', return_value=1.0):
        res = await strat.analyze("EURUSD", data, [], {})
        assert res is None
        
    # Test SELL direction
    with patch('strategies.swing_quant_strategy.AlphaCombiner.combine', return_value=-1.5), \
         patch('strategies.swing_quant_strategy.AlphaCombiner.calculate_quality_score', return_value=5.0):
        res = await strat.analyze("EURUSD", data, [], {})
        assert res['direction'] == "SELL"
