"""
VM Signal Backtest Simulator (V25.0)
====================================
Simulates the effect of proposed strategy refinements against
actual production signals from the VM database.

This is NOT re-generating signals — it's applying "what-if" filters
to the REAL signals that were generated and traded.
"""
import sqlite3
import pandas as pd
import numpy as np

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


def simulate(df, label, filters=None):
    """Apply filters and calculate simulated metrics."""
    filtered = df.copy()
    
    if filters:
        for f_name, f_func in filters.items():
            before = len(filtered)
            filtered = filtered[f_func(filtered)]
            removed = before - len(filtered)
    
    total = len(filtered)
    if total == 0:
        print(f"  {label}: No trades pass filters.")
        return
    
    wins = filtered['is_win'].sum()
    losses = total - wins
    wr = wins / total * 100
    
    # Calculate expectancy (simplified)
    avg_rr = filtered['tp1_dist'].mean() / filtered['sl_dist'].mean() if filtered['sl_dist'].mean() > 0 else 0
    expectancy = (wr / 100 * avg_rr) - ((1 - wr / 100) * 1.0)
    
    # Per-day signal count
    signals_per_day = total / 60  # Approximate over 60 days
    
    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")
    print(f"  Total Trades:     {total:>6}")
    print(f"  Wins:             {wins:>6}  |  Losses: {losses:>6}")
    print(f"  Win Rate:         {wr:>6.1f}%")
    print(f"  Avg R:R (TP1/SL): {avg_rr:>6.2f}")
    print(f"  Expectancy:       {expectancy:>+6.3f}R per trade")
    print(f"  Signals/Day:      {signals_per_day:>6.1f}")
    
    # Breakdown by trade_type
    print(f"\n  {'Trade Type':<20} {'Count':>6} {'WR':>8} {'SL%':>8}")
    print(f"  {'-'*44}")
    for tt in filtered['trade_type'].unique():
        sub = filtered[filtered['trade_type'] == tt]
        tt_wr = sub['is_win'].mean() * 100
        tt_sl = (sub['result'] == 'SL').mean() * 100
        print(f"  {tt:<20} {len(sub):>6} {tt_wr:>7.1f}% {tt_sl:>7.1f}%")
    
    # Top 3 worst symbols
    print(f"\n  Worst Symbols:")
    sym_stats = filtered.groupby('symbol').agg(
        count=('is_win', 'size'),
        wr=('is_win', 'mean')
    ).sort_values('wr')
    for sym, row in sym_stats.head(3).iterrows():
        print(f"    {sym}: {row['count']:.0f} trades, {row['wr']*100:.1f}% WR")
    
    return filtered


def main():
    df = load_signals()
    print(f"Loaded {len(df)} closed trades from VM database")
    print(f"Date range: {df['id'].min()} to {df['id'].max()}")
    
    # ──────────────────────────────────────────────────────────
    # SCENARIO 0: Current Baseline (No changes)
    # ──────────────────────────────────────────────────────────
    simulate(df, "BASELINE (Current System — No Changes)")
    
    # ──────────────────────────────────────────────────────────
    # SCENARIO 1: Pillar 2 — Quality Hard-Floor (7.0)
    # ──────────────────────────────────────────────────────────
    simulate(df, "PILLAR 2a: Quality Score ≥ 7.0", {
        "quality_floor": lambda d: d['quality_score'] >= 7.0
    })
    
    # ──────────────────────────────────────────────────────────
    # SCENARIO 2: Pillar 2 — Quality + Regime Block
    # ──────────────────────────────────────────────────────────
    simulate(df, "PILLAR 2b: Quality ≥ 7.0 + Block CHOPPY/UNKNOWN", {
        "quality_floor": lambda d: d['quality_score'] >= 7.0,
        "regime_block": lambda d: ~d['regime'].isin(['CHOPPY', 'UNKNOWN'])
    })
    
    # ──────────────────────────────────────────────────────────
    # SCENARIO 3: Pillar 2 Full — Quality + Regime + RANGING bar
    # ──────────────────────────────────────────────────────────
    def pillar2_full(d):
        """Quality ≥ 7.0 globally, ≥ 7.5 for RANGING, block CHOPPY/UNKNOWN"""
        mask = d['quality_score'] >= 7.0
        mask &= ~d['regime'].isin(['CHOPPY', 'UNKNOWN'])
        mask &= ~((d['regime'] == 'RANGING') & (d['quality_score'] < 7.5))
        return mask
    
    simulate(df, "PILLAR 2 FULL: Quality 7.0 + Regime Filters + RANGING 7.5", {
        "pillar2": pillar2_full
    })
    
    # ──────────────────────────────────────────────────────────
    # SCENARIO 4: Pillar 2 Full + Only keep Session Clock & Advanced
    # ──────────────────────────────────────────────────────────
    simulate(df, "AGGRESSIVE: Only SESSION_CLOCK + ADVANCED_PATTERN", {
        "strategy_filter": lambda d: d['trade_type'].isin(['SESSION_CLOCK', 'ADVANCED_PATTERN'])
    })
    
    # ──────────────────────────────────────────────────────────
    # SCENARIO 5: Pillar 2 Full + Exclude worst symbols  
    # ──────────────────────────────────────────────────────────
    simulate(df, "PILLAR 2 FULL + Exclude BTC-USD & USDJPY", {
        "pillar2": pillar2_full,
        "symbol_ban": lambda d: ~d['symbol'].isin(['BTC-USD', 'USDJPY=X'])
    })
    
    # ──────────────────────────────────────────────────────────
    # SCENARIO 6: Conservative Hybrid (Best of both worlds)
    # ──────────────────────────────────────────────────────────
    def hybrid_filter(d):
        """
        Keep ALL Session Clock + Advanced Pattern trades.
        For SCALP/SWING: Only accept Quality ≥ 7.5 + non-CHOPPY/UNKNOWN.
        """
        is_time_based = d['trade_type'].isin(['SESSION_CLOCK', 'ADVANCED_PATTERN'])
        quant_ok = (
            (d['quality_score'] >= 7.5) & 
            (~d['regime'].isin(['CHOPPY', 'UNKNOWN'])) &
            (~((d['regime'] == 'RANGING') & (d['quality_score'] < 8.0)))
        )
        return is_time_based | quant_ok
    
    simulate(df, "HYBRID: All Time-Based + High-Quality SCALP/SWING", {
        "hybrid": hybrid_filter
    })


if __name__ == "__main__":
    main()
