import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from app.interactive_bot import InteractiveBot
import sqlite3

@pytest.fixture
def mock_update():
    update = MagicMock()
    update.effective_chat.id = 12345
    update.message.reply_text = AsyncMock()
    update.message.reply_html = AsyncMock()
    return update

@pytest.fixture
def mock_context():
    context = MagicMock()
    context.args = []
    return context

@pytest.mark.asyncio
async def test_bot_start(mock_update, mock_context):
    bot = InteractiveBot("token")
    await bot.start(mock_update, mock_context)
    assert mock_update.message.reply_text.called
    assert "Welcome" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_bot_register_success(mock_update, mock_context):
    bot = InteractiveBot("token")
    mock_context.args = ["500"]
    with patch.object(bot.manager, 'register_client', return_value={'status': 'registered'}) as mock_reg:
        await bot.register(mock_update, mock_context)
        assert mock_reg.called
        assert "Registered successfully" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_bot_register_invalid(mock_update, mock_context):
    bot = InteractiveBot("token")
    mock_context.args = ["invalid"]
    await bot.register(mock_update, mock_context)
    assert "Invalid balance" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_bot_subscribe(mock_update, mock_context):
    bot = InteractiveBot("token")
    await bot.subscribe(mock_update, mock_context)
    assert mock_update.message.reply_html.called
    assert "UPGRADE TO QUANT PREMIUM" in mock_update.message.reply_html.call_args[0][0]

@pytest.mark.asyncio
async def test_bot_status_not_registered(mock_update, mock_context):
    bot = InteractiveBot("token")
    with patch.object(bot.manager, 'get_client', return_value=None):
        await bot.status(mock_update, mock_context)
        assert "not registered" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_bot_status_active(mock_update, mock_context, tmp_path):
    bot = InteractiveBot("token")
    db_path = str(tmp_path / "clients_test.db")
    # Initialize DB for status check
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE clients (telegram_chat_id TEXT, subscription_expiry TEXT, subscription_tier TEXT)")
    conn.execute("INSERT INTO clients VALUES ('12345', '2026-01-01', 'GOLD')")
    conn.commit()
    conn.close()
    
    with patch.object(bot.manager, 'get_client', return_value={'balance': 100}), \
         patch.object(bot.manager, 'is_subscription_active', return_value=True), \
         patch('sqlite3.connect', return_value=sqlite3.connect(db_path)):
        await bot.status(mock_update, mock_context)
        assert "ACTIVE" in mock_update.message.reply_html.call_args[0][0]

@pytest.mark.asyncio
async def test_bot_update_balance(mock_update, mock_context):
    bot = InteractiveBot("token")
    mock_context.args = ["1000"]
    with patch.object(bot.manager, 'update_balance', return_value={'status': 'success'}):
        await bot.update_balance(mock_update, mock_context)
        assert "Balance updated" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_bot_settings_not_registered(mock_update, mock_context):
    bot = InteractiveBot("token")
    with patch.object(bot.manager, 'get_client', return_value=None):
        await bot.settings(mock_update, mock_context)
        assert "not registered" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_bot_settings(mock_update, mock_context):
    bot = InteractiveBot("token")
    with patch.object(bot.manager, 'get_client', return_value={'account_balance': 500.0, 'risk_percent': 2.0}), \
         patch.object(bot.manager, 'is_subscription_active', return_value=True):
        await bot.settings(mock_update, mock_context)
        assert "Balance:</b> $500.00" in mock_update.message.reply_html.call_args[0][0]

@pytest.mark.asyncio
async def test_bot_help(mock_update, mock_context):
    bot = InteractiveBot("token")
    await bot.help(mock_update, mock_context)
    assert "COMMANDS:" in mock_update.message.reply_text.call_args[0][0]

def test_bot_set_up_handlers():
    bot = InteractiveBot("token")
    mock_app = MagicMock()
    bot._set_up_handlers(mock_app)
    assert mock_app.add_handler.called
    assert mock_app.add_handler.call_count >= 7

@pytest.mark.asyncio
async def test_bot_register_no_args(mock_update, mock_context):
    bot = InteractiveBot("token")
    mock_context.args = []
    await bot.register(mock_update, mock_context)
    assert "Usage: /register" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_bot_register_already_exists(mock_update, mock_context):
    bot = InteractiveBot("token")
    mock_context.args = ["500"]
    with patch.object(bot.manager, 'register_client', return_value={'status': 'error', 'message': 'Already exists'}):
        await bot.register(mock_update, mock_context)
        assert "Already exists" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_bot_update_balance_no_args(mock_update, mock_context):
    bot = InteractiveBot("token")
    mock_context.args = []
    await bot.update_balance(mock_update, mock_context)
    assert "Usage: /update_balance" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_bot_update_balance_error(mock_update, mock_context):
    bot = InteractiveBot("token")
    mock_context.args = ["1000"]
    with patch.object(bot.manager, 'update_balance', return_value={'status': 'error', 'message': 'Fail'}):
        await bot.update_balance(mock_update, mock_context)
        assert "Error: Fail" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_bot_update_balance_invalid(mock_update, mock_context):
    bot = InteractiveBot("token")
    mock_context.args = ["invalid"]
    await bot.update_balance(mock_update, mock_context)
    assert "Invalid balance format" in mock_update.message.reply_text.call_args[0][0]

def test_bot_run():
    bot = InteractiveBot("token")
    with patch('app.interactive_bot.Application.builder') as mock_builder:
        mock_app = mock_builder.return_value.token.return_value.build.return_value
        bot.run()
        assert mock_app.run_polling.called
