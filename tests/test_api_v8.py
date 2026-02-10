import pytest
# Legacy test - API module removed
pytest.skip("API module removed", allow_module_level=True)
# from fastapi.testclient import TestClient
# from api import app
import os
import sqlite3
from unittest.mock import patch, MagicMock

client = TestClient(app)

@pytest.fixture
def mock_db(tmp_path):
    db_file = tmp_path / "test_signals.db"
    conn = sqlite3.connect(db_file)
    conn.execute("CREATE TABLE signals (id INTEGER PRIMARY KEY, timestamp TEXT, symbol TEXT, direction TEXT, status TEXT, confidence REAL, strategy_id TEXT, res TEXT, result_pips REAL)")
    conn.commit()
    return str(db_file)

def test_health_check(mock_db):
    with patch("api.DB_PATH", mock_db):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "online"
        assert response.json()["database"] == "connected"

def test_health_check_missing_db():
    with patch("api.DB_PATH", "non_existent.db"):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["database"] == "missing"

def test_get_signals_empty(mock_db):
    with patch("api.DB_PATH", mock_db):
        response = client.get("/signals")
        assert response.status_code == 200
        assert response.json() == []

def test_get_signals_with_data(mock_db):
    conn = sqlite3.connect(mock_db)
    conn.execute("INSERT INTO signals (timestamp, symbol, direction, status, confidence, strategy_id) VALUES (?, ?, ?, ?, ?, ?)",
                 ("2026-01-23T00:00:00", "EURUSD=X", "BUY", "PENDING", 8.5, "smc_institutional"))
    conn.commit()
    
    with patch("api.DB_PATH", mock_db):
        response = client.get("/signals")
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["symbol"] == "EURUSD=X"

def test_get_stats_empty(mock_db):
    with patch("api.DB_PATH", mock_db):
        response = client.get("/stats")
        assert response.status_code == 200
        assert response.json() == {"total_trades": 0, "win_rate": 0, "total_r": 0}

def test_get_stats_with_data(mock_db):
    conn = sqlite3.connect(mock_db)
    conn.execute("INSERT INTO signals (status, res, result_pips) VALUES (?, ?, ?)", ("RESOLVED", "WIN", 2.5))
    conn.execute("INSERT INTO signals (status, res, result_pips) VALUES (?, ?, ?)", ("RESOLVED", "LOSS", -1.0))
    conn.commit()
    
    with patch("api.DB_PATH", mock_db):
        response = client.get("/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_trades"] == 2
        assert data["win_rate"] == 50.0
        assert data["total_r"] == 1.5

def test_get_logs_missing():
    with patch("api.LOG_PATH", "non_existent.log"):
        response = client.get("/logs")
        assert response.status_code == 200
        assert response.json() == []

def test_get_logs_success(tmp_path):
    log_file = tmp_path / "test.log"
    log_file.write_text("line1\nline2\nline3\n")
    
    with patch("api.LOG_PATH", str(log_file)):
        response = client.get("/logs?lines=2")
        assert response.status_code == 200
        assert response.json() == ["line2\n", "line3\n"]

def test_api_error_handling(mock_db):
    # Test GET /signals error
    with patch("api.get_db_connection", side_effect=Exception("DB Error")):
        with patch("api.DB_PATH", mock_db):
            response = client.get("/signals")
            assert response.status_code == 500
            assert "DB Error" in response.json()["detail"]

    # Test GET /stats error
    with patch("api.get_db_connection", side_effect=Exception("Stats Error")):
        with patch("api.DB_PATH", mock_db):
            response = client.get("/stats")
            assert response.status_code == 500
            assert "Stats Error" in response.json()["detail"]

    # Test GET /logs error (filesystem error)
    with patch("builtins.open", side_effect=Exception("Read Error")):
        with patch("os.path.exists", return_value=True):
            with patch("api.LOG_PATH", "some.log"):
                response = client.get("/logs")
                assert response.status_code == 500
                assert "Read Error" in response.json()["detail"]

def test_health_check_various_states(mock_db):
    # Online
    with patch("api.DB_PATH", mock_db):
        response = client.get("/health")
        assert response.json()["database"] == "connected"
    
    # Missing
    with patch("api.DB_PATH", "/tmp/missing.db"):
        response = client.get("/health")
        assert response.json()["database"] == "missing"
