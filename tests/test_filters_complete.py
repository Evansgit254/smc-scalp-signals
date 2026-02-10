import pytest
import pandas as pd
from datetime import datetime, time
import pytz
from core.filters.macro_filter import MacroFilter
from core.filters.news_filter import NewsFilter
from core.filters.news_sentiment import NewsSentimentAnalyzer
from unittest.mock import patch, MagicMock, PropertyMock

def test_macro_filter_logic():
    # Setup market context
    mock_dxy = pd.DataFrame({'close': [102.0], 'ema_20': [101.0]})
    mock_tnx = pd.DataFrame({'close': [4.5], 'ema_20': [4.4]})
    context = {'DXY': mock_dxy, '^TNX': mock_tnx}
    
    bias = MacroFilter.get_macro_bias(context)
    assert bias['DXY'] == 'BULLISH'
    assert bias['TNX'] == 'BULLISH'
    assert bias['RISK'] == 'OFF'
    
    # Check safety
    assert MacroFilter.is_macro_safe("GC=F", "BUY", bias) is False # Gold bearish if yields bullish
    assert MacroFilter.is_macro_safe("EURUSD=X", "BUY", bias) is False # EUR bullish if DXY bullish
    assert MacroFilter.is_macro_safe("^IXIC", "BUY", bias) is False # Risk OFF
    assert MacroFilter.is_macro_safe("AUDJPY=X", "BUY", bias) is True # Generic pair

def test_news_sentiment_analysis():
    # Test BULLISH_IF_HIGHER
    event_bull = {'title': 'US GDP q/q', 'forecast': '2.5%', 'previous': '2.0%'}
    assert NewsSentimentAnalyzer.get_bias(event_bull) == "BULLISH"
    
    event_bear = {'title': 'US GDP q/q', 'forecast': '1.5%', 'previous': '2.0%'}
    assert NewsSentimentAnalyzer.get_bias(event_bear) == "BEARISH"
    
    # Test BULLISH_IF_LOWER
    event_unemp = {'title': 'US Unemployment Rate', 'forecast': '3.5%', 'previous': '3.7%'}
    assert NewsSentimentAnalyzer.get_bias(event_unemp) == "BULLISH"

    # Test Neutral/Empty
    assert NewsSentimentAnalyzer.get_bias({}) == "NEUTRAL"
    assert NewsSentimentAnalyzer.get_bias({'title': 'GDP', 'forecast': '2%'}) == "NEUTRAL"
    
    # Test Exception path
    with patch('core.filters.news_sentiment.NewsSentimentAnalyzer.BULLISH_IF_HIGHER', new_callable=PropertyMock) as mock_list:
        mock_list.side_effect = Exception("Test")
        assert NewsSentimentAnalyzer.get_bias({'title': 'GDP', 'forecast': '2%', 'previous': '1%'}) == "NEUTRAL"

def test_news_filter_upcoming():
    news_events = [
        {'country': 'USD', 'impact': 'High', 'date': datetime.now(pytz.UTC).isoformat(), 'title': 'NFP'}
    ]
    upcoming = NewsFilter.get_upcoming_events(news_events, "EURUSD=X")
    assert len(upcoming) == 1
    assert NewsFilter.is_news_safe(news_events, "EURUSD=X") is False
    
    # Irrelevant country
    assert len(NewsFilter.get_upcoming_events(news_events, "GBPCHF=X")) == 0
