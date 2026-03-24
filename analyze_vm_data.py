import sqlite3
import pandas as pd
import numpy as np

def analyze():
    # Connect to the VM database
    conn = sqlite3.connect("/home/evans/smc-scalp-signals/database/signals_vm.db")
    df = pd.read_sql_query("SELECT * FROM signals", conn)
    conn.close()

    print(f"--- Forensic Performance Audit (Total Signals: {len(df)}) ---")
    
    # Pre-process
    df['is_win'] = df['result'].isin(['TP1', 'TP2', 'TP3'])
    df['is_loss'] = df['result'] == 'SL'
    df['is_open'] = df['result'] == 'OPEN'
    
    # 1. High Level Win Rate
    total_closed = len(df[~df['is_open']])
    total_wins = df['is_win'].sum()
    wr = (total_wins / total_closed * 100) if total_closed > 0 else 0
    print(f"Overall Win Rate: {wr:.2f}% (Total Closed: {total_closed})")

    # 2. Performance by Symbol (Min 5 trades)
    symbol_stats = df[~df['is_open']].groupby('symbol').agg(
        total=('id', 'count'),
        win_rate=('is_win', 'mean')
    ).reset_index()
    symbol_stats['win_rate'] *= 100
    print("\nSymbol Performance Metric (Min 5 signals):")
    print(symbol_stats[symbol_stats['total'] >= 5].sort_values('win_rate', ascending=True).to_string(index=False))

    # 3. Regime Analysis (Crucial for the "Hedge")
    regime_stats = df[~df['is_open']].groupby('regime').agg(
        total=('id', 'count'),
        win_rate=('is_win', 'mean')
    ).reset_index()
    regime_stats['win_rate'] *= 100
    print("\nRegime Performance Audit:")
    print(regime_stats.to_string(index=False))

    # 4. BTC-USD Specific Analysis
    btc_df = df[(df['symbol'] == 'BTC-USD') & (~df['is_open'])]
    if not btc_df.empty:
        print("\n--- BTC-USD Forensic Deep Dive ---")
        print(f"BTC Win Rate: {btc_df['is_win'].mean()*100:.2f}% (Total: {len(btc_df)})")
        print("BTC Performance by Regime:\n", btc_df.groupby(['regime']).agg(count=('id', 'count'), wr=('is_win', 'mean')))
        print("BTC Average Quality (Wins vs Losses):")
        print(f"  - Wins: {btc_df[btc_df['is_win']]['quality_score'].mean():.2f}")
        print(f"  - Losses: {btc_df[btc_df['is_loss']]['quality_score'].mean():.2f}")

    # 5. Potential Hedge Filter: Quality Score Cutoff
    print("\n--- Hedge Simulation (Quality Score Cutoff) ---")
    for cutoff in [5.0, 6.0, 7.0, 8.0]:
        filtered = df[(~df['is_open']) & (df['quality_score'] >= cutoff)]
        if len(filtered) > 0:
            fwr = filtered['is_win'].mean() * 100
            print(f"Cutoff {cutoff:0.1f} | Trade Count: {len(filtered):3d} | New WR: {fwr:.2f}%")

if __name__ == "__main__":
    analyze()
