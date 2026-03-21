import sqlite3
import pandas as pd
import numpy as np
import itertools

DB_PATH = "database/signals_vm.db"

def load_signals():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT id, symbol, direction, entry_price, sl, tp0, tp1, tp2,
               quality_score, regime, trade_type, result, timeframe
        FROM signals
        WHERE result IN ('SL', 'TP1', 'TP2', 'TP3')
          AND entry_price > 0 AND sl > 0
    """, conn)
    conn.close()
    
    df['sl_dist'] = abs(df['entry_price'] - df['sl'])
    df['tp1_dist'] = abs(df['tp1'] - df['entry_price'])
    df['is_win'] = df['result'].isin(['TP1', 'TP2', 'TP3']).astype(int)
    return df

def find_edges():
    df = load_signals()
    
    # Base filter: remove Gold (it's fixed by a dedicated engine now)
    df = df[df['symbol'] != 'GC=F']
    
    qualities = [6.0, 7.0, 7.5, 8.0, 8.5]
    regime_blocks = [
        [],
        ['CHOPPY'],
        ['CHOPPY', 'UNKNOWN'],
        ['CHOPPY', 'UNKNOWN', 'RANGING']
    ]
    toxic_bans = [
        [],
        ['GBPUSD=X'],
        ['GBPUSD=X', 'NZDUSD=X'],
        ['GBPUSD=X', 'NZDUSD=X', 'BTC-USD']
    ]
    type_filters = [
        None, # all
        ['SESSION_CLOCK', 'ADVANCED_PATTERN'],
        ['SESSION_CLOCK', 'ADVANCED_PATTERN', 'SCALP']
    ]

    results = []
    
    for q, rb, tb, types in itertools.product(qualities, regime_blocks, toxic_bans, type_filters):
        d = df.copy()
        
        # apply quality
        d = d[d['quality_score'] >= q]
        
        # apply regime
        if rb:
            d = d[~d['regime'].isin(rb)]
            
        # apply toxic ban
        if tb:
            d = d[~d['symbol'].isin(tb)]
            
        # apply trade type
        if types:
            d = d[d['trade_type'].isin(types)]
            
        n = len(d)
        if n < 50:
            continue
            
        wins = d['is_win'].sum()
        wr = wins / n
        avg_rr = d['tp1_dist'].mean() / d['sl_dist'].mean() if d['sl_dist'].mean() > 0 else 0
        exp = (wr * avg_rr) - ((1 - wr) * 1.0)
        
        results.append({
            'q': q,
            'blocked_regimes': "+".join(rb) if rb else "None",
            'banned_symbols': "+".join(tb) if tb else "None",
            'trade_types': "+".join(types) if types else "All",
            'trades': n,
            'wr': round(wr * 100, 1),
            'rr': round(avg_rr, 2),
            'exp': round(exp, 3)
        })

    results_df = pd.DataFrame(results)
    if results_df.empty:
        print("No robust edges found.")
        return

    # Sort strongly by Expectancy
    best = results_df.sort_values(by='exp', ascending=False).head(10)
    
    print("\n" + "="*80)
    print(" 🚀 TOP 10 HIGH-EXPECTANCY EDGES FOUND")
    print("="*80)
    print(best.to_string(index=False))

if __name__ == "__main__":
    find_edges()
