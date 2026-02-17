import time
import json
import os
from datetime import datetime
try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None
    print("⚠️ MetaTrader5 library not found. Running in LOG-ONLY mode.")

from config.config import MT5_LOGIN, MT5_PASSWORD, MT5_SERVER, SPREAD_PIPS, SLIPPAGE_PIPS
from core.filters.risk_manager import RiskManager

class MT5Handler:
    """
    MT5 Execution Layer (V16.1)
    Bridges Alpha Core signals to live MT5 orders.
    """
    BRIDGE_FILE = "mt5_bridge/signals_mt5.json"

    def __init__(self):
        self.connected = False
        if mt5:
            self.connect()

    def connect(self):
        if not mt5.initialize(login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER):
            print(f"❌ MT5 Initialization failed: {mt5.last_error()}")
            self.connected = False
        else:
            print(f"✅ Connected to MT5 Account: {MT5_LOGIN}")
            self.connected = True

    def run(self):
        print("🔄 MT5 Monitor active. Watching for signals...")
        while True:
            try:
                if os.path.exists(self.BRIDGE_FILE):
                    with open(self.BRIDGE_FILE, 'r') as f:
                        signals = json.load(f)
                    
                    if signals:
                        # Process the latest signal that hasn't been executed
                        latest_signal = signals[-1]
                        if not latest_signal.get('executed'):
                            self.execute_signal(latest_signal)
                            
                            # Mark as executed in the JSON file
                            latest_signal['executed'] = True
                            with open(self.BRIDGE_FILE, 'w') as f:
                                json.dump(signals, f, indent=4)
                
                time.sleep(1) # Poll every second
            except Exception as e:
                print(f"⚠️ Monitor Error: {e}")
                time.sleep(5)

    def execute_signal(self, signal):
        symbol = signal['symbol'].replace("=X", "") # Normalize for MT5
        direction = signal['direction']
        entry = signal['entry']
        sl = signal['sl']
        tps = [signal.get('tp1'), signal.get('tp2'), signal.get('tp3')]
        
        print(f"📡 Processing {direction} signal for {symbol}...")

        if not self.connected and mt5:
            self.connect()
            if not self.connected:
                print("❌ Aborting: MT5 not connected.")
                return

        # Pre-Flight: Live Spread Check
        if mt5:
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                print(f"❌ Symbol {symbol} not found in MT5.")
                return
            
            if not symbol_info.visible:
                mt5.symbol_select(symbol, True)
            
            # Verify Spread is within SATP limits
            live_spread = (symbol_info.ask - symbol_info.bid)
            # Normalize spread to pips
            if "JPY" in symbol: live_spread_pips = live_spread * 100
            else: live_spread_pips = live_spread * 10000
            
            if live_spread_pips > (SPREAD_PIPS + SLIPPAGE_PIPS) * 1.5:
                print(f"⚠️ High Spread Detected ({live_spread_pips} pips). Skipping for safety.")
                return

        # Execute Market Order
        if mt5:
            order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
            price = mt5.symbol_info_tick(symbol).ask if direction == "BUY" else mt5.symbol_info_tick(symbol).bid
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": signal['lots'],
                "type": order_type,
                "price": price,
                "sl": sl,
                "tp": tps[0] if tps[0] else 0.0,
                "magic": 123456,
                "comment": "AlphaCore V16.1",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                print(f"❌ Order failed: {result.comment} (Code: {result.retcode})")
            else:
                print(f"💰 Order Executed: {direction} {signal['lots']} {symbol} at {result.price}")
        else:
            print(f"📝 [MOCK] Executed {direction} {signal['lots']} {symbol} at {entry}")

if __name__ == "__main__":
    handler = MT5Handler()
    handler.run()
