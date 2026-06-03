import pytest
import sqlite3
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from admin_server import app, get_current_user

@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = lambda: {"username": "admin"}
    yield TestClient(app)
    app.dependency_overrides.clear()

def test_strategy_list_only_crt_and_advanced_pattern(client):
    response = client.get("/api/strategies")
    assert response.status_code == 200
    strategies = response.json()
    assert {s["id"] for s in strategies} == {"crt", "advanced_pattern"}
    assert all(s["enabled"] is True and s["locked"] is True for s in strategies)

def test_retired_strategy_toggle_not_found(client):
    response = client.post("/api/strategies/retired_strategy/toggle")
    assert response.status_code == 404

def test_toggle_strategy_rejects_crt(client):
    response = client.post("/api/strategies/crt/toggle")
    assert response.status_code == 403
    assert "locked on" in response.json()["detail"]

    response2 = client.post("/api/strategies/advanced_pattern/toggle")
    assert response2.status_code == 403
    assert "locked on" in response2.json()["detail"]
