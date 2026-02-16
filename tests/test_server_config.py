import sys
import os
import unittest
import sqlite3
from fastapi.testclient import TestClient

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from admin_server import app, DB_CLIENTS
from signal_service import SignalService
import config.config as cfg

class TestServerConfig(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.db_path = DB_CLIENTS
        # Backup original risk value
        self.original_risk = 2.0
        try:
            conn = sqlite3.connect(self.db_path)
            row = conn.execute("SELECT value FROM system_config WHERE key='risk_per_trade'").fetchone()
            if row:
                self.original_risk = float(row[0])
            conn.close()
        except:
            pass

    def tearDown(self):
        # Restore original risk value
        conn = sqlite3.connect(self.db_path)
        conn.execute("UPDATE system_config SET value = ? WHERE key='risk_per_trade'", (str(self.original_risk),))
        conn.commit()
        conn.close()
        # Reset in memory config
        cfg.RISK_PER_TRADE_PERCENT = self.original_risk

    def test_get_config(self):
        """Test retrieving configuration via API"""
        response = self.client.get("/api/config")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("risk_per_trade", data)
        self.assertIn("system_status", data)

    def test_update_config_and_service_load(self):
        """Test updating config via API and verifying service loads it"""
        # 1. Update Config via API
        new_risk = 5.5
        response = self.client.post("/api/config", json={"key": "risk_per_trade", "value": str(new_risk)})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["value"], str(new_risk))

        # 2. Verify in Database
        conn = sqlite3.connect(self.db_path)
        val = conn.execute("SELECT value FROM system_config WHERE key='risk_per_trade'").fetchone()[0]
        conn.close()
        self.assertEqual(float(val), new_risk)

        # 3. Verify Service loads it
        service = SignalService()
        # Mock telegram to avoid errors during init if not set, 
        # but SignalService init only sets self.telegram = TelegramService()
        # We just want to test _load_dynamic_config
        
        # Reset config module to default (simulating fresh start or pre-update state)
        cfg.RISK_PER_TRADE_PERCENT = 2.0 
        
        service._load_dynamic_config()
        
        self.assertEqual(cfg.RISK_PER_TRADE_PERCENT, new_risk)
        print(f"\n✅ Verified: Config module updated to {cfg.RISK_PER_TRADE_PERCENT}% (Expected {new_risk}%)")

if __name__ == '__main__':
    unittest.main()
