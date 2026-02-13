#!/usr/bin/env python3
"""
Signal Tracker Service for TradingExpert.
Watches open signals and updates their result (TP/SL) based on real-time price data.
"""
import asyncio
import sqlite3
import yfinance as yf
from datetime import datetime
import os
import signal
import sys

DB_PATH = "database/signals.db"
TRACKING_INTERVAL = 120  # Check every 2 minutes

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

    async def track_once(self):
        """Perform one tracking cycle for all open signals."""
        conn = None
        try:
            conn = self.get_db_connection()
            # Find all open signals
            open_signals = conn.execute("SELECT * FROM signals WHERE result = 'OPEN'").fetchall()
            
            if not open_signals:
                return

            # Group by symbol to minimize API calls
            symbols = list(set([s['symbol'] for s in open_signals]))
            
            # Fetch latest prices for all symbols in the list
            # Note: yf.download is faster for batches but can be noisy
            prices = {}
            for symbol in symbols:
                try:
                    ticker = yf.Ticker(symbol)
                    # Get 2 bars of 1m data to ensure we have the most recent closed/current price
                    hist = ticker.history(period="1d", interval="1m")
                    if not hist.empty:
                        prices[symbol] = hist['Close'].iloc[-1]
                except Exception as e:
                    print(f"⚠️ Error fetching price for {symbol}: {e}")

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

                if direction == 'BUY':
                    if current_price <= sl:
                        new_result = 'SL'
                        closed_at = datetime.now().isoformat()
                    elif current_price >= tp2:
                        new_result = 'TP3'
                        new_max_tp = 3
                        closed_at = datetime.now().isoformat()
                    elif current_price >= tp1:
                        new_max_tp = max(new_max_tp, 2)
                        # We don't close here, we wait for a terminal state (SL or Max TP)
                        # OR if the user wants partial close tracking, we could mark it.
                        # For now, let's keep it SIMPLE: result remains OPEN until SL or TP3.
                    elif current_price >= tp0:
                        new_max_tp = max(new_max_tp, 1)
                else: # SELL
                    if current_price >= sl:
                        new_result = 'SL'
                        closed_at = datetime.now().isoformat()
                    elif current_price <= tp2:
                        new_result = 'TP3'
                        new_max_tp = 3
                        closed_at = datetime.now().isoformat()
                    elif current_price <= tp1:
                        new_max_tp = max(new_max_tp, 2)
                    elif current_price <= tp0:
                        new_max_tp = max(new_max_tp, 1)

                if new_result != 'OPEN' or new_max_tp != max_tp:
                    print(f"🎯 UPDATING {symbol} {direction}: {new_result} (TP {new_max_tp}) at {current_price:.5f}")
                    conn.execute("""
                        UPDATE signals 
                        SET result = ?, max_tp_reached = ?, closed_at = ?
                        WHERE id = ?
                    """, (new_result, new_max_tp, closed_at, sig['id']))
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
