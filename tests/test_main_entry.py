import pytest
import sys
from unittest.mock import MagicMock, patch, AsyncMock
from main import main

@pytest.mark.asyncio
async def test_main_success():
    mock_signals = [('SWING', {'symbol': 'BTC/USD', 'direction': 'BUY'})]
    
    with patch('main.generate_signals', new=AsyncMock(return_value=mock_signals)), \
         patch('main.TelegramService') as MockTelegram, \
         patch('main.SignalFormatter') as MockFormatter, \
         patch('main.asyncio.sleep', new=AsyncMock()):
        
        mock_tg_instance = MockTelegram.return_value
        mock_tg_instance.bot = MagicMock()
        mock_tg_instance.chat_id = "123"
        mock_tg_instance.send_signal = AsyncMock(return_value=True)
        
        MockFormatter.format_signal.return_value = "Test Formatted Signal"
        
        with patch('builtins.print') as mock_print:
            await main()
            
            assert mock_tg_instance.send_signal.called
            assert any("Signal generation complete!" in str(call) for call in mock_print.call_args_list)

@pytest.mark.asyncio
async def test_main_no_signals():
    with patch('main.generate_signals', new=AsyncMock(return_value=[])):
        with patch('builtins.print') as mock_print:
            await main()
            assert any("No signals generated at this time." in str(call) for call in mock_print.call_args_list)

@pytest.mark.asyncio
async def test_main_signal_processing_error():
    mock_signals = [('SWING', {'symbol': 'FAIL', 'direction': 'BUY'})]
    
    with patch('main.generate_signals', new=AsyncMock(return_value=mock_signals)), \
         patch('main.TelegramService') as MockTelegram, \
         patch('main.SignalFormatter') as MockFormatter, \
         patch('main.asyncio.sleep', new=AsyncMock()):
        
        mock_tg_instance = MockTelegram.return_value
        mock_tg_instance.bot = MagicMock()
        mock_tg_instance.chat_id = "123"
        
        # Force format_signal to raise an error
        MockFormatter.format_signal.side_effect = Exception("Format Fail")
        
        with patch('builtins.print') as mock_print:
            await main()
            assert any("Error processing signal: Format Fail" in str(call) for call in mock_print.call_args_list)

@pytest.mark.asyncio
async def test_main_signal_send_failure():
    mock_signals = [('SWING', {'symbol': 'FAIL', 'direction': 'BUY'})]
    
    with patch('main.generate_signals', new=AsyncMock(return_value=mock_signals)), \
         patch('main.TelegramService') as MockTelegram, \
         patch('main.SignalFormatter') as MockFormatter, \
         patch('main.asyncio.sleep', new=AsyncMock()):
        
        mock_tg_instance = MockTelegram.return_value
        mock_tg_instance.bot = MagicMock()
        mock_tg_instance.chat_id = "123"
        mock_tg_instance.send_signal = AsyncMock(return_value=False)
        
        with patch('builtins.print') as mock_print:
            await main()
            assert any("Failed to send SWING signal" in str(call) for call in mock_print.call_args_list)

@pytest.mark.asyncio
async def test_main_fatal_error():
    with patch('main.generate_signals', new=AsyncMock(side_effect=Exception("Fatal Error"))):
        with patch('sys.exit') as mock_exit:
            await main()
            mock_exit.assert_called_with(1)
