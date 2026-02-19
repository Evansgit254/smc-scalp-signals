from data.fetcher import DataFetcher
from datetime import datetime, timedelta
import pandas as pd

def debug_fetch():
    fetcher = DataFetcher()
    symbol = "EURUSD=X"
    timeframe = "1h"
    days = 60
    start_date = (datetime.now() - timedelta(days=days + 10)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    print(f"Fetching {symbol} {timeframe} with period {days+10}d...")
    df = fetcher.fetch_data(symbol, timeframe, period=f"{days+10}d")
    
    if df is not None and not df.empty:
        print(f"✅ Success! Loaded {len(df)} bars.")
        print(df.head())
    else:
        print("❌ Failed to load data.")

if __name__ == "__main__":
    debug_fetch()
