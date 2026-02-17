import pytest
import sqlite3
import os
from unittest.mock import patch, MagicMock
from monitoring.health_monitor import HealthMonitor
from datetime import datetime
from pathlib import Path

@pytest.fixture
def mock_dbs(tmp_path):
    signals_db = str(tmp_path / "signals.db")
    metrics_db = str(tmp_path / "metrics.db")
    
    # Create signals table
    conn = sqlite3.connect(signals_db)
    conn.execute("CREATE TABLE signals (timestamp TIMESTAMP, outcome TEXT)")
    conn.execute("INSERT INTO signals VALUES (?, ?)", (datetime.now().isoformat(), 'WIN'))
    conn.execute("INSERT INTO signals VALUES (?, ?)", (datetime.now().isoformat(), 'LOSS'))
    conn.commit()
    conn.close()
    
    return signals_db, metrics_db

def test_health_monitor_init(mock_dbs):
    sig_db, met_db = mock_dbs
    with patch('monitoring.health_monitor.HealthMonitor._init_metrics_db'):
        monitor = HealthMonitor(sig_db)
        assert monitor.signals_db == sig_db

def test_get_daily_signal_count(mock_dbs):
    sig_db, _ = mock_dbs
    monitor = HealthMonitor(sig_db)
    # The monitor class hardcodes metrics.db path in __init__, 
    # but we can patch it or just let it create a file in monitoring/metrics.db
    count = monitor.get_daily_signal_count()
    assert count == 2

def test_get_win_rate(mock_dbs):
    sig_db, _ = mock_dbs
    monitor = HealthMonitor(sig_db)
    win_rate = monitor.get_win_rate()
    assert win_rate == 50.0

def test_get_win_rate_empty(tmp_path):
    empty_db = str(tmp_path / "empty.db")
    conn = sqlite3.connect(empty_db)
    conn.execute("CREATE TABLE signals (timestamp TIMESTAMP, outcome TEXT)")
    conn.commit()
    conn.close()
    monitor = HealthMonitor(empty_db)
    assert monitor.get_win_rate() is None

def test_check_service_status(mock_dbs):
    sig_db, _ = mock_dbs
    monitor = HealthMonitor(sig_db)
    with patch('monitoring.health_monitor.subprocess.run') as mock_run:
        mock_run.side_effect = [
            MagicMock(stdout='active\n', returncode=0),
            MagicMock(stdout='ActiveEnterTimestamp=Mon 2026-02-16 10:00:00 UTC\n', returncode=0)
        ]
        status = monitor.check_service_status()
        assert status['is_running'] is True

def test_check_service_status_error(mock_dbs):
    sig_db, _ = mock_dbs
    monitor = HealthMonitor(sig_db)
    with patch('monitoring.health_monitor.subprocess.run', side_effect=Exception("Subprocess failed")):
        status = monitor.check_service_status()
        assert status['is_running'] is False
        assert 'error' in status

def test_get_last_signal_time(mock_dbs):
    sig_db, _ = mock_dbs
    monitor = HealthMonitor(sig_db)
    last_time = monitor.get_last_signal_time()
    assert last_time is not None

def test_record_daily_metrics(mock_dbs):
    sig_db, _ = mock_dbs
    monitor = HealthMonitor(sig_db)
    # Patch metrics_db to use a temp one
    monitor.metrics_db = str(Path(sig_db).parent / "metrics_test.db")
    monitor._init_metrics_db()
    
    with patch.object(monitor, 'check_service_status', return_value={'is_running': True}):
        monitor.record_daily_metrics()
        
    conn = sqlite3.connect(monitor.metrics_db)
    row = conn.execute("SELECT total_signals, win_rate FROM daily_metrics").fetchone()
    assert row[0] == 2
    assert row[1] == 50.0
    conn.close()

def test_get_health_summary(mock_dbs):
    sig_db, _ = mock_dbs
    monitor = HealthMonitor(sig_db)
    summary = monitor.get_health_summary()
    assert 'signals_today' in summary
    assert 'win_rate_24h' in summary

def test_health_monitor_exceptions(mock_dbs):
    sig_db, _ = mock_dbs
    monitor = HealthMonitor(sig_db)
    with patch('sqlite3.connect', side_effect=Exception("DB Fail")):
        assert monitor.get_daily_signal_count() == 0
        assert monitor.get_win_rate() is None
        assert monitor.get_last_signal_time() is None
