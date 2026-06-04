#!/usr/bin/env python3
"""
Signal Tracker Service for TradingExpert.
Watches open signals and updates their result (TP/SL) based on real-time price data.
"""
import asyncio
import sqlite3
import yfinance as yf
import pandas as pd
from datetime import datetime
import os
import signal
import sys
import logging

# Suppress noisy yfinance warnings
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

DB_PATH = "database/signals.db"
TRACKING_INTERVAL = 120  # Check every 2 minutes

def _get_session():
    """Get a robust session for yfinance, matching data/fetcher.py approach."""
    try:
        from curl_cffi import requests as curl_requests
        return curl_requests.Session(impersonate="chrome")
    except ImportError:
        import requests
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        return session

# Reuse a single session across cycles
_session = _get_session()

def calculate_pips(symbol, entry, exit, direction):
    """V31.0: Precise institutional pip calculation."""
    try:
        # Check if JPY pair
        multiplier = 100 if "JPY" in symbol else 10000
        # Check if Gold/Oil/Crypto (usually 2-digits or 1-digit)
        if any(x in symbol for x in ["XAU", "GOLD", "GC=F", "XAG"]): multiplier = 10 
        if any(x in symbol for x in ["BTC", "ETH"]): multiplier = 1
        
        diff = (exit - entry) if direction == 'BUY' else (entry - exit)
        return round(diff * multiplier, 1)
    except:
        return 0.0

class SignalTracker:
    def __init__(self):
        self.running = True
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    def _shutdown(self, signum, frame):
        print("\n⏹️  Shutdown signal received. Stopping tracker...")
        self.running = False

    def get_db_connection(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _fetch_latest_price(self, symbol: str):
        """Fetch latest price using yf.download() with session (avoids cookie bug)."""
        try:
            df = yf.download(
                tickers=symbol,
                period="1d",
                interval="1m",
                session=_session,
                progress=False,
                auto_adjust=True,
                threads=False,
            )
            if df is None or df.empty:
                return None
            # Flatten MultiIndex columns if necessary
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            return float(df['Close'].iloc[-1])
        except Exception as e:
            print(f"⚠️ Error fetching price for {symbol}: {e}")
            return None

    async def track_once(self):
        """Perform one tracking cycle for all open signals."""
        conn = None
        try:
            conn = self.get_db_connection()
            # Find all open signals (exclude BLOCKED signals that were never executed)
            open_signals = conn.execute("""
                SELECT * FROM signals 
                WHERE result = 'OPEN' 
                  AND COALESCE(gate_status, 'PASSED') != 'BLOCKED'
            """).fetchall()
            
            if not open_signals:
                return

            # Group by symbol to minimize API calls
            symbols = list(set([s['symbol'] for s in open_signals]))
            
            # Fetch latest prices using robust yf.download() approach
            prices = {}
            for symbol in symbols:
                price = self._fetch_latest_price(symbol)
                if price is not None:
                    prices[symbol] = price

            for sig in open_signals:
                symbol = sig['symbol']
                if symbol not in prices:
                    continue

                current_price = prices[symbol]
                direction = sig['direction']
                entry = sig['entry_price']
                sl = sig['sl']
                tp0 = sig['tp0'] # TP1 (Secure)
                tp1 = sig['tp1'] # TP2 (Growth)
                tp2 = sig['tp2'] # TP3 (Runner)
                max_tp = sig['max_tp_reached'] or 0
                
                new_result = 'OPEN'
                new_max_tp = max_tp
                closed_at = None
                new_sl = sl

                if direction == 'BUY':
                    if current_price <= sl:
                        if max_tp >= 1 and sl >= entry:
                            # It was secured at breakeven, so it's a win (partial)
                            new_result = f'TP{max_tp}'
                        else:
                            new_result = 'SL'
                        closed_at = datetime.now().isoformat()
                    elif current_price >= tp2:
                        new_result = 'TP3'
                        new_max_tp = 3
                        closed_at = datetime.now().isoformat()
                    elif current_price >= tp1:
                        new_max_tp = max(new_max_tp, 2)
                        new_sl = max(sl, entry) # V25.0 Secure at TP1
                    elif current_price >= tp0:
                        new_max_tp = max(new_max_tp, 1)
                        new_sl = max(sl, entry) # V25.0 Secure at TP1
                else: # SELL
                    if current_price >= sl:
                        if max_tp >= 1 and sl <= entry:
                            # It was secured at breakeven, so it's a win (partial)
                            new_result = f'TP{max_tp}'
                        else:
                            new_result = 'SL'
                        closed_at = datetime.now().isoformat()
                    elif current_price <= tp2:
                        new_result = 'TP3'
                        new_max_tp = 3
                        closed_at = datetime.now().isoformat()
                    elif current_price <= tp1:
                        new_max_tp = max(new_max_tp, 2)
                        new_sl = min(sl, entry) # V25.0 Secure at TP1
                    elif current_price <= tp0:
                        new_max_tp = max(new_max_tp, 1)
                        new_sl = min(sl, entry) # V25.0 Secure at TP1

                if new_result != 'OPEN' or new_max_tp != max_tp or new_sl != sl:
                    if new_result != 'OPEN':
                        status_str = new_result
                    else:
                        status_str = f"OPEN (Hit TP{new_max_tp}, SL moved to {new_sl:.5f})"

                    # V31.0: Settlement Logic (Pips & Paper Account)
                    pips = 0.0
                    if new_result != 'OPEN':
                        pips = calculate_pips(symbol, entry, current_price, direction)
                        
                    print(f"🎯 UPDATING {symbol} {direction}: {status_str} at {current_price:.5f} ({pips} pips)")
                    
                    # Determine final status and outcome for closed trades
                    new_status = 'CLOSED' if new_result != 'OPEN' else None
                    outcome = None
                    if new_result != 'OPEN':
                        outcome = 'WIN' if new_result.startswith('TP') else 'LOSS'

                    conn.execute("""
                        UPDATE signals 
                        SET result = ?, max_tp_reached = ?, closed_at = ?, sl = ?, result_pips = ?,
                            result_price = CASE WHEN ? != 'OPEN' THEN ? ELSE result_price END,
                            status = CASE WHEN ? != 'OPEN' THEN 'CLOSED' ELSE status END,
                            outcome = CASE WHEN ? != 'OPEN' THEN ? ELSE outcome END
                        WHERE id = ?
                    """, (new_result, new_max_tp, closed_at, new_sl, pips,
                           new_result, current_price,
                           new_result,
                           new_result, outcome,
                           sig['id']))
                    
                    # If this was a paper trade closure, update paper balance
                    sig_dict = dict(sig)
                    if new_result != 'OPEN' and sig_dict.get('gate_status') == 'PASSED':
                        # Mapping pips to dollars (Simplified: $10 per pip for a standard lot)
                        import json
                        lot_size = 0.1 # Default mini-lot
                        try:
                            rd = json.loads(sig['risk_details'])
                            lot_size = rd.get('lot_size', 0.1)
                        except: pass
                        
                        dollar_gain = pips * (lot_size * 10)
                        conn.execute("UPDATE paper_account SET balance = balance + ?, equity = equity + ? WHERE id = 1", (dollar_gain, dollar_gain))
                        
                    conn.commit()

        except Exception as e:
            print(f"❌ Tracker cycle error: {e}")
        finally:
            if conn:
                conn.close()

    async def run(self):
        print("="*60)
        print("📊 SIGNAL TRACKER SERVICE STARTED")
        print("="*60)
        print(f"📡 Interval: {TRACKING_INTERVAL} seconds")
        print(f"🗄️ Database: {DB_PATH}")
        print("="*60)
        
        while self.running:
            start_time = datetime.now()
            await self.track_once()
            
            # Wait for next interval
            elapsed = (datetime.now() - start_time).total_seconds()
            sleep_time = max(1, TRACKING_INTERVAL - elapsed)
            await asyncio.sleep(sleep_time)

if __name__ == "__main__":
    tracker = SignalTracker()
    asyncio.run(tracker.run())
