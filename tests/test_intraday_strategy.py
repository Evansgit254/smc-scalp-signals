import pytest
import pandas as pd
from strategies.intraday_quant_strategy import IntradayQuantStrategy
from unittest.mock import patch, MagicMock

@pytest.mark.asyncio
async def test_intraday_strategy_id():
    strat = IntradayQuantStrategy()
    assert strat.get_id() == "intraday_quant_m5"
    assert "Intraday" in strat.get_name()

@pytest.mark.asyncio
async def test_intraday_strategy_sell_logic():
    strat = IntradayQuantStrategy()
    df = pd.DataFrame({
        'close': [100] * 100,
        'high': [101] * 100,
        'low': [99] * 100,
        'atr': [1.0] * 100,
    })
    data = {'m5': df}
    # Mock SessionFilter and AlphaCombiner to return a strong SELL signal
    with patch('strategies.intraday_quant_strategy.SessionFilter.is_peak_session', return_value=True), \
         patch('strategies.intraday_quant_strategy.MacroFilter.is_macro_safe', return_value=True), \
         patch('strategies.intraday_quant_strategy.AlphaCombiner.combine', return_value=-1.2), \
         patch('strategies.intraday_quant_strategy.AlphaCombiner.calculate_quality_score', return_value=9.0):
        res = await strat.analyze("EURUSD", data, [], {'regime': 'TRENDING'})
        assert res['direction'] == "SELL"
        assert res['sl'] > res['entry_price']

@pytest.mark.asyncio
async def test_intraday_strategy_filters():
    strat = IntradayQuantStrategy()
    df = pd.DataFrame({'close': [100]*100, 'atr': [1.0]*100})
    data = {'m5': df}
    
    # Test News Filter blocking
    with patch('strategies.intraday_quant_strategy.AlphaCombiner.combine', return_value=1.5), \
         patch('strategies.intraday_quant_strategy.AlphaCombiner.calculate_quality_score', return_value=9.0), \
         patch('strategies.intraday_quant_strategy.NewsFilter.is_safe_to_trade', return_value=False):
        res = await strat.analyze("EURUSD", data, ["News"], {})
        assert res is None

@pytest.mark.asyncio
async def test_intraday_strategy_exception():
    strat = IntradayQuantStrategy()
    # Trigger exception by passing None as data
    res = await strat.analyze("EURUSD", None, [], {})
    assert res is None
