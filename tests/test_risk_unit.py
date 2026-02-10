import pytest
import pandas as pd
import sqlite3
import os
from core.filters.risk_manager import RiskManager
from unittest.mock import patch, MagicMock

@pytest.fixture
def mock_db(tmp_path):
    db_path = tmp_path / "test_signals.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE signals (timestamp TEXT, status TEXT, r_multiple REAL)")
    conn.close()
    return str(db_path)

def test_calculate_lot_size_basic():
    # Test EURUSD lot calculation (0.01 lot per $0.10 pip)
    # Account: $50, Risk: 2% ($1.00)
    # SL: 10 pips -> 10 * 0.10 = $1.00 -> 0.01 lot
    res = RiskManager.calculate_lot_size("EURUSD=X", 1.1010, 1.1000, db_path="non_existent.db")
    assert res['lots'] == 0.01
    assert res['risk_cash'] == 1.0
    assert res['risk_percent'] == 2.0

def test_calculate_lot_size_jpy():
    # USDJPY: 100 multiplier for pips
    res = RiskManager.calculate_lot_size("USDJPY=X", 150.10, 150.00, db_path="non_existent.db")
    # 0.10 dist = 10 pips. JPY pip val approx 0.065.
    # 1.0 / (0.065 * 10) * 0.01 = 0.0153 -> 0.02
    assert res['lots'] >= 0.01
    assert 'lots' in res

def test_calculate_lot_size_gold_indices():
    # Gold
    res = RiskManager.calculate_lot_size("GC=F", 2005, 2000, db_path="non_existent.db")
    assert 'lots' in res
    # Nasdaq
    res = RiskManager.calculate_lot_size("IXIC", 15010, 15000, db_path="non_existent.db")
    assert 'lots' in res

def test_calculate_lot_size_streaks(mock_db):
    # Test Win Streak (multiplier 1.25)
    conn = sqlite3.connect(mock_db)
    for i in range(3):
        conn.execute("INSERT INTO signals (timestamp, status) VALUES (?, 'WIN')", (f"2026-01-0{i}",))
    conn.commit()
    conn.close()
    
    res_base = RiskManager.calculate_lot_size("EURUSD=X", 1.1001, 1.1000, db_path="none.db")
    res_streak = RiskManager.calculate_lot_size("EURUSD=X", 1.1001, 1.1000, db_path=mock_db)
    assert res_streak['lots'] > res_base['lots']

    # Test Loss Streak (multiplier 0.75)
    conn = sqlite3.connect(mock_db)
    conn.execute("DELETE FROM signals")
    for i in range(2):
        conn.execute("INSERT INTO signals (timestamp, status) VALUES (?, 'LOSS')", (f"2026-01-0{i}",))
    conn.commit()
    conn.close()
    
    res_loss = RiskManager.calculate_lot_size("EURUSD=X", 1.1001, 1.1000, db_path=mock_db)
    assert res_loss['lots'] < res_base['lots']

    # Test Breakeven (Covers Line 49 'else: break')
    conn = sqlite3.connect(mock_db)
    conn.execute("DELETE FROM signals")
    conn.execute("INSERT INTO signals (timestamp, status) VALUES ('2026-01-01', 'BREAKEVEN')")
    conn.commit()
    conn.close()
    res_be = RiskManager.calculate_lot_size("EURUSD=X", 1.1001, 1.1000, db_path=mock_db)
    assert res_be['lots'] == res_base['lots'] # No streak change

def test_calculate_lot_size_exceptions():
    # Test DB error path (invalid SQL)
    res = RiskManager.calculate_lot_size("EURUSD=X", 1.1, 1.0, db_path="/dev/null")
    assert res['lots'] == 0.01 # Should default gracefully

def test_calculate_lot_size_jpy_and_others():
    # JPY
    res = RiskManager.calculate_lot_size("USDJPY=X", 150.01, 150.00, db_path="none.db")
    assert res['pips'] == 1.0
    # Gold
    res = RiskManager.calculate_lot_size("GC=F", 2001, 2000, db_path="none.db")
    assert res['pips'] == 1.0

def test_calculate_layers():
    layers = RiskManager.calculate_layers(0.1, 1.1000, 1.0900, "BUY")
    assert len(layers) == 3
    assert layers[0]['lots'] == 0.04 # 40%
    assert layers[1]['lots'] == 0.04
    assert layers[2]['lots'] == 0.02 # 20%
    
    # Sell layers
    layers_sell = RiskManager.calculate_layers(0.1, 1.1000, 1.1100, "SELL")
    assert layers_sell[1]['price'] > 1.1000 # Pullback for sell is higher

def test_calculate_layers_a_plus():
    layers = RiskManager.calculate_layers(0.1, 1.1000, 1.0900, "BUY", quality="A+")
    assert layers[0]['lots'] == 0.05 # 50% for A+
    assert "50%" in layers[0]['label']

def test_calculate_kelly_fraction(mock_db):
    # Insert some WIN/LOSS trades
    conn = sqlite3.connect(mock_db)
    conn.execute("CREATE TABLE IF NOT EXISTS signals (status TEXT, r_multiple REAL, timestamp TEXT)")
    for _ in range(10):
        conn.execute("INSERT INTO signals (status, r_multiple, timestamp) VALUES ('WIN', 2.0, '2026-01-01')")
        conn.execute("INSERT INTO signals (status, r_multiple, timestamp) VALUES ('LOSS', 1.0, '2026-01-02')")
    conn.commit()
    conn.close()
    
    fraction = RiskManager._calculate_kelly_fraction(mock_db)
    assert 0.0 <= fraction <= 0.1 # Capped at 10%
    assert fraction > 0

def test_calculate_optimal_rr():
    res = RiskManager.calculate_optimal_rr(8.5, "TRENDING")
    assert res['tp1_rr'] > 1.5 # Should be boosted
    
    res_choppy = RiskManager.calculate_optimal_rr(5.0, "CHOPPY")
    assert res_choppy['tp1_rr'] < 1.5 # Should be reduced
