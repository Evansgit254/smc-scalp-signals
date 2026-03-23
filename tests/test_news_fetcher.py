import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from data.news_fetcher import NewsFetcher
import pytz

@pytest.fixture
def sample_events():
    return [
        {
            "title": "NFP",
            "impact": "High",
            "country": "USD",
            "date": "Mar 22",
            "time": "8:30am"
        },
        {
            "title": "Retail Sales",
            "impact": "Medium",
            "country": "USD",
            "date": "Mar 22",
            "time": "8:30am"
        },
        {
            "title": "ECB Press Conference",
            "impact": "Red",
            "country": "EUR",
            "date": "Mar 22",
            "time": "8:45am"
        },
        {
            "title": "Bank Holiday",
            "impact": "Low",
            "country": "GBP",
            "date": "Mar 22",
            "time": "All Day"
        }
    ]

def test_get_relevant_currencies():
    assert NewsFetcher._get_relevant_currencies("EURUSD=X") == {"EUR", "USD"}
    assert NewsFetcher._get_relevant_currencies("GBPJPY=X") == {"GBP", "JPY"}
    assert NewsFetcher._get_relevant_currencies("GC=F") == {"USD"}
    assert NewsFetcher._get_relevant_currencies("UNKNOWN") == set()

def test_parse_ff_time():
    # US Eastern Time is UTC-4 in summer, UTC-5 in winter. Let's provide a fixed reference.
    now = datetime(2024, 3, 22, 12, 0, 0, tzinfo=timezone.utc)
    
    # 1. Normal time (8:30am EST = 12:30 or 13:30 UTC depending on DST)
    event1 = {"date": "Mar 22", "time": "8:30am"}
    dt1 = NewsFetcher._parse_ff_time(event1, now)
    assert dt1 is not None
    assert dt1.year == 2024
    assert dt1.month == 3
    assert dt1.day == 22
    assert dt1.hour == 8
    assert dt1.minute == 30
    assert dt1.tzinfo is not None # US/Eastern timezone aware
    
    # 2. Time without minutes
    event2 = {"date": "Mar 22", "time": "2pm"}
    dt2 = NewsFetcher._parse_ff_time(event2, now)
    assert dt2 is not None
    assert dt2.hour == 14
    assert dt2.minute == 0
    
    # 3. All day event
    event3 = {"date": "Mar 22", "time": "All Day"}
    assert NewsFetcher._parse_ff_time(event3, now) is None
    
    # 4. Empty or missing
    assert NewsFetcher._parse_ff_time({}, now) is None
    
    # 5. Invalid format
    assert NewsFetcher._parse_ff_time({"date": "invalid", "time": "invalid"}, now) is None

def test_is_high_impact_imminent(sample_events):
    # Let's mock _parse_ff_time to return specific times we control
    now = datetime(2024, 3, 22, 12, 0, tzinfo=timezone.utc)
    
    # Let's say NFP (USD, High) is at 13:30 UTC.
    nfp_dt = datetime(2024, 3, 22, 13, 30, tzinfo=timezone.utc)
    
    # Let's say ECB (EUR, Red) is at 13:45 UTC.
    ecb_dt = datetime(2024, 3, 22, 13, 45, tzinfo=timezone.utc)
    
    def mock_parse(event, ref):
        if event.get('country') == "USD":
            return nfp_dt
        elif event.get('country') == "EUR":
            return ecb_dt
        return None
        
    with patch('data.news_fetcher.NewsFetcher._parse_ff_time', side_effect=mock_parse):
        # 1. Trading EURUSD at 13:00 UTC with 30min wash zone
        # NFP is at 13:30 (30 mins away) -> BLOCK!
        # ECB is at 13:45 (45 mins away) -> Safe, but NFP blocks it.
        assert NewsFetcher.is_high_impact_imminent(13, sample_events, "EURUSD=X", wash_minutes=30) == True
        
        # 2. Trading GBPJPY at 13:00 UTC
        # GBP and JPY have NO high impact events today. Safe! (Retail Sales is Medium, Holiday is Low/All Day)
        assert NewsFetcher.is_high_impact_imminent(13, sample_events, "GBPJPY=X", wash_minutes=30) == False
        
        # 3. Trading EURUSD at 12:00 UTC
        # NFP is at 13:30 (90 mins away)
        # ECB is at 13:45 (105 mins away)
        # Both outside wash_minutes=30. Safe!
        assert NewsFetcher.is_high_impact_imminent(12, sample_events, "EURUSD=X", wash_minutes=30) == False
        
        # 4. Trading EURUSD at 14:00 UTC (Post-news)
        # NFP was at 13:30 (-30 mins) -> BLOCK! (wash zone is bidirectional)
        assert NewsFetcher.is_high_impact_imminent(14, sample_events, "EURUSD=X", wash_minutes=30) == True

def test_fetch_news_success():
    with patch('requests.get') as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{"title": "Test"}]
        mock_get.return_value = mock_resp
        
        res = NewsFetcher.fetch_news()
        assert len(res) == 1
        assert res[0]["title"] == "Test"

def test_fetch_news_failure():
    with patch('requests.get') as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_get.return_value = mock_resp
        
        res = NewsFetcher.fetch_news()
        assert res == []
        
    with patch('requests.get', side_effect=Exception("Timeout")):
        res = NewsFetcher.fetch_news()
        assert res == []
