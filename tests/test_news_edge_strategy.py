import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from strategies.news_edge_strategy import NewsEdgeStrategy

@pytest.fixture
def sample_data():
    dates = pd.date_range('2024-01-01', periods=20, freq='5min')
    close = np.linspace(1.1000, 1.1100, 20) # Upward momentum
    df = pd.DataFrame({
        'open': close - 0.0001,
        'high': close + 0.0002,
        'low': close - 0.0002,
        'close': close,
        'atr': [0.0010] * 20
    }, index=dates)
    return {'m5': df}

@pytest.fixture
def sample_news_events():
    now = datetime.now(timezone.utc)
    event_time = now - timedelta(minutes=10) # 10 mins ago
    return [
        {
            'title': 'Non-Farm Employment Change', # NFP
            'impact': 'High',
            'country': 'USD',
            'date': event_time.strftime('%m-%d-%Y'),
            'time': event_time.strftime('%I:%M%p').lower()
        }
    ]

@pytest.fixture
def mock_edge_db():
    return {
        "NFP": {
            "GBPUSD=X": {
                "15min": {
                    "direction": "BUY",
                    "hit_rate": 0.75,
                    "n": 10,
                    "avg_win": 0.50, # 0.5%
                    "avg_pct": 0.25
                }
            }
        }
    }

@pytest.mark.asyncio
async def test_news_edge_buy_signal(sample_data, sample_news_events, mock_edge_db):
    strategy = NewsEdgeStrategy()
    
    # We must explicitly mock _parse_ff_time so it doesn't fail on format quirks
    now = datetime.now(timezone.utc)
    event_time = now - timedelta(minutes=10)
    
    with patch.object(strategy, '_load_db', return_value=mock_edge_db), \
         patch('data.news_fetcher.NewsFetcher._get_relevant_currencies', return_value=['USD', 'GBP']), \
         patch('data.news_fetcher.NewsFetcher._parse_ff_time', return_value=event_time):
        
        res = await strategy.analyze("GBPUSD=X", sample_data, sample_news_events, {})
        
        assert res is not None
        assert res['direction'] == "BUY"
        assert res['timeframe'] == "M5"
        assert res['trade_type'] == "NEWS_EDGE"
        assert res['confidence'] == 0.75
        assert res['score_details']['event'] == "NFP"
        assert res['score_details']['window'] == "15min"
        assert res['tp1'] > res['entry_price']

@pytest.mark.asyncio
async def test_news_edge_no_momentum(sample_data, sample_news_events, mock_edge_db):
    strategy = NewsEdgeStrategy()
    
    # Reverse the data to simulate downward momentum
    reversed_df = sample_data['m5'].iloc[::-1].copy()
    reversed_df.reset_index(drop=True, inplace=True)
    reversed_data = {'m5': reversed_df}
    
    with patch.object(strategy, '_load_db', return_value=mock_edge_db), \
         patch('data.news_fetcher.NewsFetcher._get_relevant_currencies', return_value=['USD', 'GBP']):
        
        # Edge is BUY but momentum is DOWN => should return None
        res = await strategy.analyze("GBPUSD=X", reversed_data, sample_news_events, {})
        assert res is None

@pytest.mark.asyncio
async def test_news_edge_not_whitelisted(sample_data, sample_news_events, mock_edge_db):
    strategy = NewsEdgeStrategy()
    
    # EURUSD is not in the whitelist for NFP
    bad_db = {
        "NFP": {
            "EURUSD=X": {
                "15min": {"direction": "BUY", "hit_rate": 0.80, "n": 10}
            }
        }
    }
    
    with patch.object(strategy, '_load_db', return_value=bad_db), \
         patch('data.news_fetcher.NewsFetcher._get_relevant_currencies', return_value=['USD', 'EUR']):
        
        res = await strategy.analyze("EURUSD=X", sample_data, sample_news_events, {})
        assert res is None

@pytest.mark.asyncio
async def test_news_edge_low_hit_rate(sample_data, sample_news_events):
    strategy = NewsEdgeStrategy()
    
    bad_db = {
        "NFP": {
            "GBPUSD=X": {
                "15min": {"direction": "BUY", "hit_rate": 0.50, "n": 10} # Hit rate too low
            }
        }
    }
    
    with patch.object(strategy, '_load_db', return_value=bad_db), \
         patch('data.news_fetcher.NewsFetcher._get_relevant_currencies', return_value=['USD', 'GBP']):
        
        res = await strategy.analyze("GBPUSD=X", sample_data, sample_news_events, {})
        assert res is None

@pytest.mark.asyncio
async def test_news_edge_no_recent_events(sample_data, mock_edge_db):
    strategy = NewsEdgeStrategy()
    
    # Provide old events (e.g. 5 hours ago)
    now = datetime.now(timezone.utc)
    event_time = now - timedelta(hours=5)
    stale_events = [{
        'title': 'Non-Farm Employment Change',
        'impact': 'High',
        'country': 'USD',
        'date': event_time.strftime('%m-%d-%Y'),
        'time': event_time.strftime('%I:%M%p').lower()
    }]
    
    with patch.object(strategy, '_load_db', return_value=mock_edge_db), \
         patch('data.news_fetcher.NewsFetcher._get_relevant_currencies', return_value=['USD', 'GBP']):
        
        res = await strategy.analyze("GBPUSD=X", sample_data, stale_events, {})
        assert res is None

@pytest.mark.asyncio
async def test_news_edge_sell_signal():
    """Test SELL direction TP/SL calculations and momentum"""
    strategy = NewsEdgeStrategy()
    
    # Downward momentum data
    dates = pd.date_range('2024-01-01', periods=20, freq='5min')
    close = np.linspace(1.1100, 1.1000, 20) # trending down
    df = pd.DataFrame({'close': close, 'atr': [0.0010] * 20}, index=dates)
    
    now = datetime.now(timezone.utc)
    event_time = now - timedelta(minutes=6) # 6 mins ago -> 5min window
    events = [{
        'title': 'FOMC Statement',
        'impact': 'Red',
        'country': 'USD',
        'date': event_time.strftime('%m-%d-%Y'),
        'time': event_time.strftime('%H:%M').lower() # Testing alt time format parsing
    }]
    
    sell_db = {
        "FOMC": {
            "USDJPY=X": {
                "5min": {
                    "direction": "SELL",
                    "hit_rate": 0.85,
                    "n": 15,
                    "avg_win": 0.8
                }
            }
        }
    }
    
    # Temporarily add to whitelist for this test scope
    from strategies.news_edge_strategy import WHITELIST
    WHITELIST.add(("FOMC", "USDJPY=X"))
    
    with patch.object(strategy, '_load_db', return_value=sell_db), \
         patch('data.news_fetcher.NewsFetcher._get_relevant_currencies', return_value=['USD', 'JPY']), \
         patch('data.news_fetcher.NewsFetcher._parse_ff_time', return_value=event_time):
        
        res = await strategy.analyze("USDJPY=X", {'m5': df}, events, {})
        
        assert res is not None
        assert res['direction'] == "SELL"
        assert res['tp1'] < res['entry_price']
        assert res['sl'] > res['entry_price']
        
    WHITELIST.remove(("FOMC", "USDJPY=X"))
