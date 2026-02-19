import sqlite3
import json

def audit_db():
    conn = sqlite3.connect("database/signals.db")
    conn.row_factory = sqlite3.Row
    
    print("--- Database Audit Report ---")
    
    # 1. Deduplication Audit
    duplicates = conn.execute("""
        SELECT timestamp, symbol, trade_type, direction, COUNT(*) as cnt
        FROM signals 
        GROUP BY timestamp, symbol, trade_type, direction 
        HAVING cnt > 1
    """).fetchall()
    
    if duplicates:
        print(f"❌ [FAIL] Found {len(duplicates)} duplicate signal groups.")
        for d in duplicates[:5]:
            print(f"  - Duplicate: {d['timestamp']} {d['symbol']} {d['trade_type']} ({d['cnt']} instances)")
    else:
        print("✅ [PASS] No duplicate signals found.")

    # 2. Result Consistency Audit
    invalid_results = conn.execute("""
        SELECT id, result, max_tp_reached 
        FROM signals 
        WHERE result NOT IN ('OPEN', 'SL', 'TP1', 'TP2', 'TP3')
    """).fetchall()
    
    if invalid_results:
        print(f"❌ [FAIL] Found {len(invalid_results)} signals with invalid results.")
    else:
        print("✅ [PASS] All signal results are valid (OPEN/SL/TP#).")

    # 3. Strategy Type Audit
    type_counts = conn.execute("""
        SELECT trade_type, COUNT(*) as cnt FROM signals GROUP BY trade_type
    """).fetchall()
    print("\nStrategy Distribution (Sampled):")
    for t in type_counts:
        print(f"  - {t['trade_type']}: {t['cnt']}")

    # 4. Empty Value Audit
    empty_vals = conn.execute("""
        SELECT COUNT(*) as cnt FROM signals WHERE entry_price IS NULL OR sl IS NULL OR tp1 IS NULL
    """).fetchall()[0]['cnt']
    if empty_vals > 0:
        print(f"❌ [FAIL] Found {empty_vals} signals with missing price data.")
    else:
        print("✅ [PASS] No signals with missing price data.")

    conn.close()

if __name__ == "__main__":
    audit_db()
