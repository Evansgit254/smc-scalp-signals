import pytest
import pandas as pd
from datetime import datetime, time
import pytz
from core.filters.session_filter import SessionFilter
from strategies.session_clock_strategy import SessionClockStrategy
from unittest.mock import patch, MagicMock

def test_peak_session_filter():
    # London Open (08:00 UTC) - Should be Peak
    london_time = datetime.combine(datetime.now().date(), time(8, 30), tzinfo=pytz.UTC)
    assert SessionFilter.is_peak_session(london_time) is True

    # London Mid-day (11:00 UTC) - Should NOT be Peak
    mid_day = datetime.combine(datetime.now().date(), time(11, 0), tzinfo=pytz.UTC)
    assert SessionFilter.is_peak_session(mid_day) is False

    # NY Open / Overlap (14:00 UTC) - Should be Peak
    ny_time = datetime.combine(datetime.now().date(), time(14, 0), tzinfo=pytz.UTC)
    assert SessionFilter.is_peak_session(ny_time) is True

    # Late NY (17:00 UTC) - Should NOT be Peak (window shortened to 16:00)
    late_ny = datetime.combine(datetime.now().date(), time(17, 0), tzinfo=pytz.UTC)
    assert SessionFilter.is_peak_session(late_ny) is False

@pytest.mark.asyncio
async def test_session_clock_strategy_id():
    strat = SessionClockStrategy()
    assert strat.get_id() == "session_clock_v1"
    assert "Session Clock" in strat.get_name()

@pytest.mark.asyncio
async def test_session_clock_oil_buy():
    strat = SessionClockStrategy()
    # 21:00 UTC is a BUY for OIL
    bt = datetime.combine(datetime.now().date(), time(21, 0), tzinfo=pytz.UTC)
    df = pd.DataFrame({
        'open': [100.0],
        'high': [101.0],
        'low': [99.5],
        'close': [100.5],
        'atr': [1.0]
    }, index=[bt])
    data = {'h1': df}
    
    res = await strat.analyze("CL=F", data, [], {})
    assert res is not None
    assert res['direction'] == "BUY"
    assert res['symbol'] == "CL=F"
    assert res['entry_price'] == 100.0

@pytest.mark.asyncio
async def test_session_clock_gold_buy():
    strat = SessionClockStrategy()
    # 16:00 UTC is a BUY for GOLD
    bt = datetime.combine(datetime.now().date(), time(16, 0), tzinfo=pytz.UTC)
    df = pd.DataFrame({
        'open': [2000.0],
        'high': [2010.0],
        'low': [1995.0],
        'close': [2005.0],
        'atr': [10.0]
    }, index=[bt])
    data = {'h1': df}
    
    # We should also mock RiskManager to avoid issues with environment variables
    with patch('strategies.session_clock_strategy.RiskManager.calculate_lot_size', return_value={'lots': 0.1}):
        res = await strat.analyze("GC=F", data, [], {})
        assert res is not None
        assert res['direction'] == "BUY"
        assert res['entry_price'] == 2000.0

@pytest.mark.asyncio
async def test_session_clock_friday_skip():
    strat = SessionClockStrategy()
    # A Friday at 21:00 UTC (2026-02-20 is a Friday)
    bt = datetime(2026, 2, 20, 21, 0, tzinfo=pytz.UTC)
    df = pd.DataFrame({
        'open': [100.0], 'high': [101.0], 'low': [99.0], 'close': [100.5], 'atr': [1.0]
    }, index=[bt])
    data = {'h1': df}
    
    res = await strat.analyze("CL=F", data, [], {})
    assert res is None # Friday should be skipped
