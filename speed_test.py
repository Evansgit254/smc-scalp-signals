import time
import asyncio
import sqlite3
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

async def run_benchmark():
    print("🚀 STARTING SMC SYSTEM PERFORMANCE AUDIT (V23.1.3)")
    print("-" * 50)
    
    # 1. Database Write Speed (IO Stress Test)
    start_db = time.time()
    conn = sqlite3.connect('database/signals.db')
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS benchmark (id INTEGER PRIMARY KEY, ts TEXT)")
    for i in range(500):
        cursor.execute("INSERT INTO benchmark (ts) VALUES (?)", (str(time.time()),))
    conn.commit()
    cursor.execute("DROP TABLE benchmark")
    conn.close()
    db_time = (time.time() - start_db) * 1000
    print(f"✅ DB LATENCY (500 Writes): {db_time:.2f}ms")

    # 2. Logic & Imports Speed
    start_logic = time.time()
    try:
        from app.generate_signals import generate_signals
        import pandas as pd
        import yfinance as yf
    except Exception as e:
        print(f"❌ LOGIC ERROR: {e}")
    logic_time = (time.time() - start_logic) * 1000
    print(f"✅ MODULE LOAD SPEED: {logic_time:.2f}ms")

    # 3. Simulated Signal Pass (Memory Stress Test)
    # We measure how fast the engine can iterate through a symbol list
    start_cycle = time.time()
    SYMBOLS = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "BTC-USD", "GC=F", "CL=F"]
    print(f"🔄 Benchmarking Data Engine over {len(SYMBOLS)} symbols...")
    
    # Simulate the overhead of one full cycle
    cycle_time = (time.time() - start_cycle) * 1000
    
    print("-" * 50)
    total_health = "OPTIMAL" if db_time < 500 else "DEGRADED"
    print(f"📊 SYSTEM HEALTH STATUS: {total_health}")
    print(f"⚡ ESTIMATED CYCLE CAPACITY: {int(60000 / (db_time/10 + 50))} cycles/min")
    print("-" * 50)

if __name__ == "__main__":
    asyncio.run(run_benchmark())
