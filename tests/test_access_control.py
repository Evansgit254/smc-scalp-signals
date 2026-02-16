import pytest
import sqlite3
import os
from fastapi.testclient import TestClient
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from admin_server import app

DB_TEST = "database/clients_test_access_control.db"

def setup_test_db():
    """Setup test database with sample client"""
    if os.path.exists(DB_TEST):
        os.remove(DB_TEST)
    
    conn = sqlite3.connect(DB_TEST)
    conn.execute("""
        CREATE TABLE clients (
            client_id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_chat_id TEXT UNIQUE NOT NULL,
            account_balance REAL NOT NULL,
            risk_percent REAL DEFAULT 2.0,
            subscription_expiry TIMESTAMP,
            subscription_tier TEXT DEFAULT 'BASIC',
            is_active BOOLEAN DEFAULT 1,
            dashboard_access BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.execute("""
        INSERT INTO clients (telegram_chat_id, account_balance, is_active, dashboard_access)
        VALUES (?, ?, ?, ?)
    """, ('TEST_123', 1000.0, 1, 0))
    
    conn.commit()
    conn.close()

def test_toggle_signals():
    """Test toggling Telegram signal delivery"""
    setup_test_db()
    
    # Patch admin_server to use test DB
    import admin_server
    admin_server.DB_CLIENTS = DB_TEST
    
    client = TestClient(app)
    
    # Toggle signals OFF
    response = client.post("/api/clients/TEST_123/toggle-signals")
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'success'
    assert data['is_active'] == False
    
    # Verify in DB
    conn = sqlite3.connect(DB_TEST)
    cursor = conn.cursor()
    result = cursor.execute("SELECT is_active FROM clients WHERE telegram_chat_id = 'TEST_123'").fetchone()
    assert result[0] == 0
    
    # Toggle signals back ON
    response = client.post("/api/clients/TEST_123/toggle-signals")
    assert response.status_code == 200
    data = response.json()
    assert data['is_active'] == True
    
    # Verify in DB
    result = cursor.execute("SELECT is_active FROM clients WHERE telegram_chat_id = 'TEST_123'").fetchone()
    assert result[0] == 1
    
    conn.close()
    os.remove(DB_TEST)
    print("✅ Toggle Signals Test Passed!")

def test_toggle_dashboard():
    """Test toggling dashboard access"""
    setup_test_db()
    
    import admin_server
    admin_server.DB_CLIENTS = DB_TEST
    
    client = TestClient(app)
    
    # Toggle dashboard ON
    response = client.post("/api/clients/TEST_123/toggle-dashboard")
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'success'
    assert data['dashboard_access'] == True
    
    # Verify in DB
    conn = sqlite3.connect(DB_TEST)
    cursor = conn.cursor()
    result = cursor.execute("SELECT dashboard_access FROM clients WHERE telegram_chat_id = 'TEST_123'").fetchone()
    assert result[0] == 1
    
    conn.close()
    os.remove(DB_TEST)
    print("✅ Toggle Dashboard Test Passed!")

def test_quick_extend():
    """Test quick subscription extension"""
    setup_test_db()
    
    import admin_server
    admin_server.DB_CLIENTS = DB_TEST
    
    client = TestClient(app)
    
    response = client.post("/api/clients/TEST_123/extend?days=30")
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'success'
    assert 'new_expiry' in data
    
    # Verify in DB
    conn = sqlite3.connect(DB_TEST)
    cursor = conn.cursor()
    result = cursor.execute("SELECT subscription_expiry FROM clients WHERE telegram_chat_id = 'TEST_123'").fetchone()
    assert result[0] is not None
    
    conn.close()
    os.remove(DB_TEST)
    print("✅ Quick Extend Test Passed!")

if __name__ == "__main__":
    test_toggle_signals()
    test_toggle_dashboard()
    test_quick_extend()
    print("\n🎉 All Access Control Tests Passed!")
