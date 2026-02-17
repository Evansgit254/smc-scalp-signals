import time
import json
import os
import subprocess
import signal

def run_execution_audit():
    BRIDGE_FILE = "mt5_bridge/signals_mt5.json"
    
    # 1. Clean up bridge
    if os.path.exists(BRIDGE_FILE):
        os.remove(BRIDGE_FILE)
    
    os.makedirs(os.path.dirname(BRIDGE_FILE), exist_ok=True)
    
    # 2. Start the handler in a background process
    print("🚀 Starting MT5 Execution Handler Audit...")
    handler_process = subprocess.Popen(
        ["python3", "execution/mt5_handler.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    try:
        time.sleep(2) # Wait for handler to stabilize
        
        # 3. Inject a fresh signal
        print("📡 Injecting mock signal...")
        mock_signal = {
            "symbol": "GBPUSD=X",
            "direction": "SELL",
            "entry": 1.2650,
            "sl": 1.2680,
            "tp1": 1.2600,
            "lots": 0.1,
            "quality": "A",
            "executed": False,
            "exported_at": "2026-02-18T01:50:00"
        }
        
        with open(BRIDGE_FILE, 'w') as f:
            json.dump([mock_signal], f, indent=4)
            
        # 4. Wait for processing
        print("⏳ Waiting for handler to process signal...")
        time.sleep(3)
        
        # 5. Verify the signal was marked as executed
        with open(BRIDGE_FILE, 'r') as f:
            signals = json.load(f)
            if signals[-1].get('executed'):
                print("✅ SUCCESS: Signal detected and marked as executed.")
            else:
                print("❌ FAILURE: Signal was NOT marked as executed.")
                
    finally:
        # Terminate handler
        print("🛑 Cleaning up audit processes...")
        handler_process.terminate()
        try:
            handler_process.wait(timeout=5)
        except:
            handler_process.kill()

if __name__ == "__main__":
    run_execution_audit()
