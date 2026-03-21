"""
FORENSIC AUDIT of the Triple-Edge Strategy Suite
Decomposes failures by: symbol, direction, hour, RR achieved, and identifies root causes.
"""
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from config.config import SYMBOLS, SPREAD_PIPS, DXY_SYMBOL, TNX_SYMBOL
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator
from strategies.statistical_arbitrage_strategy import StatisticalArbitrageStrategy
from strategies.smc_liquidity_sweep import SMCLiquiditySweepStrategy
from strategies.anchored_poc_strategy import AnchoredPOCStrategy

async def run_forensic_audit(days=30):
    print("=" * 90)
    print("🔬 FORENSIC AUDIT: Triple-Edge Strategy Suite")
    print("=" * 90)
    
    fetcher = DataFetcher()
    strategies = {
        'SMC_SWEEP': SMCLiquiditySweepStrategy(),
        'POC_EDGE':  AnchoredPOCStrategy(),
        'STAT_ARB':  StatisticalArbitrageStrategy(),
    }
    
    start_date = (datetime.now() - timedelta(days=days + 15)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    # Load data
    all_data = {}
    for symbol in SYMBOLS:
        print(f"  Fetching {symbol}...")
        m5_df = fetcher.fetch_range(symbol, "5m", start_date, end_date)
        h1_df = fetcher.fetch_range(symbol, "1h", start_date, end_date)
        if m5_df is None or m5_df.empty or h1_df is None or h1_df.empty:
            continue
        all_data[symbol] = {
            'm5': IndicatorCalculator.add_indicators(m5_df, "5m"),
            'h1': IndicatorCalculator.add_indicators(h1_df, "1h")
        }

    # Load DXY for Stat Arb (THIS WAS MISSING IN THE BACKTEST!)
    market_context = {}
    try:
        dxy_df = fetcher.fetch_range(DXY_SYMBOL, "1h", start_date, end_date)
        if dxy_df is not None and not dxy_df.empty:
            market_context['DXY'] = IndicatorCalculator.add_indicators(dxy_df, "1h")
            print(f"  ✅ DXY loaded: {len(market_context['DXY'])} bars")
        tnx_df = fetcher.fetch_range(TNX_SYMBOL, "1h", start_date, end_date)
        if tnx_df is not None and not tnx_df.empty:
            market_context['^TNX'] = IndicatorCalculator.add_indicators(tnx_df, "1h")
    except Exception as e:
        print(f"  ⚠️ DXY fetch failed: {e}")

    trades = []
    signal_count = {name: 0 for name in strategies}
    
    for symbol, data in all_data.items():
        h1_df = data['h1']
        m5_df = data['m5']
        
        last_signal_bar = {name: -999 for name in strategies}  # Cooldown tracker
        
        for i in range(200, len(h1_df) - 1):
            ts = h1_df.index[i]
            h1_state = h1_df.iloc[:i+1]
            m5_i = m5_df.index.get_indexer([ts], method='ffill')[0]
            m5_state = m5_df.iloc[:m5_i+1]
            
            data_bundle = {'h1': h1_state, 'm5': m5_state}
            
            for name, strat in strategies.items():
                # Enforce a cooldown of 6 bars between signals from the same strategy
                if i - last_signal_bar[name] < 6:
                    continue
                
                signal = await strat.analyze(symbol, data_bundle, [], market_context)
                
                if signal:
                    signal_count[name] += 1
                    last_signal_bar[name] = i
                    
                    entry = signal['entry_price']
                    sl = signal['sl']
                    tp = signal['tp0']
                    direction = signal['direction']
                    sl_dist = abs(entry - sl)
                    if sl_dist == 0: continue
                    
                    rr_ratio = abs(tp - entry) / sl_dist if sl_dist > 0 else 0
                    
                    hit = None
                    pnl_r = 0.0
                    bars_held = 0
                    
                    # Simulate using M5 data
                    lookahead = 576
                    for j in range(m5_i+1, min(m5_i+lookahead, len(m5_df))):
                        bars_held += 1
                        fut = m5_df.iloc[j]
                        if direction == "BUY":
                            if fut['low'] <= sl: hit = "LOSS"; pnl_r = -1.0; break
                            if fut['high'] >= tp: hit = "WIN"; pnl_r = (tp - entry) / sl_dist; break
                        else:
                            if fut['high'] >= sl: hit = "LOSS"; pnl_r = -1.0; break
                            if fut['low'] <= tp: hit = "WIN"; pnl_r = (entry - tp) / sl_dist; break
                    
                    if hit:
                        hour = ts.hour if hasattr(ts, 'hour') else 0
                        trades.append({
                            't': ts, 'symbol': symbol, 'strategy': name,
                            'direction': direction, 'res': hit, 'r': pnl_r,
                            'rr_target': rr_ratio, 'bars_held': bars_held, 'hour': hour,
                            'sl_dist': sl_dist, 'entry': entry
                        })

    if not trades:
        print("\n❌ No trades found.")
        return

    df = pd.DataFrame(trades)
    
    # ============================================================
    # SECTION 1: Overall Strategy Performance
    # ============================================================
    print("\n" + "=" * 90)
    print("📊 SECTION 1: OVERALL STRATEGY PERFORMANCE")
    print("=" * 90)
    print(f"{'STRATEGY':<15} | {'TOTAL':>6} | {'WIN%':>7} | {'PF':>6} | {'EXP':>8} | {'AVG_BARS':>9}")
    print("-" * 90)
    
    for name in strategies.keys():
        sub = df[df['strategy'] == name]
        if sub.empty:
            print(f"{name:<15} | {'0':>6} | {'N/A':>7} | {'N/A':>6} | {'N/A':>8} | {'N/A':>9}")
            continue
        wr = (sub['res'] == 'WIN').mean() * 100
        win_r = sub[sub['r'] > 0]['r'].sum()
        loss_r = abs(sub[sub['r'] < 0]['r'].sum())
        pf = win_r / loss_r if loss_r > 0 else float('inf')
        avg_bars = sub['bars_held'].mean()
        print(f"{name:<15} | {len(sub):>6} | {wr:>6.1f}% | {pf:>6.2f} | {sub['r'].mean():>7.3f}R | {avg_bars:>8.0f}")

    # ============================================================
    # SECTION 2: PER-SYMBOL BREAKDOWN
    # ============================================================
    print("\n" + "=" * 90)
    print("📊 SECTION 2: PER-SYMBOL BREAKDOWN")
    print("=" * 90)
    
    for name in strategies.keys():
        sub = df[df['strategy'] == name]
        if sub.empty: continue
        print(f"\n  --- {name} ---")
        print(f"  {'SYMBOL':<12} | {'N':>5} | {'WIN%':>7} | {'EXP':>8} | {'BUY':>5} | {'SELL':>5}")
        print(f"  " + "-" * 60)
        for sym in sub['symbol'].unique():
            sym_df = sub[sub['symbol'] == sym]
            wr = (sym_df['res'] == 'WIN').mean() * 100
            buys = len(sym_df[sym_df['direction'] == 'BUY'])
            sells = len(sym_df[sym_df['direction'] == 'SELL'])
            print(f"  {sym:<12} | {len(sym_df):>5} | {wr:>6.1f}% | {sym_df['r'].mean():>7.3f}R | {buys:>5} | {sells:>5}")
    
    # ============================================================
    # SECTION 3: DIRECTIONAL BIAS
    # ============================================================
    print("\n" + "=" * 90)
    print("📊 SECTION 3: DIRECTIONAL BIAS")
    print("=" * 90)
    
    for name in strategies.keys():
        sub = df[df['strategy'] == name]
        if sub.empty: continue
        print(f"\n  --- {name} ---")
        for d in ['BUY', 'SELL']:
            d_df = sub[sub['direction'] == d]
            if d_df.empty: continue
            wr = (d_df['res'] == 'WIN').mean() * 100
            print(f"  {d:<6}: {len(d_df):>5} trades | WR: {wr:>6.1f}% | Exp: {d_df['r'].mean():>7.3f}R")
    
    # ============================================================
    # SECTION 4: TIME-OF-DAY ANALYSIS
    # ============================================================
    print("\n" + "=" * 90)
    print("📊 SECTION 4: TIME-OF-DAY ANALYSIS (Best & Worst Hours)")
    print("=" * 90)
    
    for name in strategies.keys():
        sub = df[df['strategy'] == name]
        if sub.empty or len(sub) < 10: continue
        print(f"\n  --- {name} ---")
        hourly = sub.groupby('hour').agg(
            count=('r', 'count'),
            wr=('res', lambda x: (x == 'WIN').mean() * 100),
            exp=('r', 'mean')
        ).sort_values('exp', ascending=False)
        
        print(f"  {'HOUR':>6} | {'N':>5} | {'WIN%':>7} | {'EXP':>8}")
        print(f"  " + "-" * 40)
        for hour, row in hourly.iterrows():
            marker = " ✅" if row['exp'] > 0 else " ❌"
            print(f"  {hour:>5}h | {int(row['count']):>5} | {row['wr']:>6.1f}% | {row['exp']:>7.3f}R{marker}")
    
    # ============================================================
    # SECTION 5: LOSS ANALYSIS — Why are we losing?
    # ============================================================
    print("\n" + "=" * 90)
    print("🔬 SECTION 5: LOSS DEEP-DIVE")
    print("=" * 90)
    
    for name in strategies.keys():
        sub = df[df['strategy'] == name]
        losses = sub[sub['res'] == 'LOSS']
        wins = sub[sub['res'] == 'WIN']
        if losses.empty: continue
        
        print(f"\n  --- {name} ---")
        print(f"  Total Losses: {len(losses)} | Total Wins: {len(wins)}")
        
        # Average bars to SL hit vs bars to TP
        avg_bars_loss = losses['bars_held'].mean()
        avg_bars_win = wins['bars_held'].mean() if not wins.empty else 0
        print(f"  Avg bars to SL: {avg_bars_loss:.0f} | Avg bars to TP: {avg_bars_win:.0f}")
        
        # RR being targeted
        avg_rr = sub['rr_target'].mean()
        print(f"  Avg RR Target: {avg_rr:.2f}")
        
        # Breakeven WR needed
        be_wr = 1.0 / (1.0 + avg_rr) * 100 if avg_rr > 0 else 50.0
        actual_wr = (sub['res'] == 'WIN').mean() * 100
        print(f"  Breakeven WR needed: {be_wr:.1f}% | Actual WR: {actual_wr:.1f}% | Gap: {actual_wr - be_wr:+.1f}%")
        
        # Fastest losses (SL hit immediately)
        instant_losses = losses[losses['bars_held'] <= 6]
        print(f"  Instant SL hits (≤30min): {len(instant_losses)} ({len(instant_losses)/max(len(losses),1)*100:.0f}% of losses)")
    
    # ============================================================
    # SECTION 6: SIGNAL FREQUENCY
    # ============================================================
    print("\n" + "=" * 90)
    print("📊 SECTION 6: SIGNAL FREQUENCY (with 6-bar cooldown)")
    print("=" * 90)
    for name, count in signal_count.items():
        per_day = count / days if days > 0 else 0
        print(f"  {name:<15}: {count:>5} signals | {per_day:>5.1f}/day")
    
    # ============================================================
    # SECTION 7: ROOT CAUSE DIAGNOSIS
    # ============================================================
    print("\n" + "=" * 90)
    print("🩺 SECTION 7: ROOT CAUSE DIAGNOSIS")
    print("=" * 90)
    
    for name in strategies.keys():
        sub = df[df['strategy'] == name]
        if sub.empty:
            print(f"\n  [{name}] ❌ ZERO TRADES — Strategy conditions never met in this period.")
            if name == "STAT_ARB":
                print(f"         CAUSE: DXY Z-score never reached ±1.8 or indicator 'zscore_20' missing from DXY data.")
            continue
        
        wr = (sub['res'] == 'WIN').mean() * 100
        avg_rr = sub['rr_target'].mean()
        be_wr = 1.0 / (1.0 + avg_rr) * 100 if avg_rr > 0 else 50.0
        losses = sub[sub['res'] == 'LOSS']
        instant_losses = losses[losses['bars_held'] <= 6]
        
        print(f"\n  [{name}]")
        
        if len(instant_losses) / max(len(losses), 1) > 0.4:
            print(f"  🔴 STOP-LOSS TOO TIGHT: {len(instant_losses)/len(losses)*100:.0f}% of losses are instant SL hits (<30 min).")
            print(f"     → FIX: Widen SL from current ATR multiplier.")
        
        if wr < be_wr:
            gap = be_wr - wr
            print(f"  🔴 WR BELOW BREAKEVEN: Need {be_wr:.1f}% but achieving {wr:.1f}% (gap: {gap:.1f}%)")
            if avg_rr > 2.5:
                print(f"     → FIX: Lower TP target to improve WR. Current RR: {avg_rr:.1f}")
            else:
                print(f"     → FIX: Add confluence filters (regime, momentum confirmation).")
        
        if len(sub) > 500:
            print(f"  🟡 OVERTRADING: {len(sub)} trades in {days} days ({len(sub)/days:.0f}/day). Noise-heavy.")
            print(f"     → FIX: Increase minimum deviation threshold or add trend-alignment filter.")
        
        # Check directional imbalance
        buys = sub[sub['direction'] == 'BUY']
        sells = sub[sub['direction'] == 'SELL']
        buy_wr = (buys['res'] == 'WIN').mean() * 100 if not buys.empty else 0
        sell_wr = (sells['res'] == 'WIN').mean() * 100 if not sells.empty else 0
        if abs(buy_wr - sell_wr) > 15:
            better = "BUY" if buy_wr > sell_wr else "SELL"
            worse = "SELL" if buy_wr > sell_wr else "BUY"
            print(f"  🟡 DIRECTIONAL SKEW: {better} WR={max(buy_wr,sell_wr):.0f}% vs {worse} WR={min(buy_wr,sell_wr):.0f}%")
            print(f"     → CONSIDER: Only trade the {better} direction, or add trend filter for {worse}.")
    
    print("\n" + "=" * 90)
    print("✅ Forensic audit complete.")
    print("=" * 90)

if __name__ == "__main__":
    import sys
    d = 30
    if len(sys.argv) > 1: d = int(sys.argv[1])
    asyncio.run(run_forensic_audit(d))
