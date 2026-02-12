import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from alerts.service import TelegramService

@pytest.fixture
def telegram_service():
    with patch('alerts.service.TELEGRAM_BOT_TOKEN', 'fake_token'), \
         patch('alerts.service.TELEGRAM_CHAT_ID', 'fake_id'):
        service = TelegramService()
        service.bot = AsyncMock()
        return service

@pytest.mark.asyncio
async def test_send_signal_success(telegram_service):
    telegram_service.bot.send_message.return_value = MagicMock()
    success = await telegram_service.send_signal("Test Message")
    assert success is True
    assert telegram_service.bot.send_message.called

@pytest.mark.asyncio
async def test_send_signal_failure(telegram_service):
    telegram_service.bot.send_message.side_effect = Exception("API Error")
    success = await telegram_service.send_signal("Test Message")
    assert success is False

@pytest.mark.asyncio
async def test_broadcast_personalized_signal_single_mode(telegram_service):
    with patch('config.config.MULTI_CLIENT_MODE', False):
        await telegram_service.broadcast_personalized_signal({'symbol': 'BTC', 'direction': 'BUY'})
        assert telegram_service.bot.send_message.called

@pytest.mark.asyncio
async def test_format_signal_assets(telegram_service):
    # Test JPY
    jpy_sig = {'symbol': 'USDJPY', 'entry_price': 150.0, 'sl': 149.0, 'tp0': 151.0}
    msg_jpy = telegram_service.format_signal(jpy_sig)
    assert msg_jpy is not None
    
    # Test XAU/BTC (pip_divisor=10)
    xau_sig = {'symbol': 'XAUUSD', 'entry_price': 2000.0, 'sl': 1990.0, 'tp0': 2010.0}
    msg_xau = telegram_service.format_signal(xau_sig)
    assert msg_xau is not None
    
    # Test fallback
    plain_sig = {'symbol': 'EURUSD', 'entry_price': 1.1000, 'sl': 1.0900, 'tp0': 1.1100}
    msg_plain = telegram_service.format_signal(plain_sig)
    assert msg_plain is not None

@pytest.mark.asyncio
async def test_send_text_failure(telegram_service):
    telegram_service.bot.send_message.side_effect = Exception("Text Fail")
    success = await telegram_service.send_text("Hello")
    assert success is False

@pytest.mark.asyncio
async def test_broadcast_personalized_signal_skipped_logic(telegram_service):
    with patch('config.config.MULTI_CLIENT_MODE', True):
        with patch('core.client_manager.ClientManager') as MockManager:
            mock_manager_instance = MockManager.return_value
            # One client active, one inactive
            mock_manager_instance.get_all_active_clients.return_value = [
                {'telegram_chat_id': 'active', 'account_balance': 1000.0, 'risk_percent': 2.0},
                {'telegram_chat_id': 'inactive', 'account_balance': 500.0, 'risk_percent': 2.0}
            ]
            mock_manager_instance.is_subscription_active.side_effect = [True, False]
            
            await telegram_service.broadcast_personalized_signal({
                'symbol': 'BTC', 'direction': 'BUY', 'entry_price': 60000, 'sl': 59000, 
                'tp0': 61000, 'tp1': 62000, 'tp2': 63000, 'timeframe': 'H1', 
                'trade_type': 'SWING', 'quality_score': 0.8, 'expected_hold': '4h'
            })
            assert telegram_service.bot.send_message.call_count == 1
