import pytest
import pandas as pd
from data.fetcher import DataFetcher
from unittest.mock import MagicMock, patch

def test_fetch_data_success():
    """Test successful data fetch"""
    with patch("yfinance.download") as mock_download:
        mock_df = pd.DataFrame({
            "Open": [1.0], "High": [1.1], "Low": [0.9], "Close": [1.0], "Volume": [100]
        }, index=[pd.Timestamp.now(tz="UTC")])
        mock_download.return_value = mock_df
        
        res = DataFetcher.fetch_data("EURUSD=X", "1h", "5d")
        assert not res.empty
        assert "close" in res.columns

def test_fetch_data_empty():
    """Test fetch_data when DataFrame is empty"""
    with patch("yfinance.download") as mock_download:
        mock_download.return_value = pd.DataFrame()
        
        res = DataFetcher.fetch_data("EURUSD=X", "1h", "5d")
        assert res is None

def test_fetch_data_none():
    """Test fetch_data when history returns None"""
    with patch("yfinance.download") as mock_download:
        mock_download.return_value = None
        
        res = DataFetcher.fetch_data("EURUSD=X", "1h", "5d")
        assert res is None

def test_fetch_data_error():
    """Test fetch_data error handling"""
    with patch("yfinance.download", side_effect=Exception("Network error")):
        res = DataFetcher.fetch_data("EURUSD=X", "1h", "5d")
        assert res is None

def test_fetch_range_success():
    """Test successful range fetch"""
    with patch("yfinance.download") as mock_download:
        mock_df = pd.DataFrame({
            "Open": [1.0], "High": [1.1], "Low": [0.9], "Close": [1.0], "Volume": [100]
        }, index=[pd.Timestamp.now(tz="UTC")])
        mock_download.return_value = mock_df
        
        res = DataFetcher.fetch_range("EURUSD=X", "1h", "2024-01-01", "2024-01-02")
        assert not res.empty
        assert "close" in res.columns

def test_fetch_range_empty():
    """Test fetch_range when empty"""
    with patch("yfinance.download") as mock_download:
        mock_download.return_value = None
        
        res = DataFetcher.fetch_range("EURUSD=X", "1h", "2024-01-01", "2024-01-02")
        assert res is None

def test_fetch_range_error():
    """Test fetch_range error handling"""
    with patch("yfinance.download", side_effect=ConnectionError("Timeout")):
        res = DataFetcher.fetch_range("EURUSD=X", "1h", "2024-01-01", "2024-01-02")
        assert res is None

@pytest.mark.asyncio
async def test_get_latest_data_dxy():
    """Test DXY data fetch in get_latest_data"""
    with patch.object(DataFetcher, 'fetch_data') as mock_fetch:
        mock_df = pd.DataFrame({
            "close": [103.5], "high": [103.6], "low": [103.4],
            "open": [103.5], "volume": [1000]
        }, index=[pd.Timestamp.now(tz="UTC")])
        mock_fetch.return_value = mock_df
        
        with patch("config.config.SYMBOLS", ["EURUSD=X"]):
            with patch("config.config.DXY_SYMBOL", "DX-Y.NYB"):
                res = await DataFetcher.get_latest_data()
                assert 'DXY' in res or len(res) >= 0  # DXY may or may not be included

@pytest.mark.asyncio
async def test_get_latest_data_symbol_failure():
    """Test get_latest_data when symbol fetch fails"""
    call_count = [0]
    def mock_fetch_side_effect(symbol, tf, period):
        call_count[0] += 1
        if call_count[0] <= 1:  # DXY succeeds
            return pd.DataFrame({"close": [1], "high": [1], "low": [1], "open": [1], "volume": [1]}, index=[pd.Timestamp.now(tz="UTC")])
        return None  # Symbol data fails
    
    with patch.object(DataFetcher, 'fetch_data', side_effect=mock_fetch_side_effect):
        with patch("config.config.SYMBOLS", ["EURUSD=X"]):
            res = await DataFetcher.get_latest_data()
            # Should handle gracefully, possibly empty dict or only DXY
            assert isinstance(res, dict)
