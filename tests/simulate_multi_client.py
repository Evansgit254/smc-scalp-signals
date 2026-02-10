"""
Simulation script for Guidance-Based Risk Management (V11.1)

Verifies that signals are sent with "Minimum Recommended Balance" warnings
instead of being blocked.
"""
import asyncio
from core.client_manager import ClientManager
from core.signal_formatter import SignalFormatter
from core.filters.risk_manager import RiskManager
import os

async def simulate_guidance():
    print("🧪 SIMULATING GUIDANCE-BASED RISK DELIVERY")
    print("=" * 60)
    
    # 1. Setup Mock Clients
    db_path = "database/test_guidance.db"
    if os.path.exists(db_path):
        os.remove(db_path)
        
    manager = ClientManager(db_path)
    
    # Client A: Small account ($50)
    manager.register_client("CHAT_SMALL_50", 50.0)
    # Client B: Medium account ($200)
    manager.register_client("CHAT_MED_200", 200.0)
    # Client C: Large account ($2000)
    manager.register_client("CHAT_LARGE_2000", 2000.0)
    
    clients = manager.get_all_active_clients()
    
    # 2. Mock High-Risk Signal (Gold with 10 point SL = 100 pips)
    # 0.01 lot on Gold with 100 pips = $10 risk. 
    # For $50 account, this is 20% risk (High Risk).
    # For $200 account, this is 5% risk (Borderline).
    # For $2000 account, this is 0.5% risk (Safe).
    
    gold_signal = {
        'symbol': 'XAUUSD=X',
        'direction': 'BUY',
        'entry_price': 2600.0,
        'sl': 2590.0, 
        'tp0': 2615.0,
        'tp1': 2630.0,
        'tp2': 2650.0,
        'timeframe': 'H1',
        'trade_type': 'SWING',
        'quality_score': 7.5,
        'confidence': 1.4,
        'regime': 'TRENDING'
    }
    
    print("\n📡 BROADCASTING HIGH-RISK GOLD SIGNAL...")
    print("-" * 60)
    
    for client in clients:
        print(f"\n📱 [OUTPUT] To: {client['telegram_chat_id']} (${client['account_balance']})")
        formatted = SignalFormatter.format_personalized_signal(gold_signal, client)
        
        # Extract the personalized banner section for verification
        banner_lines = [line for line in formatted.split('\n') if any(x in line for x in ["Balance:", "Risk:", "Min Balance", "WARNING"])]
        for line in banner_lines:
            print(f"   {line.strip()}")
            
        # Verify no mention of "SKIPPED" in the full output
        if "SKIPPED" in formatted:
            print("   ❌ ERROR: Signal still contains 'SKIPPED' text!")
        else:
            print("   ✅ SUCCESS: Signal delivered with guidance.")

    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)
    print("\n" + "=" * 60)

if __name__ == "__main__":
    asyncio.run(simulate_guidance())
