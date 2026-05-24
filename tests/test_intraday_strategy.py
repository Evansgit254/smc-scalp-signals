import pytest
import pandas as pd
from strategies.quant_core_strategy import QuantCoreStrategy
from unittest.mock import patch

@pytest.mark.asyncio
async def test_quant_core_strategy_logic():
    """Verify core quant strategy decision logic."""
    strat = QuantCoreStrategy()
    assert "Alpha Core" in strat.get_name()
    
    # Create sample data
    df = pd.DataFrame({
        'close': [100.0] * 105,
        'high': [101.0] * 105,
        'low': [99.0] * 105,
        'atr': [1.0] * 105
    })
    data = {'m5': df}
    
    # Mocking Alpha Factors for a BUY signal
    # alpha_signal > 1.1 triggers BUY
    with patch('strategies.quant_core_strategy.AlphaCombiner.combine', return_value=1.5), \
         patch('strategies.quant_core_strategy.RiskManager.calculate_lot_size', return_value={'lot_size': 0.1, 'skip_trade': False}):
        
        res = await strat.analyze("EURUSD", data, [], {})
        assert res is not None
        assert res['direction'] == "BUY"
        assert res['entry_price'] == 100.0

@pytest.mark.asyncio
async def test_quant_core_strategy_sell():
    """Verify core quant strategy SELL logic."""
    strat = QuantCoreStrategy()
    df = pd.DataFrame({'close': [100.0]*105, 'atr': [1.0]*105})
    data = {'m5': df}
    
    # alpha_signal < -1.1 triggers SELL
    with patch('strategies.quant_core_strategy.AlphaCombiner.combine', return_value=-1.5), \
         patch('strategies.quant_core_strategy.RiskManager.calculate_lot_size', return_value={'lot_size': 0.1, 'skip_trade': False}):
        
        res = await strat.analyze("EURUSD", data, [], {})
        assert res is not None
        assert res['direction'] == "SELL"
        assert res['sl'] > 100.0
