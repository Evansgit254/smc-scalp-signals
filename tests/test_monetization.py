import pytest
import sqlite3
import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from core.client_manager import ClientManager
from alerts.service import TelegramService

@pytest.fixture
def client_manager(tmp_path):
    db_path = str(tmp_path / "clients.db")
    return ClientManager(db_path=db_path)

@pytest.fixture
def telegram_service():
    return TelegramService()

def test_subscription_lifecycle(client_manager):
    chat_id = "test_sub_client"
    client_manager.register_client(chat_id, 1000.0)
    
    # 1. New client should have no active subscription
    assert client_manager.is_subscription_active(chat_id) is False
    
    # 2. Add 30 days
    res = client_manager.update_subscription(chat_id, days=30, tier="GOLD")
    assert res['status'] == 'success'
    assert res['tier'] == 'GOLD'
    assert client_manager.is_subscription_active(chat_id) is True
    
    # 3. Add 30 more days (should extend)
    res = client_manager.update_subscription(chat_id, days=30)
    assert res['status'] == 'success'
    # Check if expiry is roughly 60 days from now
    expiry = datetime.strptime(res['new_expiry'], "%Y-%m-%d %H:%M:%S")
    expected = datetime.now() + timedelta(days=60)
    assert (expiry - expected).total_seconds() < 10 # Allowance for execution time
    
    # 4. Test Expired
    with patch('core.client_manager.datetime') as mock_date:
        # Mock "now" to be far in the future
        mock_date.now.return_value = datetime.now() + timedelta(days=100)
        mock_date.strptime = datetime.strptime
        assert client_manager.is_subscription_active(chat_id) is False

@pytest.mark.asyncio
async def test_signal_gating(client_manager, telegram_service):
    chat_id_active = "active_user_gate"
    chat_id_expired = "expired_user_gate"
    
    # Use a clean DB for this test
    client_manager.register_client(chat_id_active, 1000.0)
    client_manager.update_subscription(chat_id_active, days=30)
    
    client_manager.register_client(chat_id_expired, 500.0)
    
    mock_signal = {
        'symbol': 'BTC/USD', 
        'direction': 'BUY', 
        'entry_price': 60000,
        'sl': 59000,
        'tp0': 61000,
        'tp1': 62000,
        'tp2': 63000,
        'timeframe': 'H1',
        'trade_type': 'SWING',
        'reasoning': 'Test signal',
        'quality_score': 0.8,
        'expected_hold': '4h'
    }
    
    # Force the local imports to use our mocks by patching the sys.modules or the target directly
    with patch('core.client_manager.ClientManager') as MockManager:
        MockManager.return_value = client_manager
        
        # Mock SignalFormatter to avoid formatting logic entirely in this test
        with patch('alerts.service.SignalFormatter.format_personalized_signal', return_value="Test Formatted Signal"):
            # Ensure get_all_active_clients returns our test users
            client_manager.get_all_active_clients = MagicMock(return_value=[
                {'telegram_chat_id': chat_id_active, 'account_balance': 1000.0, 'risk_percent': 2.0},
                {'telegram_chat_id': chat_id_expired, 'account_balance': 500.0, 'risk_percent': 2.0}
            ])
            
            with patch('config.config.MULTI_CLIENT_MODE', True):
                with patch.object(telegram_service, 'send_text', new_callable=AsyncMock) as mock_send:
                    mock_send.return_value = True
                    await telegram_service.broadcast_personalized_signal(mock_signal)
                    
                    # Should only send to active_user
                    assert mock_send.call_count == 1
                    args, kwargs = mock_send.call_args
                    assert kwargs['chat_id'] == chat_id_active

def test_is_subscription_active_invalid_client(client_manager):
    assert client_manager.is_subscription_active("non_existent") is False

def test_update_subscription_invalid_client(client_manager):
    res = client_manager.update_subscription("non_existent", 30)
    assert res['status'] == 'error'
