import pytest
from fastapi.testclient import TestClient
from admin_server import app
import sqlite3
import os
from datetime import datetime, timedelta

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_test_dbs(tmp_path):
    # Use temporary databases for testing
    clients_db = str(tmp_path / "clients.db")
    signals_db = str(tmp_path / "signals.db")
    
    # Initialize clients DB
    conn = sqlite3.connect(clients_db)
    conn.execute("""
        CREATE TABLE clients (
            client_id INTEGER PRIMARY KEY,
            telegram_chat_id TEXT UNIQUE,
            account_balance REAL,
            risk_percent REAL DEFAULT 2.0,
            subscription_expiry TIMESTAMP,
            subscription_tier TEXT,
            is_active BOOLEAN DEFAULT 1,
            updated_at TIMESTAMP
        )
    """)
    conn.execute("INSERT INTO clients (telegram_chat_id, account_balance) VALUES ('123', 1000.0)")
    conn.commit()
    conn.close()
    
    # Initialize signals DB
    conn = sqlite3.connect(signals_db)
    conn.execute("""
        CREATE TABLE signals (
            id INTEGER PRIMARY KEY,
            timestamp TIMESTAMP,
            symbol TEXT,
            direction TEXT,
            entry_price REAL,
            sl REAL,
            tp1 REAL,
            tp2 REAL,
            reasoning TEXT,
            timeframe TEXT,
            confidence REAL,
            trade_type TEXT,
            quality_score REAL,
            regime TEXT,
            expected_hold TEXT,
            risk_details TEXT,
            score_details TEXT
        )
    """)
    conn.commit()
    conn.close()
    
    with patch('admin_server.DB_CLIENTS', clients_db), \
         patch('admin_server.DB_SIGNALS', signals_db):
        yield

from unittest.mock import patch

def test_read_clients():
    response = client.get("/api/clients")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]['telegram_chat_id'] == '123'

def test_update_client():
    update_data = {
        "account_balance": 1500.0,
        "subscription_days": 30,
        "tier": "GOLD",
        "is_active": True
    }
    response = client.post("/api/clients/123", json=update_data)
    assert response.status_code == 200
    
    # Verify update
    response = client.get("/api/clients")
    updated = response.json()[0]
    assert updated['account_balance'] == 1500.0
    assert updated['subscription_tier'] == 'GOLD'
    assert updated['subscription_expiry'] is not None

def test_update_non_existent_client():
    response = client.post("/api/clients/999", json={"account_balance": 100})
    assert response.status_code == 404

def test_read_signals_empty():
    response = client.get("/api/signals")
    assert response.status_code == 200
    assert response.json() == []

def test_get_stats():
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert data['active_clients'] == 1
    assert data['signals_today'] == 0
    assert 'server_time' in data

def test_update_client_all_fields():
    update_data = {
        "account_balance": 2000.0,
        "risk_percent": 3.5,
        "subscription_days": 10,
        "tier": "PLATINUM",
        "is_active": False
    }
    response = client.post("/api/clients/123", json=update_data)
    assert response.status_code == 200
    
    # Verify update
    response = client.get("/api/clients")
    updated = response.json()[0]
    assert updated['account_balance'] == 2000.0
    assert updated['risk_percent'] == 3.5
    assert updated['subscription_tier'] == 'PLATINUM'
    assert updated['is_active'] == 0

def test_update_client_no_fields():
    response = client.post("/api/clients/123", json={})
    assert response.status_code == 200

def test_get_signals_with_data(tmp_path):
    signals_db = str(tmp_path / "signals_test.db")
    # Insert a mock signal
    conn = sqlite3.connect(signals_db)
    conn.execute("""
        CREATE TABLE signals (
            id INTEGER PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            symbol TEXT,
            direction TEXT,
            entry_price REAL,
            sl REAL,
            tp1 REAL,
            tp2 REAL,
            reasoning TEXT,
            timeframe TEXT,
            confidence REAL,
            trade_type TEXT,
            quality_score REAL,
            regime TEXT,
            expected_hold TEXT,
            risk_details TEXT,
            score_details TEXT
        )
    """)
    conn.execute("INSERT INTO signals (symbol, direction, entry_price, sl, tp1, tp2, confidence) VALUES ('EURUSD', 'BUY', 1.10, 1.09, 1.11, 1.12, 0.9)")
    conn.commit()
    conn.close()
    
    with patch('admin_server.DB_SIGNALS', signals_db):
        response = client.get("/api/signals")
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]['symbol'] == 'EURUSD'
