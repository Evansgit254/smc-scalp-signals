import pytest
import pandas as pd
import asyncio
from data.fetcher import DataFetcher
from unittest.mock import MagicMock, patch, AsyncMock

from config.config import SYMBOLS, NARRATIVE_TF, STRUCTURE_TF, ENTRY_TF

@pytest.fixture
def mock_ticker():
    with patch('yfinance.Ticker') as mock:
        ticker_inst = MagicMock()
        mock.return_value = ticker_inst
        yield ticker_inst

def test_fetch_data_success(mock_ticker):
    # Mock successful history fetch
    index = pd.date_range(end=pd.Timestamp.now(tz="UTC"), periods=2, freq="15min")
    df = pd.DataFrame({
        'Open': [1, 2], 'High': [2, 3], 'Low': [0, 1], 'Close': [1, 2], 'Volume': [100, 200]
    }, index=index)
    with patch('yfinance.download', return_value=df):
        res = DataFetcher.fetch_data("EURUSD=X", "15m")
        assert res is not None
        assert not res.empty
        assert 'close' in res.columns

def test_fetch_range_success(mock_ticker):
    index = pd.date_range(end=pd.Timestamp.now(tz="UTC"), periods=2, freq="15min")
    df = pd.DataFrame({
        'Open': [1, 2], 'High': [2, 3], 'Low': [0, 1], 'Close': [1, 2], 'Volume': [100, 200]
    }, index=index)
    with patch('yfinance.download', return_value=df):
        res = DataFetcher.fetch_range("EURUSD=X", "15m", "2026-01-01", "2026-01-02")
        assert res is not None
        assert 'close' in res.columns

def test_fetch_range_failure(mock_ticker):
    with patch('yfinance.download', return_value=pd.DataFrame()):
        res = DataFetcher.fetch_range("EURUSD=X", "15m", "2026-01-01", "2026-01-02")
        assert res is None
    
    # Exception
    with patch('yfinance.download', side_effect=Exception("error")):
        res = DataFetcher.fetch_range("EURUSD=X", "15m", "2026-01-01", "2026-01-02")
        assert res is None

def test_fetch_data_failure(mock_ticker):
    # Mock empty response
    with patch('yfinance.download', return_value=pd.DataFrame()):
        res = DataFetcher.fetch_data("EURUSD=X", "15m")
        assert res is None

def test_fetch_data_exception(mock_ticker):
    # Mock exception
    with patch('yfinance.download', side_effect=Exception("API Error")):
        res = DataFetcher.fetch_data("EURUSD=X", "15m")
        assert res is None

@pytest.mark.asyncio
async def test_fetch_data_async():
    # Test the async wrapper
    with patch('data.fetcher.DataFetcher.fetch_data', return_value=pd.DataFrame({'a': [1]})) as mock_sync:
        res = await DataFetcher.fetch_data_async("EURUSD=X", "1h")
        assert not res.empty
        mock_sync.assert_called_once()

@pytest.mark.asyncio
async def test_get_latest_data_async():
    # Mock fetch_data_async to return controlled values
    async def mock_fetch(symbol, tf, period="5d"):
        # Convert legacy 'm' suffix to 'min' for Pandas compatibility
        freq = tf.replace('m', 'min') if tf.endswith('m') and not tf.endswith('min') else tf
        index = pd.date_range(end=pd.Timestamp.now(tz="UTC"), periods=100, freq=freq)
        return pd.DataFrame({
            'close': [1.1]*100, 'volume': [1000]*100, 'high': [1.2]*100, 'low': [1.0]*100, 'open': [1.1]*100
        }, index=index)

    with patch('data.fetcher.DataFetcher.fetch_data_async', side_effect=mock_fetch):
        # We need to ensure DXY is also mocked
        results = await DataFetcher.get_latest_data(symbols=["EURUSD=X"])
        
        assert 'DXY' in results
        assert 'EURUSD=X' in results
        assert 'h1' in results['EURUSD=X']
        assert 'm15' in results['EURUSD=X']
        assert 'm5' in results['EURUSD=X']

@pytest.mark.asyncio
async def test_get_latest_data_missing_timeframes():
    # Mock fetch to return None for some calls
    async def mock_fetch_partial(symbol, tf, period="5d"):
        # Match against ENTRY_TF from config
        if symbol == 'EURUSD=X' and tf == ENTRY_TF:
            return None
        # Convert legacy 'm' suffix to 'min' for Pandas compatibility
        freq = tf.replace('m', 'min') if tf.endswith('m') and not tf.endswith('min') else tf
        index = pd.date_range(end=pd.Timestamp.now(tz="UTC"), periods=10, freq=freq)
        return pd.DataFrame({
            'close': [1.1]*10, 'volume': [1000]*10, 'high': [1.2]*10, 'low': [1.0]*10, 'open': [1.1]*10
        }, index=index)

    with patch('data.fetcher.DataFetcher.fetch_data_async', side_effect=mock_fetch_partial):
        results = await DataFetcher.get_latest_data(symbols=["EURUSD=X"])
        # Should NOT include EURUSD=X because ENTRY_TF is missing
        assert 'EURUSD=X' not in results
        assert 'DXY' in results
