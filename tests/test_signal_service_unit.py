import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from signal_service import SignalService, main
import asyncio
import sys

@pytest.fixture
def mock_strategy():
    mock = MagicMock()
    mock.generate_signals = AsyncMock(return_value=[('SWING', {
        'symbol': 'BTC/USD', 
        'direction': 'BUY',
        'entry_price': 60000,
        'sl': 59000,
        'tp0': 61000,
        'tp1': 62000,
        'tp2': 63000,
        'timeframe': 'H1',
        'trade_type': 'SWING',
        'quality_score': 0.8,
        'expected_hold': '4h'
    })])
    return mock

@pytest.fixture
def mock_telegram():
    mock = MagicMock()
    mock.broadcast_personalized_signal = AsyncMock()
    mock.bot = MagicMock()
    return mock

@pytest.mark.asyncio
async def test_signal_service_run(mock_strategy, mock_telegram):
    with patch('signal_service.generate_signals', new=mock_strategy.generate_signals), \
         patch('signal_service.TelegramService', return_value=mock_telegram):
        
        service = SignalService()
        
        with patch('signal_service.SignalFormatter.format_personalized_signal', return_value="Test Formatted"):
            await service.run(test_mode=True)
                
            assert mock_strategy.generate_signals.called
            assert mock_telegram.broadcast_personalized_signal.called

@pytest.mark.asyncio
async def test_signal_service_duplicate_skipped(mock_strategy, mock_telegram):
    service = SignalService()
    sig_data = mock_strategy.generate_signals.return_value[0][1]
    service._mark_sent(sig_data)
    
    with patch('signal_service.generate_signals', new=mock_strategy.generate_signals), \
         patch('signal_service.TelegramService', return_value=mock_telegram), \
         patch('builtins.print') as mock_print:
        
        await service.run(test_mode=True)
        assert not mock_telegram.broadcast_personalized_signal.called
        assert any("Skipped duplicate" in str(call) for call in mock_print.call_args_list)

@pytest.mark.asyncio
async def test_signal_service_no_signals_cycle(mock_telegram):
    service = SignalService()
    with patch('signal_service.generate_signals', new=AsyncMock(return_value=[])), \
         patch('signal_service.TelegramService', return_value=mock_telegram), \
         patch('builtins.print') as mock_print:
        
        await service.run(test_mode=True)
        assert any("No signals generated this cycle" in str(call) for call in mock_print.call_args_list)

@pytest.mark.asyncio
async def test_signal_service_error_handling(mock_telegram):
    with patch('signal_service.TelegramService', return_value=mock_telegram), \
         patch('builtins.print') as mock_print:
        
        service = SignalService()
        with patch('signal_service.generate_signals', AsyncMock(side_effect=Exception("Test Error"))):
            await service.run(test_mode=True)
            
        found = any("Error generating signals: Test Error" in str(call) for call in mock_print.call_args_list)
        assert found

@pytest.mark.asyncio
async def test_signal_service_deduplication(mock_telegram):
    with patch('signal_service.TelegramService', return_value=mock_telegram):
        service = SignalService()
        sig = {'symbol': 'EURUSD', 'direction': 'BUY', 'timeframe': 'H1'}
        
        h1 = service._signal_hash(sig)
        h2 = service._signal_hash(sig)
        assert h1 == h2
        
        assert not service._is_duplicate(sig)
        service._mark_sent(sig)
        assert service._is_duplicate(sig)
        
        with patch('signal_service.DEDUP_WINDOW_HOURS', -1):
            service._cleanup_old_signals()
            assert not service._is_duplicate(sig)

@pytest.mark.asyncio
async def test_signal_service_infinite_run_loop(mock_strategy, mock_telegram):
    with patch('signal_service.generate_signals', new=mock_strategy.generate_signals), \
         patch('signal_service.TelegramService', return_value=mock_telegram), \
         patch('signal_service.SignalFormatter.format_personalized_signal', return_value="Test Formatted"):
        
        service = SignalService()
        
        with patch('signal_service.asyncio.sleep', side_effect=[None, asyncio.CancelledError()]):
            try:
                await service.run(test_mode=False)
            except asyncio.CancelledError:
                pass

@pytest.mark.asyncio
async def test_signal_service_cycle_retry(mock_telegram):
    service = SignalService()
    with patch('signal_service.TelegramService', return_value=mock_telegram), \
         patch('builtins.print') as mock_print, \
         patch('signal_service.asyncio.sleep', side_effect=[asyncio.CancelledError()]):
        
        with patch.object(service, 'run_cycle', side_effect=Exception("Cycle Fail")):
            try:
                await service.run(test_mode=False)
            except asyncio.CancelledError:
                pass
            
            assert any("Cycle error: Cycle Fail" in str(call) for call in mock_print.call_args_list)

@pytest.mark.asyncio
async def test_signal_service_fatal_config():
    with patch('signal_service.TelegramService') as MockTG:
        mock_tg = MockTG.return_value
        mock_tg.bot = None 
        
        service = SignalService()
        with patch('builtins.print') as mock_print:
            await service.run(test_mode=True)
            assert any("FATAL: Telegram not configured" in str(call) for call in mock_print.call_args_list)

@pytest.mark.asyncio
async def test_signal_service_graceful_shutdown_loop(mock_strategy, mock_telegram):
    service = SignalService()
    with patch('signal_service.TelegramService', return_value=mock_telegram), \
         patch('signal_service.generate_signals', new=mock_strategy.generate_signals), \
         patch('signal_service.SignalFormatter.format_personalized_signal', return_value="Test"):
        
        def toggle_running(*args, **kwargs):
            service.running = False
            return None
            
        with patch('signal_service.asyncio.sleep', side_effect=toggle_running):
            await service.run(test_mode=False)
            assert not service.running

@pytest.mark.asyncio
async def test_signal_service_main_entry():
    with patch('signal_service.SignalService.run', new_callable=AsyncMock) as mock_run:
        with patch.object(sys, 'argv', ['signal_service.py', '--test']):
            await ss_main()
            mock_run.assert_called_with(test_mode=True)

async def ss_main():
    from signal_service import main as service_main
    await service_main()
