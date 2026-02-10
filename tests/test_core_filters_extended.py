import pytest
import pandas as pd
from datetime import datetime, time
import pytz
from core.filters.session_filter import SessionFilter
from core.filters.daily_bias import DailyBias
from core.filters.volatility_filter import VolatilityFilter

def test_session_filter_logic():
    # Test London Open (08:30 UTC)
    london_time = datetime(2024, 1, 1, 8, 30, tzinfo=pytz.UTC)
    assert SessionFilter.is_valid_session(london_time) is True
    
    # Test NY Overlap (14:30 UTC)
    ny_time = datetime(2024, 1, 1, 14, 30, tzinfo=pytz.UTC)
    assert SessionFilter.is_valid_session(ny_time) is True
    
    # Test Outside Session (21:00 UTC)
    late_time = datetime(2024, 1, 1, 21, 0, tzinfo=pytz.UTC)
    assert SessionFilter.is_valid_session(late_time) is False
    
    # Test get_session_name (Internal mock since it uses datetime.now)
    # We can't easily mock datetime.now without library, but we covered branches in is_valid_session

def test_daily_bias_analysis():
    # Setup D1 dataframe
    df = pd.DataFrame({
        'open': [100]*60,
        'high': [110]*60,
        'low': [90]*60,
        'close': [105]*60
    })
    df['ema_20'] = 100
    
    # Bullish Bias
    res = DailyBias.analyze(df)
    assert res['bias'] == 'BULLISH'
    assert res['strength'] == 'WEAK'
    
    # Strong Bullish Expansion
    df.iloc[-1] = {'open': 100, 'high': 120, 'low': 98, 'close': 119}
    df['ema_20'] = 100
    res_strong = DailyBias.analyze(df)
    assert res_strong['strength'] == 'STRONG'

    # Bearish Bias
    df_bear = pd.DataFrame({
        'open': [100]*60, 'high': [110]*60, 'low': [90]*60, 'close': [95]*60
    })
    df_bear['ema_20'] = 100
    res_bear = DailyBias.analyze(df_bear)
    assert res_bear['bias'] == 'BEARISH'

    # Strong Bearish Expansion
    df_bear.iloc[-1] = {'open': 100, 'high': 102, 'low': 80, 'close': 81}
    df_bear['ema_20'] = 100
    res_bear_strong = DailyBias.analyze(df_bear)
    assert res_bear_strong['strength'] == 'STRONG'

    # Empty/Small Data
    assert DailyBias.analyze(pd.DataFrame())['bias'] == 'NEUTRAL'

def test_volatility_filter():
    df = pd.DataFrame({
        'atr': [1.5, 2.0],
        'atr_avg': [1.0, 1.0]
    })
    assert bool(VolatilityFilter.is_volatile(df)) is True
    assert VolatilityFilter.get_atr_status(df) == "Expanding"
    
    df_low = pd.DataFrame({
        'atr': [0.5, 0.5],
        'atr_avg': [1.0, 1.0]
    })
    assert bool(VolatilityFilter.is_volatile(df_low)) is False
    assert VolatilityFilter.get_atr_status(df_low) == "Compressed"
