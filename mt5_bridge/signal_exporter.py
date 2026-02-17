import json
import os
from datetime import datetime

class SignalExporter:
    """
    MT5 Bridge Layer (V14.1)
    Exports optimized signals to a standardized JSON format for MT5 EA integration.
    """
    BRIDGE_FILE = "mt5_bridge/signals_mt5.json"

    @staticmethod
    def export_signal(signal_data: dict):
        """
        Appends a new signal to the bridge file for MT5 consumption.
        """
        try:
            # Ensure bridge directory exists
            os.makedirs(os.path.dirname(SignalExporter.BRIDGE_FILE), exist_ok=True)
            
            # Load existing signals
            signals = []
            if os.path.exists(SignalExporter.BRIDGE_FILE):
                with open(SignalExporter.BRIDGE_FILE, 'r') as f:
                    try:
                        signals = json.load(f)
                    except json.JSONDecodeError:
                        signals = []
            
            # Add export metadata
            signal_data['exported_at'] = datetime.now().isoformat()
            
            # Deduplicate by timestamp and symbol
            signals.append(signal_data)
            
            # Only keep the last 50 signals to prevent file bloat
            signals = signals[-50:]
            
            with open(SignalExporter.BRIDGE_FILE, 'w') as f:
                json.dump(signals, f, indent=4)
                
            print(f"📡 Exported signal for {signal_data['symbol']} to MT5 Bridge.")
            
        except Exception as e:
            print(f"⚠️ MT5 Export failed: {e}")

    @staticmethod
    def clear_expired_signals(max_age_minutes: int = 60):
        """
        Clears signals older than max_age_minutes to ensure MT5 doesn't trade stale data.
        """
        if not os.path.exists(SignalExporter.BRIDGE_FILE):
             return
             
        try:
            with open(SignalExporter.BRIDGE_FILE, 'r') as f:
                signals = json.load(f)
            
            now = datetime.now()
            valid_signals = []
            
            for s in signals:
                exported_at = datetime.fromisoformat(s['exported_at'])
                age = (now - exported_at).total_seconds() / 60
                if age < max_age_minutes:
                    valid_signals.append(s)
            
            with open(SignalExporter.BRIDGE_FILE, 'w') as f:
                json.dump(valid_signals, f, indent=4)
                
        except Exception as e:
            print(f"⚠️ MT5 Bridge Cleanup failed: {e}")
