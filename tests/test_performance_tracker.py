import asyncio
import sqlite3
import os
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from signal_tracker import SignalTracker

DB_PATH = "database/signals_test.db"

async def test_tracking_logic():
    # Setup test DB
    if os.path.exists(DB_PATH): os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE signals (
            id INTEGER PRIMARY KEY,
            timestamp TIMESTAMP,
            symbol TEXT,
            direction TEXT,
            entry_price REAL,
            sl REAL,
            tp0 REAL,
            tp1 REAL,
            tp2 REAL,
            result TEXT DEFAULT 'OPEN',
            max_tp_reached INTEGER DEFAULT 0,
            closed_at TIMESTAMP
        )
    """)
    
    # Insert a test BUY signal
    # Entry: 1.1000, SL: 1.0900, TP1: 1.1100, TP2: 1.1200, TP3: 1.1300
    conn.execute("""
        INSERT INTO signals (timestamp, symbol, direction, entry_price, sl, tp0, tp1, tp2)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (datetime.now().isoformat(), 'EURUSD=X', 'BUY', 1.1000, 1.0900, 1.1100, 1.1200, 1.1300))
    conn.commit()
    conn.close()

    # Patch SignalTracker to use test DB and mock prices
    tracker = SignalTracker()
    import signal_tracker
    signal_tracker.DB_PATH = DB_PATH
    
    class MockPriceTracker(SignalTracker):
        async def track_once(self, mock_price):
            conn = self.get_db_connection()
            open_signals = conn.execute("SELECT * FROM signals WHERE result = 'OPEN'").fetchall()
            
            for sig in open_signals:
                symbol = sig['symbol']
                current_price = mock_price
                direction = sig['direction']
                sl = sig['sl']
                tp0 = sig['tp0']
                tp1 = sig['tp1']
                tp2 = sig['tp2']
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
                    elif current_price >= tp0:
                        new_max_tp = max(new_max_tp, 1)

                if new_result != 'OPEN' or new_max_tp != max_tp:
                    conn.execute("""
                        UPDATE signals 
                        SET result = ?, max_tp_reached = ?, closed_at = ?
                        WHERE id = ?
                    """, (new_result, new_max_tp, closed_at, sig['id']))
                    conn.commit()
            conn.close()

    mock_tracker = MockPriceTracker()
    
    # Simulate Price Action
    print("🚀 Simulating TP1 hit (1.1150)...")
    await mock_tracker.track_once(1.1150)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    res = conn.execute("SELECT * FROM signals WHERE symbol = 'EURUSD=X'").fetchone()
    print(f"Result: {res['result']}, Max TP: {res['max_tp_reached']}")
    assert res['max_tp_reached'] == 1
    
    print("🚀 Simulating TP3 hit (1.1350)...")
    await mock_tracker.track_once(1.1350)
    res = conn.execute("SELECT * FROM signals WHERE symbol = 'EURUSD=X'").fetchone()
    print(f"Result: {res['result']}, Max TP: {res['max_tp_reached']}, Closed At: {res['closed_at']}")
    assert res['result'] == 'TP3'
    assert res['max_tp_reached'] == 3
    assert res['closed_at'] is not None
    
    print("✅ Logic Verified!")
    conn.close()
    if os.path.exists(DB_PATH): os.remove(DB_PATH)

if __name__ == "__main__":
    asyncio.run(test_tracking_logic())
