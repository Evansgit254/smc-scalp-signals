import pytest
import os
import sqlite3
from unittest.mock import patch
from fastapi.testclient import TestClient
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from admin_server import app

DB_TEST = "database/clients_test_access_control.db"

@pytest.fixture
def test_db(tmp_path):
    """Setup test database with sample client and admin user"""
    db_test = str(tmp_path / "clients_test.db")
    
    conn = sqlite3.connect(db_test)
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
        CREATE TABLE admin_users (
            username TEXT PRIMARY KEY,
            password_hash TEXT,
            last_login TEXT
        )
    """)
    
    # admin/admin123
    import hashlib
    salt = "static_test_salt"
    pwd_hash = hashlib.sha256(("admin123" + salt).encode()).hexdigest()
    stored_val = f"{salt}${pwd_hash}"
    conn.execute("INSERT INTO admin_users (username, password_hash) VALUES (?, ?)", ("admin", stored_val))
    
    conn.execute("""
        INSERT INTO clients (telegram_chat_id, account_balance, is_active, dashboard_access)
        VALUES (?, ?, ?, ?)
    """, ('TEST_123', 1000.0, 1, 0))
    
    conn.commit()
    conn.close()
    return db_test

def test_toggle_signals(test_db):
    """Test toggling Telegram signal delivery"""
    with patch('admin_server.DB_CLIENTS', test_db), \
         patch('config.config.DB_CLIENTS', test_db):
        client = TestClient(app)
        
        # Authenticate
        auth_res = client.post("/api/token", data={"username": "admin", "password": "admin123"})
        if auth_res.status_code != 200:
            print(f"DEBUG: auth_res.status_code={auth_res.status_code}")
            print(f"DEBUG: auth_res.text={auth_res.text}")
        token = auth_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Toggle signals OFF
        response = client.post("/api/clients/TEST_123/toggle-signals", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['is_active'] == False
        
        # Verify in DB
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        result = cursor.execute("SELECT is_active FROM clients WHERE telegram_chat_id = 'TEST_123'").fetchone()
        assert result[0] == 0
        
        # Toggle signals back ON
        response = client.post("/api/clients/TEST_123/toggle-signals", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data['is_active'] == True
        
        # Verify in DB
        result = cursor.execute("SELECT is_active FROM clients WHERE telegram_chat_id = 'TEST_123'").fetchone()
        assert result[0] == 1
        conn.close()

def test_toggle_dashboard(test_db):
    """Test toggling dashboard access"""
    with patch('admin_server.DB_CLIENTS', test_db), \
         patch('config.config.DB_CLIENTS', test_db):
        client = TestClient(app)
        
        # Authenticate
        auth_res = client.post("/api/token", data={"username": "admin", "password": "admin123"})
        token = auth_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
    
        # Toggle dashboard ON
        response = client.post("/api/clients/TEST_123/toggle-dashboard", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['dashboard_access'] == True
        
        # Verify in DB
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        result = cursor.execute("SELECT dashboard_access FROM clients WHERE telegram_chat_id = 'TEST_123'").fetchone()
        assert result[0] == 1
        conn.close()

def test_quick_extend(test_db):
    """Test quick subscription extension"""
    with patch('admin_server.DB_CLIENTS', test_db), \
         patch('config.config.DB_CLIENTS', test_db):
        client = TestClient(app)
        
        # Authenticate
        auth_res = client.post("/api/token", data={"username": "admin", "password": "admin123"})
        token = auth_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
    
        response = client.post("/api/clients/TEST_123/extend?days=30", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert 'new_expiry' in data
        
        # Verify in DB
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        result = cursor.execute("SELECT subscription_expiry FROM clients WHERE telegram_chat_id = 'TEST_123'").fetchone()
        assert result[0] is not None
        conn.close()

if __name__ == "__main__":
    test_toggle_signals()
    test_toggle_dashboard()
    test_quick_extend()
    print("\n🎉 All Access Control Tests Passed!")
