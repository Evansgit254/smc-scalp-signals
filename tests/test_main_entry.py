import pytest
import sys
from unittest.mock import MagicMock, patch, AsyncMock
from main import main

@pytest.mark.asyncio
async def test_main_success():
    with patch('main.SignalService') as MockService:
        MockService.return_value.run_cycle = AsyncMock(return_value=(1, 1))
        with patch('builtins.print') as mock_print:
            await main()

            MockService.return_value.run_cycle.assert_awaited_once()
            assert any("Signal service cycle complete!" in str(call) for call in mock_print.call_args_list)

@pytest.mark.asyncio
async def test_main_no_signals():
    with patch('main.SignalService') as MockService:
        MockService.return_value.run_cycle = AsyncMock(return_value=(0, 0))
        with patch('builtins.print') as mock_print:
            await main()
            assert any("0/0 signals sent" in str(call) for call in mock_print.call_args_list)

@pytest.mark.asyncio
async def test_main_signal_processing_error():
    with patch('main.SignalService') as MockService:
        MockService.return_value.run_cycle = AsyncMock(return_value=(1, 0))
        with patch('builtins.print') as mock_print:
            await main()
            assert any("0/1 signals sent" in str(call) for call in mock_print.call_args_list)

@pytest.mark.asyncio
async def test_main_signal_send_failure():
    with patch('main.SignalService') as MockService:
        MockService.return_value.run_cycle = AsyncMock(return_value=(1, 0))
        with patch('builtins.print') as mock_print:
            await main()
            assert any("0/1 signals sent" in str(call) for call in mock_print.call_args_list)

@pytest.mark.asyncio
async def test_main_fatal_error():
    with patch('main.SignalService') as MockService:
        MockService.return_value.run_cycle = AsyncMock(side_effect=Exception("Fatal Error"))
        with patch('sys.exit') as mock_exit:
            await main()
            mock_exit.assert_called_with(1)
