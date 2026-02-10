import requests
import pandas as pd
from datetime import datetime
from typing import List, Dict

class NewsFetcher:
    CALENDAR_URL = "https://nfs.forexfactory1.com/ff_calendar_thisweek.json"

    @staticmethod
    def fetch_news() -> List[Dict]:
        """
        Fetches the Forex Factory economic calendar for the current week.
        """
        try:
            response = requests.get(NewsFetcher.CALENDAR_URL, timeout=10)
            if response.status_code == 200:
                events = response.json()
                return events
            else:
                print(f"Failed to fetch news: {response.status_code}")
                return []
        except Exception:
            # Silent fail for news to avoid log spam, system will default to no-news safety
            return []

    @staticmethod
    def filter_relevant_news(events: List[Dict], symbols: List[str]) -> List[Dict]:
        """
        Filters events by relevant currencies (extracted from symbols).
        """
        relevant_currencies = set()
        for s in symbols:
            # EURUSD=X -> EUR, USD
            s_clean = s.replace('=X', '')
            if len(s_clean) == 6:
                relevant_currencies.add(s_clean[:3])
                relevant_currencies.add(s_clean[3:])
        
        filtered = []
        for event in events:
            if event.get('country') in relevant_currencies:
                filtered.append(event)
        return filtered
