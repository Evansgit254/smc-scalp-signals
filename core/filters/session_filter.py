from datetime import datetime, time
import pytz
from config.config import LONDON_OPEN, NY_OPEN, NY_CLOSE

class SessionFilter:
    @staticmethod
    def is_valid_session(check_time=None) -> bool:
        """
        Validates if the current time is within allowed sessions.
        London Open -> first 2 hours (08:00 - 10:00 UTC)
        London-New York overlap (13:00 - 16:00 UTC)
        """
        if check_time:
            # Handle datetime object or time object
            if hasattr(check_time, 'time'):
                now_utc = check_time.time()
            else:
                now_utc = check_time
        else:
            now_utc = datetime.now(pytz.UTC).time()
        
        # London Open: first 2 hours
        london_early = (now_utc >= time(LONDON_OPEN, 0)) and (now_utc <= time(LONDON_OPEN + 2, 0))
        
        # London-NY Overlap (Extended for V11.0 Option B)
        # 13:00 to 18:00 UTC (captures late NY moves)
        overlap = (now_utc >= time(NY_OPEN, 0)) and (now_utc <= time(NY_OPEN + 5, 0))
        
        return london_early or overlap

    @staticmethod
    def get_session_name() -> str:
        now_utc = datetime.now(pytz.UTC).time()
        if (now_utc >= time(LONDON_OPEN, 0)) and (now_utc <= time(LONDON_OPEN + 2, 0)):
            return "London Open"
        if (now_utc >= time(NY_OPEN, 0)) and (now_utc <= time(NY_OPEN + 5, 0)):
            return "London-NY Overlap (Extended)"
        return "Outside Session"
