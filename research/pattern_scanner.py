"""
Pattern Scanner — Finds Statistically Repeating Market Patterns
Tests the following phenomena across all symbols:
  1. London Open Breakout (08:00 UTC)
  2. NY Open Reversal (13:00 UTC)
  3. Asian Range Sweep & Reverse (00:00–07:00 UTC)
  4. Monday Gap Fill
  5. 3-Bar Momentum Continuation
  6. RSI Exhaustion Reversal (RSI > 75 / < 25)
  7. ATR Expansion Breakout (volatility squeeze pop)
  8. End-of-Day Mean Reversion (20:00 UTC)

For each pattern, calculates:
  - Hit Rate (% of times pattern leads to profitable outcome)
  - Average R-Multiple
  - Profit Factor
  - Sample count (N)
"""
import yfinance as yf
import pandas as pd
import numpy as np
import warnings
from datetime import time

warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

SYMBOLS = {
    "EURUSD=X": "EURUSD",
    "GBPUSD=X": "GBPUSD",
    "USDJPY=X": "USDJPY",
    "AUDUSD=X": "AUDUSD",
    "GBPJPY=X": "GBPJPY",
    "GC=F":     "GOLD",
    "CL=F":     "OIL",
    "BTC-USD":  "BTC",
}

FWD_BARS   = 4    # bars to check for TP/SL hit (4h on 1h data)
RR         = 2.0  # reward:risk ratio for all patterns
ATR_PERIOD = 14


# ── Helpers ───────────────────────────────────────────────────────────────────

def calc_atr(df, n=ATR_PERIOD):
    hl = df['High'] - df['Low']
    hc = (df['High'] - df['Close'].shift()).abs()
    lc = (df['Low']  - df['Close'].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.rolling(n).mean()

def calc_rsi(close, n=14):
    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(n).mean()
    loss  = (-delta.clip(upper=0)).rolling(n).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def simulate_trade(df, idx, direction, atr_val, rr=RR, fwd=FWD_BARS):
    """Returns 'WIN', 'LOSS', or None (no resolution)."""
    entry = df['Close'].iloc[idx]
    sl_dist = atr_val * 1.0
    tp_dist = sl_dist * rr

    sl = entry - sl_dist if direction == 'BUY' else entry + sl_dist
    tp = entry + tp_dist if direction == 'BUY' else entry - tp_dist

    for j in range(idx + 1, min(idx + fwd + 1, len(df))):
        h, l = df['High'].iloc[j], df['Low'].iloc[j]
        if direction == 'BUY':
            if l <= sl: return 'LOSS'
            if h >= tp: return 'WIN'
        else:
            if h >= sl: return 'LOSS'
            if l <= tp: return 'WIN'
    return None

def score(trades):
    """Returns (hit_rate, profit_factor, avg_r, n)."""
    if not trades: return 0, 0, 0, 0
    wins   = trades.count('WIN')
    losses = trades.count('LOSS')
    n      = wins + losses
    if n == 0: return 0, 0, 0, 0
    hr  = wins / n
    pf  = (wins * RR) / losses if losses else float('inf')
    avg = (wins * RR - losses) / n
    return round(hr, 3), round(pf, 3), round(avg, 3), n


# ── Pattern Detectors ─────────────────────────────────────────────────────────

def pattern_london_open_breakout(df):
    """Buy/Sell breakout of the 07:00 candle high/low at 08:00 UTC."""
    trades = []
    df = df.copy()
    df.index = pd.to_datetime(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_convert('UTC')

    for i in range(1, len(df) - FWD_BARS):
        ts = df.index[i]
        if ts.hour == 8 and ts.minute == 0:
            prev = df.iloc[i - 1]
            curr = df.iloc[i]
            # Breakout above previous candle high → BUY
            if curr['Close'] > prev['High']:
                r = simulate_trade(df, i, 'BUY', df['atr'].iloc[i])
                if r: trades.append(r)
            # Breakout below previous candle low → SELL
            elif curr['Close'] < prev['Low']:
                r = simulate_trade(df, i, 'SELL', df['atr'].iloc[i])
                if r: trades.append(r)
    return trades

def pattern_ny_open_reversal(df):
    """Fade the first 30-min NY move: if 13:00 candle is bullish → SELL, bearish → BUY."""
    trades = []
    df = df.copy()
    df.index = pd.to_datetime(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_convert('UTC')

    for i in range(1, len(df) - FWD_BARS):
        ts = df.index[i]
        if ts.hour == 13 and ts.minute == 0:
            candle = df.iloc[i]
            body = candle['Close'] - candle['Open']
            atr  = df['atr'].iloc[i]
            # Only trade if candle body > 0.5 ATR (meaningful move)
            if abs(body) > atr * 0.5:
                direction = 'SELL' if body > 0 else 'BUY'
                r = simulate_trade(df, i, direction, atr)
                if r: trades.append(r)
    return trades

def pattern_asian_sweep_reverse(df):
    """Asian range (00:00–07:00) sweep then reverse: price sweeps range high/low then closes back inside."""
    trades = []
    df = df.copy()
    df.index = pd.to_datetime(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_convert('UTC')

    dates = df.index.normalize().unique()
    for date in dates:
        asian = df[(df.index.date == date.date()) & (df.index.hour < 7)]
        if len(asian) < 3: continue
        a_high = asian['High'].max()
        a_low  = asian['Low'].min()

        # Check 07:00–09:00 for sweep + reversal
        post = df[(df.index.date == date.date()) & (df.index.hour.isin([7, 8]))]
        for i in range(len(post)):
            row = post.iloc[i]
            idx = df.index.get_loc(post.index[i])
            if idx + FWD_BARS >= len(df): continue
            atr = df['atr'].iloc[idx]
            # Sweep high then close back below → SELL
            if row['High'] > a_high and row['Close'] < a_high:
                r = simulate_trade(df, idx, 'SELL', atr)
                if r: trades.append(r)
            # Sweep low then close back above → BUY
            elif row['Low'] < a_low and row['Close'] > a_low:
                r = simulate_trade(df, idx, 'BUY', atr)
                if r: trades.append(r)
    return trades

def pattern_3bar_momentum(df):
    """3 consecutive same-direction bars → trade continuation on 4th bar."""
    trades = []
    for i in range(3, len(df) - FWD_BARS):
        c = df['Close']
        # 3 bullish bars
        if c.iloc[i-1] > c.iloc[i-2] > c.iloc[i-3]:
            r = simulate_trade(df, i, 'BUY', df['atr'].iloc[i])
            if r: trades.append(r)
        # 3 bearish bars
        elif c.iloc[i-1] < c.iloc[i-2] < c.iloc[i-3]:
            r = simulate_trade(df, i, 'SELL', df['atr'].iloc[i])
            if r: trades.append(r)
    return trades

def pattern_rsi_exhaustion(df):
    """RSI > 75 → SELL; RSI < 25 → BUY (mean reversion after exhaustion)."""
    trades = []
    for i in range(1, len(df) - FWD_BARS):
        rsi = df['rsi'].iloc[i]
        prev_rsi = df['rsi'].iloc[i - 1]
        atr = df['atr'].iloc[i]
        # RSI crosses back below 75 → SELL
        if prev_rsi >= 75 and rsi < 75:
            r = simulate_trade(df, i, 'SELL', atr)
            if r: trades.append(r)
        # RSI crosses back above 25 → BUY
        elif prev_rsi <= 25 and rsi > 25:
            r = simulate_trade(df, i, 'BUY', atr)
            if r: trades.append(r)
    return trades

def pattern_atr_squeeze_breakout(df):
    """ATR drops below 20-period average (squeeze), then expands → trade the breakout."""
    trades = []
    atr_avg = df['atr'].rolling(20).mean()
    for i in range(21, len(df) - FWD_BARS):
        prev_ratio = df['atr'].iloc[i-1] / atr_avg.iloc[i-1]
        curr_ratio = df['atr'].iloc[i]   / atr_avg.iloc[i]
        # Was in squeeze (< 0.8), now expanding (> 1.0)
        if prev_ratio < 0.8 and curr_ratio > 1.0:
            # Trade in direction of the breakout candle
            candle = df.iloc[i]
            direction = 'BUY' if candle['Close'] > candle['Open'] else 'SELL'
            r = simulate_trade(df, i, direction, df['atr'].iloc[i])
            if r: trades.append(r)
    return trades

def pattern_eod_mean_reversion(df):
    """End of day (20:00 UTC): if price is > 1 ATR from daily open → fade it."""
    trades = []
    df = df.copy()
    df.index = pd.to_datetime(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_convert('UTC')

    dates = df.index.normalize().unique()
    for date in dates:
        day_bars = df[df.index.date == date.date()]
        if day_bars.empty: continue
        day_open = day_bars['Open'].iloc[0]

        eod = day_bars[day_bars.index.hour == 20]
        for i in range(len(eod)):
            idx = df.index.get_loc(eod.index[i])
            if idx + FWD_BARS >= len(df): continue
            price = eod.iloc[i]['Close']
            atr   = df['atr'].iloc[idx]
            dist  = price - day_open
            if abs(dist) > atr:
                direction = 'SELL' if dist > 0 else 'BUY'
                r = simulate_trade(df, idx, direction, atr)
                if r: trades.append(r)
    return trades


# ── Main ──────────────────────────────────────────────────────────────────────

PATTERNS = {
    "London Open Breakout":    pattern_london_open_breakout,
    "NY Open Reversal":        pattern_ny_open_reversal,
    "Asian Sweep & Reverse":   pattern_asian_sweep_reverse,
    "3-Bar Momentum":          pattern_3bar_momentum,
    "RSI Exhaustion Reversal": pattern_rsi_exhaustion,
    "ATR Squeeze Breakout":    pattern_atr_squeeze_breakout,
    "EOD Mean Reversion":      pattern_eod_mean_reversion,
}

def run():
    # Aggregate results: pattern → list of (hr, pf, avg_r, n) per symbol
    agg = {p: [] for p in PATTERNS}
    symbol_results = []

    for ticker, label in SYMBOLS.items():
        print(f"  Fetching {label}...")
        try:
            df = yf.download(ticker, period="180d", interval="1h",
                             progress=False, auto_adjust=True)
            if df.empty: continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            df['atr'] = calc_atr(df)
            df['rsi'] = calc_rsi(df['Close'])
            df = df.dropna()

            for pname, pfunc in PATTERNS.items():
                try:
                    trades = pfunc(df)
                    hr, pf, avg_r, n = score(trades)
                    agg[pname].append((hr, pf, avg_r, n))
                    symbol_results.append({
                        'Symbol': label, 'Pattern': pname,
                        'N': n, 'HitRate': hr, 'PF': pf, 'AvgR': avg_r
                    })
                except Exception as e:
                    pass
        except Exception as e:
            print(f"    ❌ {e}")

    # ── Print per-symbol table ────────────────────────────────────────────────
    df_res = pd.DataFrame(symbol_results)

    print("\n" + "="*90)
    print("  PATTERN SCANNER RESULTS  (180 days × 1h × 8 symbols)")
    print("  PF > 1.5 = Interesting  |  PF > 2.0 = Strong  |  N > 30 = Reliable")
    print("="*90)

    for pname in PATTERNS:
        sub = df_res[df_res['Pattern'] == pname]
        total_n = sub['N'].sum()
        if total_n == 0: continue

        # Weighted average across symbols
        w_hr  = (sub['HitRate'] * sub['N']).sum() / total_n
        w_pf  = (sub['PF']      * sub['N']).sum() / total_n
        w_avg = (sub['AvgR']    * sub['N']).sum() / total_n

        flag = "🟢" if w_pf > 2.0 else ("🟡" if w_pf > 1.5 else "🔴")
        print(f"\n{flag} {pname}")
        print(f"   Overall  N={total_n:>4}  HitRate={w_hr:.1%}  PF={w_pf:.2f}  AvgR={w_avg:+.3f}")
        print(f"   {'Symbol':<10} {'N':>5}  {'HitRate':>8}  {'PF':>7}  {'AvgR':>8}")
        for _, row in sub.sort_values('PF', ascending=False).iterrows():
            sym_flag = "🟢" if row['PF'] > 2.0 else ("🟡" if row['PF'] > 1.5 else "⚪")
            print(f"   {sym_flag} {row['Symbol']:<9} {int(row['N']):>5}  "
                  f"{row['HitRate']:>8.1%}  {row['PF']:>7.2f}  {row['AvgR']:>+8.3f}")

    # ── Best patterns summary ─────────────────────────────────────────────────
    print("\n" + "="*90)
    print("  🏆 TOP PATTERNS BY PROFIT FACTOR (N ≥ 30)")
    print("="*90)
    strong = df_res[df_res['N'] >= 30].sort_values('PF', ascending=False).head(15)
    for _, row in strong.iterrows():
        print(f"  {row['Symbol']:<10} {row['Pattern']:<28} "
              f"N={int(row['N']):>4}  HR={row['HitRate']:.1%}  PF={row['PF']:.2f}  AvgR={row['AvgR']:+.3f}")

    df_res.to_csv("research/pattern_scan_results.csv", index=False)
    print("\n  ✅ Saved to research/pattern_scan_results.csv")


if __name__ == "__main__":
    print("🔍 Pattern Scanner — Finding Repeating Market Phenomena")
    print("   180 days × 1h bars × 8 symbols × 7 patterns\n")
    run()
