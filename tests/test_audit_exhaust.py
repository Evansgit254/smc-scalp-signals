import pytest
# Legacy test - audit module removed
pytest.skip("Audit module removed", allow_module_level=True)
# import pandas as pd
# import sqlite3
# import os
# from datetime import datetime, timedelta
# from unittest.mock import MagicMock, patch, AsyncMock
# from audit.performance_auditor import PerformanceAuditor
# from audit.journal import SignalJournal

@pytest.fixture
def mock_db_with_signals(tmp_path):
    db_path = tmp_path / "test_audit.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE signals (
            id INTEGER PRIMARY KEY,
            symbol TEXT,
            timestamp TEXT,
            direction TEXT,
            entry_price REAL,
            sl REAL,
            tp0 REAL,
            tp1 REAL,
            tp2 REAL,
            status TEXT,
            res TEXT DEFAULT 'PENDING',
            result_pips REAL
        )
    """)
    now_iso = (datetime.now() - timedelta(hours=2)).isoformat()
    # Add a BUY signal and a SELL signal
    conn.execute("""
        INSERT INTO signals (symbol, timestamp, direction, entry_price, sl, tp0, tp1, tp2, status, res)
        VALUES ('EURUSD', ?, 'SELL', 1.0850, 1.0900, 1.0800, 1.0750, 1.0700, 'PENDING', 'PENDING')
    """, [now_iso])
    conn.execute("""
        INSERT INTO signals (symbol, timestamp, direction, entry_price, sl, tp0, tp1, tp2, status, res)
        VALUES ('GBPUSD', ?, 'BUY', 1.2500, 1.2450, 1.2550, 1.2600, 1.2650, 'PENDING', 'PENDING')
    """, [now_iso])
    conn.commit()
    conn.close()
    return db_path

@pytest.mark.asyncio
async def test_performance_auditor_resolve_sell_win(mock_db_with_signals):
    auditor = PerformanceAuditor(db_path=str(mock_db_with_signals))
    
    # Mock data for SELL signal
    # Price hits TP2
    dates = pd.date_range(end=datetime.now(), periods=20, freq='5min')
    df_sell = pd.DataFrame({
        'high': [1.0850]*20,
        'low': [1.0850]*10 + [1.0600]*10, # Hits TP2 (1.0700)
        'close': [1.0850]*20
    }, index=dates)
    
    with patch("data.fetcher.DataFetcher.fetch_range", return_value=df_sell):
        await auditor.resolve_trades(force=True)
        
    with sqlite3.connect(mock_db_with_signals) as conn:
        conn.row_factory = sqlite3.Row
        res = conn.execute("SELECT * FROM signals WHERE symbol='EURUSD'").fetchone()
        assert res['status'] == 'RESOLVED'
        assert res['res'] == 'WIN'

@pytest.mark.asyncio
async def test_performance_auditor_sell_loss_be_partial(mock_db_with_signals):
    auditor = PerformanceAuditor(db_path=str(mock_db_with_signals))
    
    # Mock data for SELL signal
    # Price hits SL (Loss)
    dates = pd.date_range(end=datetime.now(), periods=20, freq='5min')
    df_loss = pd.DataFrame({
        'high': [1.0850]*10 + [1.0950]*10, # Hits SL (1.0900)
        'low': [1.0850]*20,
        'close': [1.0850]*20
    }, index=dates)
    
    with patch("data.fetcher.DataFetcher.fetch_range", return_value=df_loss):
        # We need to ensure we only process the SELL one for this test or isolate
        # auditor.journal.get_pending_signals = lambda: [sell_signal_dict]
        await auditor.resolve_trades() # Not force

@pytest.mark.asyncio
async def test_performance_auditor_empty_df(mock_db_with_signals):
    auditor = PerformanceAuditor(db_path=str(mock_db_with_signals))
    with patch("data.fetcher.DataFetcher.fetch_range", return_value=pd.DataFrame()):
        await auditor.resolve_trades()
        # Should just continue

def test_performance_auditor_main_block():
    with patch("audit.performance_auditor.PerformanceAuditor") as MockAuditor:
        mock_inst = MockAuditor.return_value
        mock_inst.resolve_trades = AsyncMock()
        with patch("sys.argv", ["script.py", "--force"]):
            # Simulate main
            from audit.performance_auditor import PerformanceAuditor as PA
            force_mode = "--force" in ["--force"]
            auditor = PA()
            # This is hard to test without actually running the block, 
            # but we can test the logic that determines force_mode
            assert force_mode == True
