"""
Tests for Monitoring and Alerting System
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
import sqlite3

from monitoring.health_monitor import HealthMonitor
from monitoring.alert_service import AlertService
from monitoring.daily_report import DailyReportGenerator

@pytest.fixture
def mock_db(tmp_path):
    """Create temporary database for testing."""
    db_path = tmp_path / "test_signals.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE signals (
            id INTEGER PRIMARY KEY,
            symbol TEXT,
            timestamp DATETIME,
            outcome TEXT
        )
    """)
    
    # Insert sample data
    today = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
    
    # Today: 1 win, 1 loss
    cursor.execute("INSERT INTO signals (symbol, timestamp, outcome) VALUES (?, ?, ?)", 
                  ('EURUSD', today, 'WIN'))
    cursor.execute("INSERT INTO signals (symbol, timestamp, outcome) VALUES (?, ?, ?)", 
                  ('GBPUSD', today, 'LOSS'))
                  
    # Yesterday: 1 win
    cursor.execute("INSERT INTO signals (symbol, timestamp, outcome) VALUES (?, ?, ?)", 
                  ('USDJPY', yesterday, 'WIN'))
                  
    conn.commit()
    conn.close()
    return str(db_path)

@patch('monitoring.health_monitor.subprocess.run')
def test_health_monitor_metrics(mock_subprocess, mock_db):
    """Test HealthMonitor metric calculations."""
    # Mock systemctl output
    mock_subprocess.return_value.stdout = "active"
    mock_subprocess.return_value.returncode = 0
    
    monitor = HealthMonitor(signals_db_path=mock_db)
    
    # Test signal count - only counts TODAY via DATE() filter
    # Fixture inserts 'today' and 'yesterday'. daily count should be 2.
    assert monitor.get_daily_signal_count() == 2
    
    # Test win rate 
    # Logic uses DATE(timestamp) >= (now - 1 day). 
    # This includes Today (2 items) AND Yesterday (1 item).
    # Total 3 items: 2 Wins, 1 Loss. 
    # Win rate = 2/3 = 66.66%
    rate = monitor.get_win_rate(days=1)
    assert rate == pytest.approx(66.66, rel=0.01)
    
    # Test service status
    status = monitor.check_service_status()
    assert status['is_running'] is True

@patch('monitoring.alert_service.Bot')
def test_alert_service_triggers(mock_bot_cls):
    """Test AlertService trigger logic."""
    # Use AsyncMock for the bot instance to handle await calls
    mock_bot = AsyncMock()
    mock_bot_cls.return_value = mock_bot
    
    service = AlertService()
    service.monitor = Mock()
    
    # Test Signal Drought Alert
    # Mock last signal being 3 hours ago
    service.monitor.get_last_signal_time.return_value = (datetime.now() - timedelta(hours=3)).isoformat()
    
    import asyncio
    asyncio.run(service.check_signal_drought(hours=2))
    
    # Should have sent an alert
    mock_bot.send_message.assert_awaited()
    assert "No Signals Generated" in mock_bot.send_message.call_args[1]['text']

def test_daily_report_generation(mock_db):
    """Test DailyReportGenerator content."""
    with patch('monitoring.health_monitor.subprocess.run') as mock_sub:
        mock_sub.return_value.stdout = "active"
        
        generator = DailyReportGenerator()
        generator.monitor = HealthMonitor(signals_db_path=mock_db)
        
        report = generator.generate_report()
        
        assert "DAILY PERFORMANCE REPORT" in report
        assert "Today: 2 signals" in report
        # 66.67% is >= 50, so it gets ✅
        assert "Last 24h: ✅ 66.67%" in report
        assert "Status: ✅ Running" in report
