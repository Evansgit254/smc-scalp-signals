import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from strategies.pre_news_quant_strategy import PreNewsQuantStrategy

@pytest.fixture
def sample_data_buy():
    # Rubber band stretched down
    dates = pd.date_range('2024-01-01', periods=30, freq='5min')
    df = pd.DataFrame({
        'open': np.linspace(1.1000, 1.1000, 30),
        'high': np.linspace(1.1000, 1.1000, 30),
        'low': np.linspace(1.1000, 1.1000, 30),
        'close': np.linspace(1.1000, 1.1000, 30),
        'atr': [0.0010] * 30,
        'zscore_20': [-2.5] * 30 # Stretched down
    }, index=dates)
    return {'m5': df}

@pytest.fixture
def sample_data_sell():
    # Rubber band stretched up
    dates = pd.date_range('2024-01-01', periods=30, freq='5min')
    df = pd.DataFrame({
        'open': np.linspace(1.1000, 1.1000, 30),
        'high': np.linspace(1.1000, 1.1000, 30),
        'low': np.linspace(1.1000, 1.1000, 30),
        'close': np.linspace(1.1000, 1.1000, 30),
        'atr': [0.0010] * 30,
        'zscore_20': [2.5] * 30 # Stretched up
    }, index=dates)
    return {'m5': df}

@pytest.fixture
def imminent_events():
    now = datetime.now(timezone.utc)
    event_time = now + timedelta(minutes=45) # 45 mins away
    return [
        {
            'title': 'FOMC Economic Projections',
            'impact': 'High',
            'country': 'USD',
            'date': event_time.strftime('%m-%d-%Y'),
            'time': event_time.strftime('%I:%M%p').lower()
        }
    ]

@pytest.fixture
def market_context():
    # DXY Context
    dates = pd.date_range('2024-01-01', periods=5, freq='1H')
    dxy_df = pd.DataFrame({
        'close': [104.5] * 5,
        'ema_20': [104.0] * 5 # Close > EMA -> BULLISH DXY
    }, index=dates)
    return {'DXY': dxy_df}


@pytest.mark.asyncio
async def test_pre_news_buy_signal(sample_data_buy, imminent_events):
    strategy = PreNewsQuantStrategy()
    event_time = datetime.now(timezone.utc) + timedelta(minutes=45)
    
    # Needs BEARISH DXY to trigger divergence bonus against a negative Z-Score
    dates = pd.date_range('2024-01-01', periods=5, freq='1H')
    dxy_df = pd.DataFrame({'close': [103.0] * 5, 'ema_20': [104.0] * 5}, index=dates)
    bearish_context = {'DXY': dxy_df}
    
    with patch('data.news_fetcher.NewsFetcher._get_relevant_currencies', return_value=['USD', 'EUR']), \
         patch('data.news_fetcher.NewsFetcher._parse_ff_time', return_value=event_time), \
         patch('indicators.calculations.IndicatorCalculator.get_market_regime', return_value='RANGING'):
         
        res = await strategy.analyze("EURUSD=X", sample_data_buy, imminent_events, bearish_context)
        
        assert res is not None
        assert res['direction'] == "BUY"
        assert res['timeframe'] == "M5"
        assert res['trade_type'] == "PRE_NEWS"
        assert res['tp1'] > res['entry_price']
        assert res['quality_score'] == 7.5

@pytest.mark.asyncio
async def test_pre_news_sell_signal(sample_data_sell, imminent_events, market_context):
    strategy = PreNewsQuantStrategy()
    event_time = datetime.now(timezone.utc) + timedelta(minutes=45)
    
    with patch('data.news_fetcher.NewsFetcher._get_relevant_currencies', return_value=['USD', 'EUR']), \
         patch('data.news_fetcher.NewsFetcher._parse_ff_time', return_value=event_time), \
         patch('indicators.calculations.IndicatorCalculator.get_market_regime', return_value='RANGING'):
         
        res = await strategy.analyze("EURUSD=X", sample_data_sell, imminent_events, market_context)
        
        assert res is not None
        assert res['direction'] == "SELL"
        # DXY is BULLISH, Z-score is POSITIVE => divergence bonus applies (+1.5)
        assert res['quality_score'] == 7.5

@pytest.mark.asyncio
async def test_pre_news_low_zscore(sample_data_buy, imminent_events):
    strategy = PreNewsQuantStrategy()
    
    # Modify z-score to be too weak (< 1.8)
    df = sample_data_buy['m5'].copy()
    df['zscore_20'] = -1.5 
    
    event_time = datetime.now(timezone.utc) + timedelta(minutes=45)
    
    with patch('data.news_fetcher.NewsFetcher._get_relevant_currencies', return_value=['USD', 'EUR']), \
         patch('data.news_fetcher.NewsFetcher._parse_ff_time', return_value=event_time):
         
        res = await strategy.analyze("EURUSD=X", {'m5': df}, imminent_events, {})
        assert res is None

@pytest.mark.asyncio
async def test_pre_news_choppy_regime(sample_data_buy, imminent_events):
    strategy = PreNewsQuantStrategy()
    event_time = datetime.now(timezone.utc) + timedelta(minutes=45)
    
    with patch('data.news_fetcher.NewsFetcher._get_relevant_currencies', return_value=['USD', 'EUR']), \
         patch('data.news_fetcher.NewsFetcher._parse_ff_time', return_value=event_time), \
         patch('indicators.calculations.IndicatorCalculator.get_market_regime', return_value='CHOPPY'):
         
        res = await strategy.analyze("EURUSD=X", sample_data_buy, imminent_events, {})
        assert res is None # Blocked by choppy regime

@pytest.mark.asyncio
async def test_pre_news_too_far_away(sample_data_sell, imminent_events):
    strategy = PreNewsQuantStrategy()
    # Event is 3 hours away (MAX_EVENT_MINUTES is 90)
    event_time = datetime.now(timezone.utc) + timedelta(minutes=180)
    
    with patch('data.news_fetcher.NewsFetcher._get_relevant_currencies', return_value=['USD', 'EUR']), \
         patch('data.news_fetcher.NewsFetcher._parse_ff_time', return_value=event_time):
         
        res = await strategy.analyze("EURUSD=X", sample_data_sell, imminent_events, {})
        assert res is None # Blocked because event is too far
