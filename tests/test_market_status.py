import unittest
from datetime import datetime, time
from unittest.mock import patch, MagicMock
import pytz
from core.market_status import MarketStatus

class TestMarketStatus(unittest.TestCase):
    
    def setUp(self):
        self.ny_tz = pytz.timezone('America/New_York')

    @patch('core.market_status.datetime')
    def test_crypto_always_open(self, mock_datetime):
        # Even during a weekend, crypto should be open
        mock_now = datetime(2023, 10, 7, 12, 0, 0, tzinfo=self.ny_tz) # Saturday
        mock_datetime.now.return_value = mock_now
        
        self.assertTrue(MarketStatus.is_market_open("BTC-USD"))
        self.assertTrue(MarketStatus.is_market_open("ETH-USD"))

    @patch('core.market_status.datetime')
    def test_forex_closed_weekend(self, mock_datetime):
        # Saturday - Closed
        mock_now = datetime(2023, 10, 7, 12, 0, 0, tzinfo=self.ny_tz) 
        mock_datetime.now.return_value = mock_now
        self.assertFalse(MarketStatus.is_market_open("EURUSD=X"))

        # Friday 17:00:01 NY - Closed
        mock_now = datetime(2023, 10, 6, 17, 0, 1, tzinfo=self.ny_tz) # Friday
        mock_datetime.now.return_value = mock_now
        self.assertFalse(MarketStatus.is_market_open("GBPUSD=X"))
        
        # Sunday 16:59:59 NY - Closed
        mock_now = datetime(2023, 10, 8, 16, 59, 59, tzinfo=self.ny_tz) # Sunday
        mock_datetime.now.return_value = mock_now
        self.assertFalse(MarketStatus.is_market_open("USDJPY=X"))

    @patch('core.market_status.datetime')
    def test_forex_open_weekdays(self, mock_datetime):
        # Wednesday 10:00 NY - Open
        mock_now = datetime(2023, 10, 4, 10, 0, 0, tzinfo=self.ny_tz)
        mock_datetime.now.return_value = mock_now
        self.assertTrue(MarketStatus.is_market_open("EURUSD=X"))
        
        # Sunday 17:01 NY - Open
        mock_now = datetime(2023, 10, 8, 17, 1, 0, tzinfo=self.ny_tz)
        mock_datetime.now.return_value = mock_now
        self.assertTrue(MarketStatus.is_market_open("EURUSD=X"))

    @patch('core.market_status.datetime')
    def test_commodity_daily_break(self, mock_datetime):
        # Gold on Tuesday 17:30 NY - Closed (Daily Break)
        mock_now = datetime(2023, 10, 3, 17, 30, 0, tzinfo=self.ny_tz)
        mock_datetime.now.return_value = mock_now
        
        # Only commodities should be closed here
        self.assertFalse(MarketStatus.is_market_open("GC=F"))
        self.assertFalse(MarketStatus.is_market_open("CL=F"))
        
        # Forex technically trades but might be illiquid - logic says open though for simplicity unless we add strict liquidity hours
        self.assertTrue(MarketStatus.is_market_open("EURUSD=X"))

    @patch('core.market_status.datetime')
    def test_commodity_open_hours(self, mock_datetime):
        # Gold on Tuesday 14:00 NY - Open
        mock_now = datetime(2023, 10, 3, 14, 0, 0, tzinfo=self.ny_tz)
        mock_datetime.now.return_value = mock_now
        self.assertTrue(MarketStatus.is_market_open("GC=F"))

if __name__ == '__main__':
    unittest.main()
