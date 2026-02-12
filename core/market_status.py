from datetime import datetime, time, timezone
import pytz

class MarketStatus:
    """
    Utility to check if financial markets are open.
    Handles specific rules for:
    - Crypto: 24/7 (Always Open)
    - Forex: 24/5 (Closes weekends)
    - Commodities/Indices: 24/5 with daily maintenance breaks
    """

    # Timezone for market hours (New York is standard for Forex/Futures close)
    NY_TZ = pytz.timezone('America/New_York')

    @staticmethod
    def is_market_open(symbol: str) -> bool:
        """
        Determines if the market is open for a given symbol.
        """
        # 1. Crypto is always open
        if "BTC" in symbol or "ETH" in symbol or "-USD" in symbol:
            return True

        # Get current time in NY
        now_ny = datetime.now(MarketStatus.NY_TZ)
        weekday = now_ny.weekday() # 0=Mon, 4=Fri, 5=Sat, 6=Sun
        current_time = now_ny.time()

        # 2. Weekend Closure Rule (Forex & Commodities)
        # Market closes Friday 17:00 NY
        if weekday == 4 and current_time >= time(17, 0):
            return False
            
        # Market is closed all Saturday
        if weekday == 5: 
            return False

        # Market opens Sunday 17:00 NY
        if weekday == 6:
            if current_time < time(17, 0):
                return False
            else:
                return True # Open after Sunday 17:00 NY

        # 3. Daily Maintenance Break (Mon-Thu)
        # Futures (Gold, Oil, etc.) often break 17:00-18:00 NY
        # Forex is technically 24h during week, but liquidity is thin 17:00-17:05.
        # We will enforce a break 16:59 - 18:00 NY for Commodities to be safe.
        
        is_commodity = symbol in ["GC=F", "CL=F", "^TNX", "DX-Y.NYB"]
        
        if is_commodity:
            # Daily break 17:00 - 18:00 NY
            if current_time >= time(17, 0) and current_time < time(18, 0):
                return False

        return True

    @staticmethod
    def get_market_status_msg(symbol: str) -> str:
        """Returns a human-readable status message."""
        if MarketStatus.is_market_open(symbol):
            return "OPEN"
        else:
            return "CLOSED"
