from config.config import NEWS_WASH_ZONE, NEWS_IMPACT_LEVELS
from core.filters.news_sentiment import NewsSentimentAnalyzer
from datetime import datetime
import pytz
import logging
import pandas as pd

class NewsFilter:
    @staticmethod
    def get_upcoming_events(news_events: list, symbol: str) -> list:
        """
        Checks for upcoming or recent high-impact news events for a symbol.
        """
        if not news_events:
            return []

        now_utc = datetime.now(pytz.UTC)
        s_clean = symbol.replace('=X', '')
        currencies = [s_clean[:3], s_clean[3:]]
        
        active_events = []
        
        for event in news_events:
            if event.get('country') not in currencies:
                continue
                
            if event.get('impact') not in NEWS_IMPACT_LEVELS:
                continue

            # Event time format: "2026-01-04T12:00:00-05:00" or similar
            # FF JSON usually has "date": "2026-01-04T12:00:00-05:00"
            try:
                event_time = pd.to_datetime(event.get('date')).to_pydatetime()
                if event_time.tzinfo is None:
                    event_time = pytz.UTC.localize(event_time)
                else:
                    event_time = event_time.astimezone(pytz.UTC)
                
                # Check if within wash zone
                time_diff = abs((event_time - now_utc).total_seconds()) / 60
                
                if time_diff <= NEWS_WASH_ZONE:
                    bias = NewsSentimentAnalyzer.get_bias(event)
                    active_events.append({
                        'title': event.get('title'),
                        'impact': event.get('impact'),
                        'time': event_time,
                        'minutes_away': round((event_time - now_utc).total_seconds() / 60, 1),
                        'bias': bias
                    })
            except Exception as e:
                logging.error(f"Error parsing news tool time: {e}")
                continue
                
        return active_events

    @staticmethod
    def is_news_safe(news_events: list, symbol: str) -> bool:
        """
        Returns False if there is a high-impact event within the NEWS_WASH_ZONE.
        """
        upcoming = NewsFilter.get_upcoming_events(news_events, symbol)
        # Block only if impact is "High" for complete safety
        for event in upcoming:
            if event['impact'] == "High":
                return False
        return True
    
    @staticmethod
    def is_safe_to_trade(news_events: list, symbol: str) -> bool:
        """
        Alias for is_news_safe for consistency.
        """
        return NewsFilter.is_news_safe(news_events, symbol)