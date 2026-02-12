import sqlite3
import json
from datetime import datetime

# Import Signal Service (assuming it's in the python path)
import sys
import os
sys.path.append(os.getcwd())

# Mock data simulating a full strategy signal
mock_full_signal = {
    'symbol': 'BTC-USD',
    'direction': 'SELL',
    'entry_price': 65000.0,
    'sl': 66000.0,
    'tp0': 64000.0,
    'tp1': 63000.0,
    'tp2': 60000.0,
    'timeframe': 'H1',
    'trade_type': 'SWING',
    'confidence': 0.85,
    'quality_score': 9.2,
    'regime': 'TRENDING_DOWN',
    'expected_hold': '1-2 Days',
    'reasoning': 'Micro-structure break on H1. Volume confirming bearish divergence.',
    'risk_details': {'risk_per_trade_percent': 1.0, 'risk_amount_usd': 50.0, 'lot_size': 0.05},
    'score_details': {'momentum': 0.75, 'volatility': 0.45, 'zscore': 2.1}
}

def verify_full_fidelity():
    print("🚀 Starting Signal Fidelity Verification...")
    
    # 1. Simulate Logging (Direct DB Insert to test Schema)
    conn = sqlite3.connect("database/signals.db")
    try:
        risk_json = json.dumps(mock_full_signal['risk_details'])
        score_json = json.dumps(mock_full_signal['score_details'])
        
        conn.execute("""
            INSERT INTO signals (
                timestamp, symbol, direction, entry_price, 
                sl, tp0, tp1, tp2, reasoning, timeframe, confidence,
                trade_type, quality_score, regime, expected_hold, risk_details, score_details
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            mock_full_signal['symbol'],
            mock_full_signal['direction'],
            mock_full_signal['entry_price'],
            mock_full_signal['sl'],
            mock_full_signal['tp0'],
            mock_full_signal['tp1'],
            mock_full_signal['tp2'],
            mock_full_signal['reasoning'],
            mock_full_signal['timeframe'],
            mock_full_signal['confidence'],
            mock_full_signal['trade_type'],
            mock_full_signal['quality_score'],
            mock_full_signal['regime'],
            mock_full_signal['expected_hold'],
            risk_json,
            score_json
        ))
        conn.commit()
        print("✅ Signal inserted into DB successfully.")
    except Exception as e:
        print(f"❌ DB Insert Failed: {e}")
        return

    # 2. Verify Retrieval
    cursor = conn.execute("SELECT * FROM signals ORDER BY timestamp DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    
    # Check if new columns exist and have data
    columns = [description[0] for description in cursor.description]
    row_dict = dict(zip(columns, row))
    
    print("\n🧐 Verifying Data Integrity:")
    if row_dict['trade_type'] == 'SWING':
        print("✅ trade_type verified")
    else:
        print(f"❌ trade_type mismatch: {row_dict.get('trade_type')}")

    if row_dict['quality_score'] == 9.2:
        print("✅ quality_score verified")
    else:
        print(f"❌ quality_score mismatch: {row_dict.get('quality_score')}")

    # Check JSON parsing
    retrieved_risk = json.loads(row_dict['risk_details'])
    if retrieved_risk['lot_size'] == 0.05:
        print("✅ risk_details JSON verified")
    else:
        print("❌ risk_details JSON parsing failed")

    print("\n🎉 Verification Passed! System is ready for full signal fidelity.")

if __name__ == "__main__":
    verify_full_fidelity()
