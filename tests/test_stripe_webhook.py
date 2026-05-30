import json
import sqlite3
import os
import sys
from datetime import datetime
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from admin_server import app, stripe_webhook

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
    
    with patch('admin_server.DB_CLIENTS', DB_CLIENTS), \
         patch('admin_server.STRIPE_WEBHOOK_SECRET', None), \
         patch('admin_server.ALLOW_UNSIGNED_STRIPE_WEBHOOK', True), \
         patch('config.config.DB_CLIENTS', DB_CLIENTS):
        
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

@pytest.mark.asyncio
async def test_stripe_webhook_requires_signature_without_dev_bypass():
    class FakeRequest:
        headers = {}

        async def body(self):
            return b'{"type":"checkout.session.completed"}'

    with patch('admin_server.STRIPE_WEBHOOK_SECRET', None), \
         patch('admin_server.ALLOW_UNSIGNED_STRIPE_WEBHOOK', False):
        with pytest.raises(HTTPException) as exc:
            await stripe_webhook(FakeRequest())

    assert exc.value.status_code == 503

if __name__ == "__main__":
    test_stripe_webhook_activation()
