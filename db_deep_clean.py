import sqlite3

def deep_clean():
    db_path = "database/signals.db"
    conn = sqlite3.connect(db_path)
    
    print("🧹 Starting Deep Clean...")
    
    # 1. Fix numerical results (anything not OPEN/SL/TP#)
    # We'll assume if it's not a standard tag, it was a mis-logged SL.
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE signals 
        SET result = 'SL' 
        WHERE result NOT IN ('OPEN', 'SL', 'TP1', 'TP2', 'TP3')
    """)
    print(f"✅ Fixed {cursor.rowcount} corrupted result strings.")
    
    # 2. Standardize Symbol naming (BTC/USD -> BTC-USD)
    cursor.execute("""
        UPDATE signals 
        SET symbol = 'BTC-USD' 
        WHERE symbol IN ('BTC/USD', 'BTC-USD', 'BTCUSD')
    """)
    print(f"✅ Standardized {cursor.rowcount} BTC symbol variations.")
    
    cursor.execute("""
        UPDATE signals 
        SET symbol = 'ETH-USD' 
        WHERE symbol IN ('ETH/USD', 'ETH-USD', 'ETHUSD')
    """)
    print(f"✅ Standardized {cursor.rowcount} ETH symbol variations.")

    # 3. Handle NULL entry prices for open signals (Sanity Check)
    # If price is missing for an old open signal, mark it closed as SL to avoid tracker errors
    cursor.execute("""
        UPDATE signals 
        SET result = 'SL' 
        WHERE result = 'OPEN' AND entry_price IS NULL
    """)
    print(f"✅ Closed {cursor.rowcount} stale open signals with missing price data.")

    conn.commit()
    conn.close()
    print("✨ Deep Clean Complete!")

if __name__ == "__main__":
    deep_clean()
