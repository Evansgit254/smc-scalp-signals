import pytest
import pandas as pd
from strategies.statistical_arbitrage_strategy import StatisticalArbitrageStrategy
from unittest.mock import patch

@pytest.fixture
def stat_data():
    dates = pd.date_range(end=pd.Timestamp.now(), periods=60, freq='h')
    df = pd.DataFrame({
        'close': [1.1000] * 60,
        'zscore_20': [0.0] * 60,
        'atr': [0.0010] * 60
    }, index=dates)
    return df

@pytest.mark.asyncio
async def test_stat_arb_id():
    strat = StatisticalArbitrageStrategy()
    assert strat.get_id() == "stat_arb_v1"

@pytest.mark.asyncio
async def test_stat_arb_no_dxy(stat_data):
    strat = StatisticalArbitrageStrategy()
    # Missing DXY in market_context
    res = await strat.analyze("EURUSD=X", {'h1': stat_data}, [], {})
    assert res is None

@pytest.mark.asyncio
async def test_stat_arb_insufficient_data():
    strat = StatisticalArbitrageStrategy()
    res = await strat.analyze("EURUSD=X", {'h1': pd.DataFrame()}, [], {})
    assert res is None

@pytest.mark.asyncio
async def test_stat_arb_trending(stat_data):
    strat = StatisticalArbitrageStrategy()
    context = {'DXY': stat_data}
    with patch('strategies.statistical_arbitrage_strategy.IndicatorCalculator.get_market_regime', return_value='TRENDING'):
        res = await strat.analyze("EURUSD=X", {'h1': stat_data}, [], context)
        assert res is None

@pytest.mark.asyncio
async def test_stat_arb_usd_quote_sell(stat_data):
    strat = StatisticalArbitrageStrategy()
    
    # Asset Z > 0 (EURUSD overbought), DXY Z > 2.2 (DXY overbought) -> Divergence (EURUSD should be oversold)
    stat_data.loc[stat_data.index[-2:], 'zscore_20'] = 1.0
    dxy_df = stat_data.copy()
    dxy_df.loc[dxy_df.index[-2:], 'zscore_20'] = 2.5
    
    with patch('strategies.statistical_arbitrage_strategy.IndicatorCalculator.get_market_regime', return_value='RANGING'), \
         patch('strategies.statistical_arbitrage_strategy.RiskManager.calculate_lot_size', return_value={}):
        res = await strat.analyze("EURUSD=X", {'h1': stat_data}, [], {'DXY': dxy_df})
        assert res is not None
        assert res['direction'] == "SELL"

@pytest.mark.asyncio
async def test_stat_arb_usd_quote_buy(stat_data):
    strat = StatisticalArbitrageStrategy()
    
    # Asset Z < 0, DXY Z < -2.2 -> Divergence
    stat_data.loc[stat_data.index[-2:], 'zscore_20'] = -1.0
    dxy_df = stat_data.copy()
    dxy_df.loc[dxy_df.index[-2:], 'zscore_20'] = -2.5
    
    with patch('strategies.statistical_arbitrage_strategy.IndicatorCalculator.get_market_regime', return_value='RANGING'), \
         patch('strategies.statistical_arbitrage_strategy.RiskManager.calculate_lot_size', return_value={}):
        res = await strat.analyze("EURUSD=X", {'h1': stat_data}, [], {'DXY': dxy_df})
        assert res is not None
        assert res['direction'] == "BUY"

@pytest.mark.asyncio
async def test_stat_arb_usd_base_buy(stat_data):
    strat = StatisticalArbitrageStrategy()
    
    # USDJPY moves WITH DXY. Divergence if USDJPY < 0 while DXY > 2.2
    stat_data.loc[stat_data.index[-2:], 'zscore_20'] = -1.0
    dxy_df = stat_data.copy()
    dxy_df.loc[dxy_df.index[-2:], 'zscore_20'] = 2.5
    
    with patch('strategies.statistical_arbitrage_strategy.IndicatorCalculator.get_market_regime', return_value='RANGING'), \
         patch('strategies.statistical_arbitrage_strategy.RiskManager.calculate_lot_size', return_value={}):
        res = await strat.analyze("USDJPY=X", {'h1': stat_data}, [], {'DXY': dxy_df})
        assert res is not None
        assert res['direction'] == "BUY"

@pytest.mark.asyncio
async def test_stat_arb_usd_base_sell(stat_data):
    strat = StatisticalArbitrageStrategy()
    
    # USDJPY > 0 while DXY < -2.2
    stat_data.loc[stat_data.index[-2:], 'zscore_20'] = 1.0
    dxy_df = stat_data.copy()
    dxy_df.loc[dxy_df.index[-2:], 'zscore_20'] = -2.5
    
    with patch('strategies.statistical_arbitrage_strategy.IndicatorCalculator.get_market_regime', return_value='RANGING'), \
         patch('strategies.statistical_arbitrage_strategy.RiskManager.calculate_lot_size', return_value={}):
        res = await strat.analyze("USDJPY=X", {'h1': stat_data}, [], {'DXY': dxy_df})
        assert res is not None
        assert res['direction'] == "SELL"

@pytest.mark.asyncio
async def test_stat_arb_no_direction(stat_data):
    strat = StatisticalArbitrageStrategy()
    dxy_df = stat_data.copy()
    with patch('strategies.statistical_arbitrage_strategy.IndicatorCalculator.get_market_regime', return_value='RANGING'):
        res = await strat.analyze("EURUSD=X", {'h1': stat_data}, [], {'DXY': dxy_df})
        assert res is None

@pytest.mark.asyncio
async def test_stat_arb_exception():
    strat = StatisticalArbitrageStrategy()
    res = await strat.analyze("EURUSD=X", None, [], {})
    assert res is None
