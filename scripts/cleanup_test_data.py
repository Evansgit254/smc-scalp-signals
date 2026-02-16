#!/usr/bin/env python3
"""
Cleanup Script for TradingExpert
Removes test data from production databases.
"""
import sqlite3
import os
import sys

# Configuration
TEST_CLIENT_IDS = ['12345678', '777777', '999888777']
TEST_SYMBOLS = ['TESTPAIR']
DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database')

def cleanup_clients():
    db_path = os.path.join(DB_DIR, 'clients.db')
    if not os.path.exists(db_path):
        print(f"⚠️ Clients database not found at {db_path}")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check for test clients
        placeholders = ','.join('?' * len(TEST_CLIENT_IDS))
        cursor.execute(f"SELECT COUNT(*) FROM clients WHERE telegram_chat_id IN ({placeholders})", TEST_CLIENT_IDS)
        count = cursor.fetchone()[0]
        
        if count > 0:
            print(f"🗑️ Removing {count} test clients...")
            cursor.execute(f"DELETE FROM clients WHERE telegram_chat_id IN ({placeholders})", TEST_CLIENT_IDS)
            conn.commit()
            print("✅ Test clients removed.")
        else:
            print("✓ No test clients found.")
            
        conn.close()
    except Exception as e:
        print(f"❌ Error cleaning clients: {e}")

def cleanup_signals():
    db_path = os.path.join(DB_DIR, 'signals.db')
    if not os.path.exists(db_path):
        print(f"⚠️ Signals database not found at {db_path}")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check for test signals
        placeholders = ','.join('?' * len(TEST_SYMBOLS))
        cursor.execute(f"SELECT COUNT(*) FROM signals WHERE symbol IN ({placeholders})", TEST_SYMBOLS)
        count = cursor.fetchone()[0]
        
        if count > 0:
            print(f"🗑️ Removing {count} test signals...")
            cursor.execute(f"DELETE FROM signals WHERE symbol IN ({placeholders})", TEST_SYMBOLS)
            conn.commit()
            print("✅ Test signals removed.")
        else:
            print("✓ No test signals found.")
            
        conn.close()
    except Exception as e:
        print(f"❌ Error cleaning signals: {e}")

def main():
    print("🧹 Starting Data Cleanup...")
    print(f"📂 Database Directory: {DB_DIR}")
    
    cleanup_clients()
    cleanup_signals()
    
    print("✨ Cleanup Complete!")

if __name__ == "__main__":
    main()
