import requests
import pandas as pd
from datetime import datetime, timezone
from typing import List, Dict, Optional
from config.config import NEWS_WASH_ZONE, NEWS_IMPACT_LEVELS

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
                return []
        except Exception:
            # Silent fail — system defaults to no-news safety (allow all trades)
            return []

    @staticmethod
    def get_upcoming_events() -> List[Dict]:
        """Alias used by generate_signals.py to get all this-week events."""
        return NewsFetcher.fetch_news()

    @staticmethod
    def filter_relevant_news(events: List[Dict], symbols: List[str]) -> List[Dict]:
        """
        Filters events by relevant currencies (extracted from symbols).
        """
        relevant_currencies = set()
        for s in symbols:
            s_clean = s.replace('=X', '')
            if len(s_clean) == 6:
                relevant_currencies.add(s_clean[:3])
                relevant_currencies.add(s_clean[3:])
        
        filtered = []
        for event in events:
            if event.get('country') in relevant_currencies:
                filtered.append(event)
        return filtered

    @staticmethod
    def is_high_impact_imminent(
        check_hour_utc: int,
        news_events: List[Dict],
        symbol: str,
        wash_minutes: int = NEWS_WASH_ZONE
    ) -> bool:
        """
        V26.2: Returns True if a high-impact news event is scheduled within
        ±wash_minutes of check_hour_utc for the currencies related to symbol.
        
        This is the primary guard against SESSION_CLOCK firing into NFP/CPI/FOMC.
        
        Args:
            check_hour_utc:  The UTC hour the strategy wants to trade (e.g. 8, 13, 16)
            news_events:     The raw Forex Factory event list
            symbol:          Trading symbol, e.g. "EURUSD=X", "GC=F", "BTC-USD"
            wash_minutes:    Minutes buffer around each event (default: 30min from config)
        
        Returns:
            True = news imminent, BLOCK the trade
            False = safe to trade
        """
        if not news_events:
            return False  # No data = assume safe (fail-open)

        # Determine which currencies are relevant for this symbol 
        relevant_currencies = NewsFetcher._get_relevant_currencies(symbol)
        if not relevant_currencies:
            return False  # No known currencies → don't block

        now_utc = datetime.now(timezone.utc)

        for event in news_events:
            # Only block "High" impact events
            impact = event.get('impact', '').lower()
            if impact not in ('high', 'red'):
                continue

            # Only block if this event's currency is relevant to our symbol
            event_currency = event.get('country', '').upper()
            if event_currency not in relevant_currencies:
                continue

            # Parse the event time — Forex Factory timestamps are in EST
            event_time = NewsFetcher._parse_ff_time(event, now_utc)
            if event_time is None:
                continue

            # Convert event time to UTC hour
            event_hour_utc = event_time.astimezone(timezone.utc).hour
            event_minute_utc = event_time.astimezone(timezone.utc).minute

            # Check if the event's UTC hour is within the wash zone of our check_hour
            # We compare in minutes from midnight UTC
            check_minute_of_day = check_hour_utc * 60
            event_minute_of_day = event_hour_utc * 60 + event_minute_utc

            if abs(check_minute_of_day - event_minute_of_day) <= wash_minutes:
                return True  # BLOCK: High-impact event too close

        return False

    @staticmethod
    def _get_relevant_currencies(symbol: str) -> set:
        """Maps a trading symbol to its relevant currency codes."""
        symbol_map = {
            "EURUSD=X": {"EUR", "USD"},
            "GBPUSD=X": {"GBP", "USD"},
            "AUDUSD=X": {"AUD", "USD"},
            "NZDUSD=X": {"NZD", "USD"},
            "USDJPY=X": {"USD", "JPY"},
            "GBPJPY=X": {"GBP", "JPY"},
            "GC=F":     {"USD"},  # Gold is driven by USD/Fed events
            "CL=F":     {"USD"},  # Oil is driven by USD/EIA
            "BTC-USD":  {"USD"},  # BTC correlates with macro USD events
        }
        return symbol_map.get(symbol, set())

    @staticmethod
    def _parse_ff_time(event: Dict, reference_date: datetime) -> Optional[datetime]:
        """
        Attempts to parse a Forex Factory event time (various formats).
        Returns a timezone-aware datetime or None if unparseable.
        """
        try:
            # FF uses formats like "8:30am" or "All Day"
            time_str = event.get('time', '').strip()
            date_str = event.get('date', '').strip()

            if not time_str or time_str.lower() in ('all day', 'tentative', ''):
                return None

            from datetime import timedelta
            from zoneinfo import ZoneInfo
            try:
                est = ZoneInfo('US/Eastern')
            except Exception:
                # Fallback to UTC offset if tzdata is missing entirely
                est = timezone(timedelta(hours=-4))
            
            # Combine date and time
            # Try MM-DD-YYYY first (common in some JSON feeds)
            combined_mdy = f"{date_str} {time_str}"
            
            # Try Month DD YYYY (common in other feeds)
            year = reference_date.year
            combined_bdy = f"{date_str} {year} {time_str}"
            
            formats_to_try = [
                (combined_mdy, '%m-%d-%Y %I:%M%p'),
                (combined_mdy, '%m-%d-%Y %I%p'),
                (combined_bdy, '%b %d %Y %I:%M%p'),
                (combined_bdy, '%b %d %Y %I%p'),
            ]
            
            for time_string, fmt in formats_to_try:
                try:
                    naive_dt = datetime.strptime(time_string, fmt)
                    aware_dt = naive_dt.replace(tzinfo=est)
                    return aware_dt
                except ValueError:
                    continue

            return None
        except Exception:
            return None
