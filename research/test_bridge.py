import json
import os
from datetime import datetime
from mt5_bridge.signal_exporter import SignalExporter

def test_bridge_export():
    mock_signal = {
        "symbol": "EURUSD=X",
        "direction": "BUY",
        "entry": 1.0850,
        "sl": 1.0830,
        "tp1": 1.0880,
        "tp2": 1.0910,
        "tp3": 1.0950,
        "lots": 0.05,
        "quality": "A",
        "regime": "TRENDING",
        "strategy": "CRT"
    }
    
    print("🚀 Simulating signal export...")
    SignalExporter.export_signal(mock_signal)
    
    # Verify file exists
    if os.path.exists("mt5_bridge/signals_mt5.json"):
        with open("mt5_bridge/signals_mt5.json", "r") as f:
            data = json.load(f)
            print(f"✅ Bridge file verified. Found {len(data)} signals.")
            print(f"📡 Latest signal: {data[-1]['symbol']} {data[-1]['direction']} at {data[-1]['entry']}")
    else:
        print("❌ Bridge file NOT found!")

if __name__ == "__main__":
    test_bridge_export()
