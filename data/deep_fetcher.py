import asyncio
import pandas as pd
from datetime import datetime, timezone
import ccxt
try:
    from dukascopy_python import fetch as duka_fetch
except ImportError:
    duka_fetch = None

class DeepDataFetcher:
    @staticmethod
    async def fetch_range_async(symbol: str, timeframe: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Routes the fetch request based on the symbol.
        Timeframe expected: "5m", "15m", "1h", "1d"
        """
        # Convert yfinance format '5m' to minutes for crypto, and Dukascopy strings for forex
        if symbol == "BTC-USD":
            return await DeepDataFetcher._fetch_crypto_binance(symbol, timeframe, start_date, end_date)
        else:
            return await DeepDataFetcher._fetch_forex_dukascopy(symbol, timeframe, start_date, end_date)

    @staticmethod
    async def _fetch_crypto_binance(symbol: str, timeframe: str, start_date: str, end_date: str) -> pd.DataFrame:
        exchange = ccxt.binance({
            'enableRateLimit': True,
        })
        
        # ccxt format mapping
        tf_map = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "1d": "1d"}
        ccxt_tf = tf_map.get(timeframe, timeframe)
        
        since_dt = datetime.strptime(start_date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        since_ms = int(since_dt.timestamp() * 1000)
        
        end_dt = datetime.strptime(end_date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        end_ms = int(end_dt.timestamp() * 1000)
        
        all_ohlcv = []
        
        # Async wrapper to prevent blocking the event loop
        def fetch_sync():
            nonlocal since_ms, end_ms
            local_ohlcv = []
            while since_ms < end_ms:
                ohlcv = exchange.fetch_ohlcv('BTC/USDT', ccxt_tf, since=since_ms, limit=1000)
                if not len(ohlcv):
                    break
                
                # Filter out bars past end_ms
                ohlcv = [bar for bar in ohlcv if bar[0] <= end_ms]
                if not len(ohlcv):
                    break
                    
                local_ohlcv += ohlcv
                since_ms = ohlcv[-1][0] + 1  # Next bar
            return local_ohlcv

        # Run ccxt sync fetching in thread
        loop = asyncio.get_event_loop()
        all_ohlcv = await loop.run_in_executor(None, fetch_sync)
        
        if not all_ohlcv:
            return pd.DataFrame()
            
        df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        df.set_index('datetime', inplace=True)
        df.drop(columns=['timestamp'], inplace=True)
        return df

    @staticmethod
    async def _fetch_forex_dukascopy(symbol: str, timeframe: str, start_date: str, end_date: str) -> pd.DataFrame:
        # dukascopy_python is currently broken on PyPI for pagination.
        # Returning an empty DataFrame here correctly signals the Backtest Engine
        # to fallback to standard yfinance H1 representation for deep history.
        return pd.DataFrame()
