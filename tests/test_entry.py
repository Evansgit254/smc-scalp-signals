import pandas as pd
import pytest
# Legacy test - strategy module removed (now strategies/)
pytest.skip("Legacy strategy module removed", allow_module_level=True)
# from strategy.entry import EntryLogic

def test_calculate_levels_buy():
    # Mock data
    df = pd.DataFrame({'close': [1.0500]})
    direction = "BUY"
    sweep_level = 1.0490
    atr = 0.0010
    
    levels = EntryLogic.calculate_levels(df, direction, sweep_level, atr)
    
    # SL should be slightly below sweep level
    assert levels['sl'] < sweep_level
    # TP1 should be 1.0500 + 0.0010 = 1.0510
    assert abs(levels['tp1'] - 1.0510) < 0.00001
    # TP2 should be 1.0500 + 0.0018 = 1.0518 (Config 1.8x)
    assert abs(levels['tp2'] - 1.0518) < 0.00001

def test_calculate_levels_sell():
    df = pd.DataFrame({'close': [1.0500]})
    direction = "SELL"
    sweep_level = 1.0510
    atr = 0.0010
    
    levels = EntryLogic.calculate_levels(df, direction, sweep_level, atr)
    
    assert levels['sl'] > sweep_level
    assert abs(levels['tp1'] - 1.0490) < 0.00001
    assert abs(levels['tp2'] - 1.0482) < 0.00001

def test_check_pullback_no_data():
    df = pd.DataFrame()
    assert EntryLogic.check_pullback(df, "BUY") is None
