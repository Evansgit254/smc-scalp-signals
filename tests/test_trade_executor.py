import pytest
import asyncio
from unittest.mock import patch, MagicMock
from core.trade_executor import TradeExecutor

@pytest.fixture
def executor():
    ex = TradeExecutor()
    ex.paper_mode = True
    ex.auto_trade = True
    return ex

@pytest.mark.asyncio
async def test_paper_trade_execution(executor):
    signal = {
        "symbol": "EURUSD=X",
        "direction": "BUY",
        "entry_price": 1.0550,
        "lot_size": 0.05,
        "sl": 1.0500,
        "tp1": 1.0600,
        "timestamp": "2026-04-20T12:00:00Z"
    }
    
    with patch("core.trade_executor._executor", executor):
        with patch("config.config.MT5_SYMBOL_SUFFIX", "c"): # Ensure suffix test passes
            with patch.object(executor, "_log_paper_trade") as mock_log:
                result = await executor.execute_trade(signal)
            
            assert result["status"] == "paper"
            assert result["symbol"] == "EURUSDc"  # Testing the suffix addition
            assert result["direction"] == "BUY"
            mock_log.assert_called_once()

@pytest.mark.asyncio
async def test_auto_trade_disabled(executor):
    executor.auto_trade = False
    
    signal = {"symbol": "EURUSD=X"}
    result = await executor.execute_trade(signal)
    
    assert result["status"] == "skipped"
    assert "MT5_AUTO_TRADE=false" in result["reason"]

@pytest.mark.asyncio
async def test_missing_entry_price_blocks_execution(executor):
    signal = {
        "symbol": "EURUSD=X",
        "direction": "BUY",
        "lot_size": 0.05,
        "sl": 1.0500,
        "tp1": 1.0600,
    }

    with patch.object(executor, "_persist_execution_state") as mock_persist:
        result = await executor.execute_trade(signal)

    assert result["status"] == "error"
    assert "entry_price" in result["reason"]
    mock_persist.assert_called_once()
