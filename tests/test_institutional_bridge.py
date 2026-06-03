"""
Institutional Bridge Test Suite (v5.1.2)
Tests for MT5 heartbeat, data-provider pivoting, system governance, and all API contracts.
"""
import pytest
import os
from fastapi.testclient import TestClient
from admin_server import app, get_current_user, User
from config.manager import config_manager

pytestmark = [pytest.mark.integration]

# ── AUTH MOCK ──────────────────────────────────────────────
async def mock_get_current_user():
    return User(username="admin")

@pytest.fixture(autouse=True)
def auth_override():
    app.state.disable_reconciliation_loop = True
    config_manager.set_runtime_override("mt5_paper_mode", True)
    config_manager.set_runtime_override("metaapi_token", "")
    config_manager.set_runtime_override("metaapi_account_id", "")
    app.dependency_overrides[get_current_user] = mock_get_current_user
    yield
    app.dependency_overrides.clear()
    config_manager.clear_runtime_overrides()
    app.state.disable_reconciliation_loop = False
client = TestClient(app)


# ── STATIC / DASHBOARD ────────────────────────────────────
class TestDashboardServing:
    def test_root_serves_index(self):
        """Dashboard root returns 200 with HTML content."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_dashboard_has_title(self):
        """Dashboard contains a proper <title> tag."""
        response = client.get("/")
        assert "<title>" in response.text


# ── DATA PROVIDER PIVOT ───────────────────────────────────
class TestDataProviderPivot:
    def test_switch_to_yfinance(self):
        """POST /api/config/data-provider with yfinance returns success."""
        response = client.post(
            "/api/config/data-provider",
            json={"key": "data_provider", "value": "yfinance"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["provider"] == "yfinance"

    def test_switch_to_mt5(self):
        """POST /api/config/data-provider with mt5 returns success."""
        response = client.post(
            "/api/config/data-provider",
            json={"key": "data_provider", "value": "mt5"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["provider"] == "mt5"

    def test_invalid_provider_rejected(self):
        """POST /api/config/data-provider with invalid provider returns 400."""
        response = client.post(
            "/api/config/data-provider",
            json={"key": "data_provider", "value": "invalid_source"}
        )
        assert response.status_code == 400


# ── MT5 HEARTBEAT ─────────────────────────────────────────
class TestMT5Heartbeat:
    def test_mt5_status_disconnected_in_yfinance_mode(self):
        """When DATA_MODE is YFINANCE, MT5 heartbeat reports DISCONNECTED."""
        os.environ["DATA_MODE"] = "YFINANCE"
        response = client.get("/api/mt5/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "DISCONNECTED"
        assert data["mode"] == "YFINANCE"

    def test_mt5_status_in_mt5_mode(self):
        """When DATA_MODE is MT5_BRIDGE, MT5 heartbeat reports a non-DISCONNECTED state."""
        os.environ["DATA_MODE"] = "MT5_BRIDGE"
        response = client.get("/api/mt5/status")
        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "MT5_BRIDGE"
        assert data["status"] in ("CONNECTED", "CONNECTING", "ERROR")

    def test_mt5_status_has_required_fields(self):
        """MT5 status response always includes status, mode, and account fields."""
        response = client.get("/api/mt5/status")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "mode" in data
        assert "account" in data


# ── SYSTEM GOVERNANCE ─────────────────────────────────────
class TestSystemGovernance:
    def test_invalid_action_rejected(self):
        """Invalid governance actions are rejected with 400."""
        response = client.post("/api/system/manage", json={"action": "destroy_all"})
        assert response.status_code == 400

    def test_valid_actions_accepted(self):
        """Valid governance actions (backup, update, rollback) are accepted."""
        for action in ["backup", "update", "rollback"]:
            response = client.post("/api/system/manage", json={"action": action})
            assert response.status_code == 200
            data = response.json()
            assert "status" in data

    def test_backup_returns_output(self):
        """Backup action returns a response with output or status field."""
        response = client.post("/api/system/manage", json={"action": "backup"})
        assert response.status_code == 200
        data = response.json()
        assert "status" in data


# ── SYSTEM CONFIG ─────────────────────────────────────────
class TestSystemConfig:
    def test_config_returns_symbols_and_strategies(self):
        """GET /api/system/config returns symbols and strategies."""
        response = client.get("/api/system/config")
        assert response.status_code == 200
        data = response.json()
        assert "symbols" in data
        assert "strategies" in data
        assert isinstance(data["symbols"], list)
        assert isinstance(data["strategies"], list)
        assert len(data["symbols"]) > 0
        assert len(data["strategies"]) > 0


# ── EXISTING API CONTRACTS ────────────────────────────────
class TestExistingAPIs:
    def test_signals_endpoint(self):
        """GET /api/signals returns list of signals with core fields."""
        response = client.get("/api/signals?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            assert "symbol" in data[0]
            assert "direction" in data[0]
            assert "confidence" in data[0]

    def test_stats_endpoint(self):
        """GET /api/stats returns system status and market context."""
        response = client.get("/api/stats")
        assert response.status_code == 200
        data = response.json()
        assert "system_status" in data
        assert "market_context" in data
        assert "active_clients" in data

    def test_clients_endpoint(self):
        """GET /api/clients returns list of registered clients."""
        response = client.get("/api/clients")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_execution_positions(self):
        """GET /api/execution/positions returns open trade data."""
        response = client.get("/api/execution/positions")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_execution_paper_account(self):
        """GET /api/execution/paper-account returns balance and gate metrics."""
        response = client.get("/api/execution/paper-account")
        assert response.status_code == 200
        data = response.json()
        assert "balance" in data
        assert "equity" in data
        assert "total_passed" in data

    def test_gate_log(self):
        """GET /api/execution/gate-log returns decision history."""
        response = client.get("/api/execution/gate-log")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_observation_report(self):
        """GET /api/execution/observation-report returns readiness metrics."""
        response = client.get("/api/execution/observation-report")
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert "readiness_score" in data

    def test_analytics_daily(self):
        """GET /api/analytics/daily returns full performance matrix."""
        response = client.get("/api/analytics/daily")
        assert response.status_code == 200
        data = response.json()
        assert "total_signals" in data
        assert "assets" in data
        assert "stats_by_type" in data

    def test_backtest_runs(self):
        """GET /api/backtest/runs returns historical backtest metadata."""
        response = client.get("/api/backtest/runs")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_config_weights(self):
        """GET /api/config/weights returns active alpha multipliers."""
        response = client.get("/api/config/weights")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            assert "event_type" in data[0]
            assert "multiplier" in data[0]
