import json
import sqlite3
import os
import sys
from datetime import datetime
from fastapi.testclient import TestClient

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from admin_server import app

DB_CLIENTS = "database/clients_test_webhook.db"

def setup_test_db():
    if os.path.exists(DB_CLIENTS): os.remove(DB_CLIENTS)
    conn = sqlite3.connect(DB_CLIENTS)
    conn.execute("""
        CREATE TABLE clients (
            client_id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_chat_id TEXT UNIQUE NOT NULL,
            account_balance REAL NOT NULL,
            risk_percent REAL DEFAULT 2.0,
            subscription_expiry TIMESTAMP,
            subscription_tier TEXT DEFAULT 'BASIC',
            is_active BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Insert a deactivated client
    conn.execute("""
        INSERT INTO clients (telegram_chat_id, account_balance, is_active)
        VALUES (?, ?, ?)
    """, ('TEST_USER_123', 500.0, 0))
    
    conn.commit()
    conn.close()

def test_stripe_webhook_activation():
    setup_test_db()
    
    # Patch admin_server to use test DB and bypass signature for test
    import admin_server
    admin_server.DB_CLIENTS = DB_CLIENTS
    admin_server.STRIPE_WEBHOOK_SECRET = None # Bypass signature check
    
    client = TestClient(app)
    
    # Mock Stripe Payload
    webhook_payload = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_123",
                "metadata": {
                    "telegram_chat_id": "TEST_USER_123",
                    "subscription_days": "30",
                    "tier": "GOLD"
                }
            }
        }
    }
    
    print("🚀 Sending Mock Stripe Webhook...")
    response = client.post("/api/stripe/webhook", json=webhook_payload)
    
    assert response.status_code == 200
    assert response.json() == {"status": "success"}
    
    # Verify DB update
    conn = sqlite3.connect(DB_CLIENTS)
    conn.row_factory = sqlite3.Row
    res = conn.execute("SELECT * FROM clients WHERE telegram_chat_id = 'TEST_USER_123'").fetchone()
    
    print(f"📊 VERIFICATION RESULTS:")
    print(f"Status: {'✅ ACTIVE' if res['is_active'] else '❌ INACTIVE'}")
    print(f"Tier: {res['subscription_tier']}")
    print(f"Expiry: {res['subscription_expiry']}")
    
    assert res['is_active'] == 1
    assert res['subscription_tier'] == 'GOLD'
    assert res['subscription_expiry'] is not None
    
    print("\n✅ Stripe Webhook Activation Test Passed!")
    
    if os.path.exists(DB_CLIENTS): os.remove(DB_CLIENTS)

if __name__ == "__main__":
    test_stripe_webhook_activation()
