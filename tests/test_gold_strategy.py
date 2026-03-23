import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from unittest.mock import patch

from strategies.gold_quant_strategy import GoldQuantStrategy

@pytest.fixture
def sample_data():
    dates = pd.date_range('2024-01-01', periods=120, freq='5min')
    df = pd.DataFrame({
        'open': np.linspace(2000.0, 2010.0, 120),
        'high': np.linspace(2000.0, 2010.0, 120) + 1.0,
        'low': np.linspace(2000.0, 2010.0, 120) - 1.0,
        'close': np.linspace(2000.0, 2010.0, 120),
        'atr': [2.0] * 120
    }, index=dates)
    return {'m5': df}

@pytest.fixture
def market_context_dxy_bullish():
    dates = pd.date_range('2024-01-01', periods=5, freq='1H')
    df = pd.DataFrame({
        'ema_fast': [105.0] * 5,
        'ema_slow': [104.0] * 5 # Fast > Slow = Bullish DXY
    }, index=dates)
    return {'DXY': df}

@pytest.fixture
def market_context_dxy_bearish():
    dates = pd.date_range('2024-01-01', periods=5, freq='1H')
    df = pd.DataFrame({
        'ema_fast': [103.0] * 5,
        'ema_slow': [104.0] * 5 # Fast < Slow = Bearish DXY
    }, index=dates)
    return {'DXY': df}

@pytest.mark.asyncio
async def test_gold_wrong_symbol(sample_data):
    strategy = GoldQuantStrategy()
    res = await strategy.analyze("EURUSD=X", sample_data, [], {})
    assert res is None

@pytest.mark.asyncio
async def test_gold_buy_signal_clean(sample_data):
    strategy = GoldQuantStrategy()
    
    with patch('core.filters.session_filter.SessionFilter.is_peak_session', return_value=True), \
         patch('indicators.calculations.IndicatorCalculator.get_market_regime', return_value='TRENDING'), \
         patch('core.alpha_combiner.AlphaCombiner.combine', return_value=0.50), \
         patch('core.alpha_combiner.AlphaCombiner.calculate_quality_score', return_value=8.0), \
         patch('core.filters.risk_manager.RiskManager.calculate_optimal_rr', return_value={'is_friction_heavy': False}):
         
        # DXY is empty, no penalty
        res = await strategy.analyze("GC=F", sample_data, [], {})
        
        assert res is not None
        assert res['direction'] == "BUY"
        assert res['timeframe'] == "M5"
        assert res['trade_type'] == "ADVANCED_PATTERN" # Gold maps to this internally
        assert res['quality_score'] == 8.0
        # TP0 = entry + 1 ATR (atr is 2.0)
        assert res['tp0'] == res['entry_price'] + 2.0

@pytest.mark.asyncio
async def test_gold_sell_signal_clean(sample_data):
    strategy = GoldQuantStrategy()
    
    with patch('core.filters.session_filter.SessionFilter.is_peak_session', return_value=True), \
         patch('indicators.calculations.IndicatorCalculator.get_market_regime', return_value='TRENDING'), \
         patch('core.alpha_combiner.AlphaCombiner.combine', return_value=-0.50), \
         patch('core.alpha_combiner.AlphaCombiner.calculate_quality_score', return_value=8.0), \
         patch('core.filters.risk_manager.RiskManager.calculate_optimal_rr', return_value={'is_friction_heavy': False}):
         
        res = await strategy.analyze("GC=F", sample_data, [], {})
        
        assert res is not None
        assert res['direction'] == "SELL"
        # TP0 = entry - 1 ATR
        assert res['tp0'] == res['entry_price'] - 2.0

@pytest.mark.asyncio
async def test_gold_buy_dxy_penalty_survives(sample_data, market_context_dxy_bullish):
    strategy = GoldQuantStrategy()
    # DXY Bullish + Gold Buy = Penalty of 1.5
    # If initial score is 8.0, after penalty it is 6.5, which is >= 5.0 (passes)
    # Wait: The code says: `if quality_score < 8.0:` the penalty applies. 
    # If it is 8.0 exactly, the penalty does NOT apply! Let's use 7.5.
    
    with patch('core.filters.session_filter.SessionFilter.is_peak_session', return_value=True), \
         patch('indicators.calculations.IndicatorCalculator.get_market_regime', return_value='TRENDING'), \
         patch('core.alpha_combiner.AlphaCombiner.combine', return_value=0.50), \
         patch('core.alpha_combiner.AlphaCombiner.calculate_quality_score', return_value=7.5), \
         patch('core.filters.risk_manager.RiskManager.calculate_optimal_rr', return_value={'is_friction_heavy': False}):
         
        res = await strategy.analyze("GC=F", sample_data, [], market_context_dxy_bullish)
        
        assert res is not None
        assert res['direction'] == "BUY"
        assert res['quality_score'] == 6.0 # 7.5 - 1.5 penalty

@pytest.mark.asyncio
async def test_gold_buy_dxy_penalty_rejects(sample_data, market_context_dxy_bullish):
    strategy = GoldQuantStrategy()
    # DXY Bullish + Gold Buy = Penalty of 1.5
    # Initial score 6.0. After penalty it's 4.5. 4.5 < 5.0 -> Reject
    
    with patch('core.filters.session_filter.SessionFilter.is_peak_session', return_value=True), \
         patch('indicators.calculations.IndicatorCalculator.get_market_regime', return_value='TRENDING'), \
         patch('core.alpha_combiner.AlphaCombiner.combine', return_value=0.50), \
         patch('core.alpha_combiner.AlphaCombiner.calculate_quality_score', return_value=6.0), \
         patch('core.filters.risk_manager.RiskManager.calculate_optimal_rr', return_value={'is_friction_heavy': False}):
         
        res = await strategy.analyze("GC=F", sample_data, [], market_context_dxy_bullish)
        assert res is None

@pytest.mark.asyncio
async def test_gold_sell_dxy_penalty_survives(sample_data, market_context_dxy_bearish):
    strategy = GoldQuantStrategy()
    # DXY Bearish + Gold Sell = Penalty of 1.5
    
    with patch('core.filters.session_filter.SessionFilter.is_peak_session', return_value=True), \
         patch('indicators.calculations.IndicatorCalculator.get_market_regime', return_value='TRENDING'), \
         patch('core.alpha_combiner.AlphaCombiner.combine', return_value=-0.50), \
         patch('core.alpha_combiner.AlphaCombiner.calculate_quality_score', return_value=7.0), \
         patch('core.filters.risk_manager.RiskManager.calculate_optimal_rr', return_value={'is_friction_heavy': False}):
         
        res = await strategy.analyze("GC=F", sample_data, [], market_context_dxy_bearish)
        
        assert res is not None
        assert res['direction'] == "SELL"
        assert res['quality_score'] == 5.5

@pytest.mark.asyncio
async def test_gold_choppy_regime(sample_data):
    strategy = GoldQuantStrategy()
    with patch('core.filters.session_filter.SessionFilter.is_peak_session', return_value=True), \
         patch('indicators.calculations.IndicatorCalculator.get_market_regime', return_value='CHOPPY'):
         
        res = await strategy.analyze("GC=F", sample_data, [], {})
        assert res is None

@pytest.mark.asyncio
async def test_gold_low_quality(sample_data):
    strategy = GoldQuantStrategy()
    with patch('core.filters.session_filter.SessionFilter.is_peak_session', return_value=True), \
         patch('indicators.calculations.IndicatorCalculator.get_market_regime', return_value='TRENDING'), \
         patch('core.alpha_combiner.AlphaCombiner.combine', return_value=0.50), \
         patch('core.alpha_combiner.AlphaCombiner.calculate_quality_score', return_value=4.0): # < 5.0
         
        res = await strategy.analyze("GC=F", sample_data, [], {})
        assert res is None
