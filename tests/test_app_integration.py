import pytest
import asyncio
from app.generate_signals import generate_signals
from app.diagnose_alpha import diagnose_alpha_levels
from unittest.mock import patch, MagicMock
import pandas as pd

@pytest.mark.asyncio
async def test_generate_signals_integration():
    # Mock the fetcher to avoid network calls
    mock_df = pd.DataFrame({
        'open': [1.0]*150, 'high': [1.1]*150, 'low': [0.9]*150, 'close': [1.0]*150
    }, index=pd.date_range('2024-01-01', periods=150, freq='5min'))
    
    with patch('data.fetcher.DataFetcher.fetch_data_async', return_value=mock_df), \
         patch('data.news_fetcher.NewsFetcher.fetch_news', return_value=[]), \
         patch('alerts.service.TelegramService.send_signal', return_value=True):
        
        # Test the main generation loop
        signals = await generate_signals()
        assert isinstance(signals, list)
        
def test_app_main_exceptions():
    # Test macro fetch failure
    with patch('data.fetcher.DataFetcher.fetch_data_async', side_effect=Exception("API Down")):
        try:
            asyncio.run(generate_signals())
        except Exception:
            pass

    # Test individual symbol processing failure
    mock_df = pd.DataFrame({'close': [1.0]*150}, index=pd.date_range('2024-01-01', periods=150, freq='5min'))
    with patch('data.fetcher.DataFetcher.fetch_data_async') as mock_fetch:
        # First 2 calls for macro (Success), 3rd for symbol (Fail)
        mock_fetch.side_effect = [mock_df, mock_df, Exception("Data Format Error")]
        try:
            asyncio.run(generate_signals())
        except Exception:
            pass
