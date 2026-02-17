import pytest
import asyncio
from unittest.mock import patch, MagicMock
from monitoring.alert_service import AlertService
from monitoring.daily_report import DailyReportGenerator
from datetime import datetime, timedelta

@pytest.fixture
def mock_monitor():
    monitor = MagicMock()
    monitor.check_service_status.return_value = {
        'is_running': True,
        'last_check': datetime.now().isoformat(),
        'uptime_seconds': 3600
    }
    monitor.get_last_signal_time.return_value = datetime.now().isoformat()
    monitor.get_win_rate.return_value = 50.0
    monitor.get_daily_signal_count.return_value = 250
    monitor.get_health_summary.return_value = {
        'signals_today': 250,
        'win_rate_24h': 50.0,
        'win_rate_7d': 50.0,
        'win_rate_30d': 50.0,
        'service_status': {'is_running': True},
        'last_signal': datetime.now().isoformat()
    }
    return monitor

@pytest.mark.asyncio
async def test_alert_service_send_alert(mock_monitor):
    with patch('monitoring.alert_service.Bot') as mock_bot:
        service = AlertService()
        service.monitor = mock_monitor
        service.bot = mock_bot.return_value
        
        # Test successful send
        mock_bot.return_value.send_message = MagicMock()
        fut = asyncio.Future()
        fut.set_result(True)
        mock_bot.return_value.send_message.return_value = fut
        
        res = await service.send_alert("Test Message", "test_type")
        assert res is True
        assert mock_bot.return_value.send_message.called

@pytest.mark.asyncio
async def test_alert_service_cooldown(mock_monitor):
    service = AlertService()
    service.monitor = mock_monitor
    service.alert_cooldown["test_type"] = datetime.now()
    
    # Within cooldown
    res = await service.send_alert("Test Message", "test_type")
    assert res is False

@pytest.mark.asyncio
async def test_alert_service_send_alert_no_bot():
    service = AlertService()
    service.bot = None
    res = await service.send_alert("Test")
    assert res is False

@pytest.mark.asyncio
async def test_alert_service_send_alert_telegram_error(mock_monitor):
    from telegram.error import TelegramError
    with patch('monitoring.alert_service.Bot') as mock_bot:
        service = AlertService()
        service.monitor = mock_monitor
        service.bot = mock_bot.return_value
        # Mocking an awaitable that raises
        fut = asyncio.Future()
        fut.set_exception(TelegramError("Fail"))
        mock_bot.return_value.send_message.return_value = fut
        
        res = await service.send_alert("Test")
        assert res is False

@pytest.mark.asyncio
async def test_alert_service_check_signal_drought_none(mock_monitor):
    service = AlertService()
    service.monitor = mock_monitor
    mock_monitor.get_last_signal_time.return_value = None
    await service.check_signal_drought() # Should return gracefully

@pytest.mark.asyncio
async def test_alert_service_check_service_down(mock_monitor):
    service = AlertService()
    service.monitor = mock_monitor
    mock_monitor.check_service_status.return_value = {'is_running': False, 'last_check': 'now'}
    
    with patch.object(service, 'send_alert', return_value=True) as mock_send:
        await service.check_service_down()
        assert mock_send.called
        assert "Service Stopped" in mock_send.call_args[0][0]

@pytest.mark.asyncio
async def test_alert_service_check_signal_drought(mock_monitor):
    service = AlertService()
    service.monitor = mock_monitor
    # 5 hours ago
    last_time = (datetime.now() - timedelta(hours=5)).isoformat()
    mock_monitor.get_last_signal_time.return_value = last_time
    
    with patch.object(service, 'send_alert', return_value=True) as mock_send:
        await service.check_signal_drought(hours=2)
        assert mock_send.called
        assert "No Signals Generated" in mock_send.call_args[0][0]

@pytest.mark.asyncio
async def test_daily_report_generation(mock_monitor):
    generator = DailyReportGenerator()
    generator.monitor = mock_monitor
    
    report = generator.generate_report()
    assert "DAILY PERFORMANCE REPORT" in report
    assert "250 signals" in report
    assert "✅ 50.00%" in report

@pytest.mark.asyncio
async def test_daily_report_send(mock_monitor):
    with patch('monitoring.daily_report.Bot') as mock_bot:
        generator = DailyReportGenerator()
        generator.monitor = mock_monitor
        generator.bot = mock_bot.return_value
        
        mock_bot.return_value.send_message = MagicMock()
        fut = asyncio.Future()
        fut.set_result(True)
        mock_bot.return_value.send_message.return_value = fut
        
        res = await generator.send_report()
        assert res is True
        assert mock_bot.return_value.send_message.called

@pytest.mark.asyncio
async def test_daily_report_send_no_bot():
    generator = DailyReportGenerator()
    generator.bot = None
    res = await generator.send_report()
    assert res is False

@pytest.mark.asyncio
async def test_daily_report_send_telegram_error(mock_monitor):
    from telegram.error import TelegramError
    with patch('monitoring.daily_report.Bot') as mock_bot:
        generator = DailyReportGenerator()
        generator.monitor = mock_monitor
        generator.bot = mock_bot.return_value
        
        fut = asyncio.Future()
        fut.set_exception(TelegramError("Fail"))
        mock_bot.return_value.send_message.return_value = fut
        
        res = await generator.send_report()
        assert res is False

def test_daily_report_symbol_breakdown():
    gen = DailyReportGenerator()
    assert gen._get_symbol_breakdown() == "Coming soon..."

@pytest.mark.asyncio
async def test_alert_service_anomalies(mock_monitor):
    service = AlertService()
    service.monitor = mock_monitor
    
    # Win rate anomaly
    mock_monitor.get_win_rate.return_value = 30.0
    with patch.object(service, 'send_alert') as mock_send:
        await service.check_win_rate_anomaly(threshold=40.0)
        assert mock_send.called
        assert "Win Rate Alert" in mock_send.call_args[0][0]

@pytest.mark.asyncio
async def test_alert_service_check_win_rate_anomaly_none(mock_monitor):
    service = AlertService()
    service.monitor = mock_monitor
    mock_monitor.get_win_rate.return_value = None
    await service.check_win_rate_anomaly() # Should return gracefully

    # Signal count anomaly
    mock_monitor.get_daily_signal_count.return_value = 50
    with patch.object(service, 'send_alert') as mock_send:
        await service.check_signal_count_anomaly()
        assert mock_send.called
        assert "Low Signal Count" in mock_send.call_args[0][0]

def test_daily_report_format_win_rate():
    gen = DailyReportGenerator()
    assert gen._format_win_rate(None) == "N/A"
    assert "✅" in gen._format_win_rate(55.0)
    assert "⚠️" in gen._format_win_rate(48.0)
    assert "❌" in gen._format_win_rate(40.0)
