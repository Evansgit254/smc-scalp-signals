import pandas as pd
import numpy as np
import random
import os

# --- CONFIGURATION ---
START_BALANCE = 50.0
MIN_LOT = 0.01
LOT_VALUE_PER_PIP = 0.10  # 0.01 lot = $0.10 per pip
SPREAD_COST_USD = 0.30    # Fixed cost per trade (approx 3 pips)
RISK_PERCENT = 0.02       # 2% Risk 
TARGET_BALANCE = 100.0    # Double the account
BANKRUPT_BALANCE = 10.0   # Critical level
ITERATIONS = 1000         # Monte Carlo runs

DATA_PATH = "research/backtest_trade_logs.csv"

def run_simulation():
    print(f"📈 STARTING $50 ACCOUNT SIMULATION (V23.1.3)")
    print("-" * 50)
    
    if not os.path.exists(DATA_PATH):
        print(f"❌ Error: {DATA_PATH} not found.")
        return

    df = pd.read_csv(DATA_PATH)
    trades_r = df['r'].tolist() # R-multiples from historical data
    
    results = []
    
    for i in range(ITERATIONS):
        balance = START_BALANCE
        # Shuffle trades for Monte Carlo
        current_trades = random.choices(trades_r, k=min(len(trades_r), 100))
        
        peak_balance = balance
        max_drawdown = 0.0
        
        for r in current_trades:
            # Calculate Risk Amount ($)
            # We risk 2% of balance, but minimum lot is 0.01
            # For simplicity, assume average SL is 20 pips ($2.00 risk @ 0.01 lot)
            risk_usd = max(2.0, balance * RISK_PERCENT)
            
            # PnL = (R-Multiple * Risk) - Spread
            pnl = (r * risk_usd) - SPREAD_COST_USD
            balance += pnl
            
            # Track Stats
            if balance > peak_balance:
                peak_balance = balance
            
            dd = (peak_balance - balance) / peak_balance * 100
            if dd > max_drawdown:
                max_drawdown = dd
                
            if balance < BANKRUPT_BALANCE:
                break
        
        results.append({
            'final': balance,
            'max_dd': max_drawdown,
            'success': balance >= TARGET_BALANCE,
            'blown': balance <= BANKRUPT_BALANCE
        })

    res_df = pd.DataFrame(results)
    
    win_rate = res_df['success'].mean() * 100
    blow_rate = res_df['blown'].mean() * 100
    avg_final = res_df['final'].mean()
    median_dd = res_df['max_dd'].median()
    
    print(f"✅ SIMULATION COMPLETE ({ITERATIONS} Runs)")
    print(f"📍 Starting Balance: ${START_BALANCE}")
    print(f"🎯 Target ($100):     {win_rate:.1f}% Chance")
    print(f"💀 Risk of Ruin:      {blow_rate:.1f}%")
    print(f"📊 Avg Final Balance: ${avg_final:.2f}")
    print(f"📉 Median Max DD:     {median_dd:.1f}%")
    print("-" * 50)
    
    if win_rate > 50:
        print("💡 VERDICT: The system is HIGHLY FEASIBLE for a $50 account.")
    else:
        print("💡 VERDICT: Recommended starting balance is $100+ for safer buffers.")

if __name__ == "__main__":
    run_simulation()
