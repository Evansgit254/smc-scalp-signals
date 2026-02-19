"""
Daily Pattern Scanner
=====================
Scans WHAT THE MARKET DOES EVERY DAY at each hour.

Outputs:
  1. Hourly Return Heatmap — avg return per hour of day per symbol
  2. Best Trading Hours — hours with consistent directional bias
  3. Day-of-Week Effect — which days trend vs reverse
  4. Session Transition Patterns — what happens at London/NY open/close
  5. Intraday Volatility Profile — when ATR expands (best for breakouts)

This is pure empirical analysis — no indicators, just raw price behavior.
"""
import yfinance as yf
import pandas as pd
import numpy as np
import warnings
from scipy import stats

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

DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']


def fetch(ticker, period="365d"):
    df = yf.download(ticker, period=period, interval="1h",
                     progress=False, auto_adjust=True)
    if df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.index = pd.to_datetime(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_convert('UTC')
    # Candle return (%)
    df['ret']  = (df['Close'] - df['Open']) / df['Open'] * 100
    df['atr1'] = (df['High'] - df['Low']) / df['Open'] * 100  # candle range %
    df['hour'] = df.index.hour
    df['dow']  = df.index.dayofweek   # 0=Mon
    df['date'] = df.index.date
    return df


def hourly_analysis(df, label):
    """For each hour 0-23: avg return, win rate, t-stat, avg range."""
    rows = []
    for h in range(24):
        sub = df[df['hour'] == h]['ret'].dropna()
        if len(sub) < 20:
            continue
        mean_r  = sub.mean()
        win_r   = (sub > 0).mean()
        t, p    = stats.ttest_1samp(sub, 0)
        rng     = df[df['hour'] == h]['atr1'].mean()
        rows.append({
            'Hour': h, 'N': len(sub),
            'AvgRet%': round(mean_r, 4),
            'WinRate': round(win_r, 3),
            'T-stat': round(t, 2),
            'P-val': round(p, 3),
            'AvgRange%': round(rng, 4),
            'Significant': p < 0.05
        })
    return pd.DataFrame(rows)


def dow_analysis(df):
    """Day-of-week: avg daily return and win rate."""
    rows = []
    for d in range(5):
        day_df = df[df['dow'] == d]
        # Aggregate to daily return
        daily = day_df.groupby('date')['ret'].sum()
        if len(daily) < 10:
            continue
        rows.append({
            'Day': DAYS[d],
            'N': len(daily),
            'AvgDayRet%': round(daily.mean(), 4),
            'WinRate': round((daily > 0).mean(), 3),
            'T-stat': round(stats.ttest_1samp(daily, 0)[0], 2),
            'P-val': round(stats.ttest_1samp(daily, 0)[1], 3),
        })
    return pd.DataFrame(rows)


def session_transitions(df):
    """
    Measure what happens in the FIRST CANDLE of each session:
    - Asian Open  (00:00 UTC)
    - London Open (08:00 UTC)
    - NY Open     (13:00 UTC)
    - London Close(16:00 UTC)
    - NY Close    (21:00 UTC)
    Returns avg return and win rate at each transition.
    """
    sessions = {
        'Asian Open (00h)':   0,
        'London Open (08h)':  8,
        'NY Open (13h)':     13,
        'London Close (16h)':16,
        'NY Close (21h)':    21,
    }
    rows = []
    for name, h in sessions.items():
        sub = df[df['hour'] == h]['ret'].dropna()
        if len(sub) < 20:
            continue
        mean_r = sub.mean()
        win_r  = (sub > 0).mean()
        t, p   = stats.ttest_1samp(sub, 0)
        rows.append({
            'Session': name, 'N': len(sub),
            'AvgRet%': round(mean_r, 4),
            'WinRate': round(win_r, 3),
            'T-stat': round(t, 2),
            'P-val': round(p, 3),
            'Bias': 'BULL' if mean_r > 0 else 'BEAR',
            'Significant': p < 0.05
        })
    return pd.DataFrame(rows)


def run():
    all_hourly = []
    all_dow    = []
    all_sess   = []

    for ticker, label in SYMBOLS.items():
        print(f"  Fetching {label} (365d)...")
        df = fetch(ticker)
        if df is None:
            print(f"    ⚠ No data"); continue

        h_df  = hourly_analysis(df, label)
        d_df  = dow_analysis(df)
        s_df  = session_transitions(df)

        h_df['Symbol'] = label
        d_df['Symbol'] = label
        s_df['Symbol'] = label

        all_hourly.append(h_df)
        all_dow.append(d_df)
        all_sess.append(s_df)

    hourly = pd.concat(all_hourly)
    dow    = pd.concat(all_dow)
    sess   = pd.concat(all_sess)

    # ── 1. HOURLY HEATMAP ────────────────────────────────────────────────────
    print("\n" + "="*100)
    print("  📊 HOURLY RETURN HEATMAP (avg candle return % per UTC hour)")
    print("  🟢 = Bullish bias  |  🔴 = Bearish bias  |  * = Statistically significant (p<0.05)")
    print("="*100)

    pivot = hourly.pivot(index='Symbol', columns='Hour', values='AvgRet%').fillna(0)
    sig   = hourly.pivot(index='Symbol', columns='Hour', values='Significant').fillna(False)

    # Header
    hours = sorted(hourly['Hour'].unique())
    print(f"  {'Symbol':<10}", end="")
    for h in hours:
        print(f" {h:>5}h", end="")
    print()
    print("  " + "-"*98)

    for sym in pivot.index:
        print(f"  {sym:<10}", end="")
        for h in hours:
            val  = pivot.loc[sym, h] if h in pivot.columns else 0
            star = "*" if (h in sig.columns and sig.loc[sym, h]) else " "
            icon = "🟢" if val > 0.001 else ("🔴" if val < -0.001 else "⚪")
            print(f" {icon}{star}", end="")
        print()

    # ── 2. BEST HOURS (significant + consistent direction) ───────────────────
    print("\n" + "="*100)
    print("  🏆 BEST TRADING HOURS (Statistically Significant, p < 0.05)")
    print("="*100)
    sig_hours = hourly[hourly['Significant']].sort_values('AvgRet%', key=abs, ascending=False)
    if sig_hours.empty:
        print("  No statistically significant hours found.")
    else:
        print(f"  {'Symbol':<10} {'Hour':>5}  {'AvgRet%':>9}  {'WinRate':>8}  {'T-stat':>7}  {'N':>5}  Bias")
        for _, row in sig_hours.head(20).iterrows():
            bias = "🟢 BULL" if row['AvgRet%'] > 0 else "🔴 BEAR"
            print(f"  {row['Symbol']:<10} {int(row['Hour']):>5}h  "
                  f"{row['AvgRet%']:>+9.4f}  {row['WinRate']:>8.1%}  "
                  f"{row['T-stat']:>7.2f}  {int(row['N']):>5}  {bias}")

    # ── 3. DAY-OF-WEEK EFFECT ────────────────────────────────────────────────
    print("\n" + "="*100)
    print("  📅 DAY-OF-WEEK EFFECT (avg daily return %)")
    print("="*100)
    dow_pivot = dow.pivot(index='Symbol', columns='Day', values='AvgDayRet%').fillna(0)
    col_order = [d for d in DAYS if d in dow_pivot.columns]
    print(f"  {'Symbol':<10}", end="")
    for d in col_order:
        print(f"  {d:>8}", end="")
    print()
    print("  " + "-"*60)
    for sym in dow_pivot.index:
        print(f"  {sym:<10}", end="")
        for d in col_order:
            val = dow_pivot.loc[sym, d]
            icon = "🟢" if val > 0.01 else ("🔴" if val < -0.01 else "⚪")
            print(f"  {icon}{val:>+6.3f}", end="")
        print()

    # ── 4. SESSION TRANSITIONS ───────────────────────────────────────────────
    print("\n" + "="*100)
    print("  🕐 SESSION TRANSITION ANALYSIS")
    print("  Shows the average direction of the FIRST CANDLE at each session open")
    print("="*100)
    print(f"  {'Symbol':<10} {'Session':<25} {'N':>5}  {'AvgRet%':>9}  {'WinRate':>8}  {'Bias':<8}  Sig?")
    print("  " + "-"*80)
    sess_sorted = sess.sort_values(['Session', 'AvgRet%'], key=lambda x: x if x.dtype != object else x.str.len())
    for _, row in sess.sort_values('AvgRet%', key=abs, ascending=False).iterrows():
        sig_mark = "✅" if row['Significant'] else "  "
        bias_icon = "🟢" if row['Bias'] == 'BULL' else "🔴"
        print(f"  {row['Symbol']:<10} {row['Session']:<25} {int(row['N']):>5}  "
              f"{row['AvgRet%']:>+9.4f}  {row['WinRate']:>8.1%}  "
              f"{bias_icon} {row['Bias']:<6}  {sig_mark}")

    # ── 5. VOLATILITY PROFILE ────────────────────────────────────────────────
    print("\n" + "="*100)
    print("  💥 HOURLY VOLATILITY PROFILE (avg candle range % — best hours for breakouts)")
    print("="*100)
    vol_pivot = hourly.pivot(index='Symbol', columns='Hour', values='AvgRange%').fillna(0)
    # Show top 5 highest-volatility hours per symbol
    print(f"  {'Symbol':<10}  Top Volatile Hours (UTC)")
    print("  " + "-"*60)
    for sym in vol_pivot.index:
        top5 = vol_pivot.loc[sym].nlargest(5)
        hours_str = "  ".join([f"{int(h):02d}h({v:.3f}%)" for h, v in top5.items()])
        print(f"  {sym:<10}  {hours_str}")

    # Save
    hourly.to_csv("research/daily_pattern_hourly.csv", index=False)
    dow.to_csv("research/daily_pattern_dow.csv", index=False)
    sess.to_csv("research/daily_pattern_sessions.csv", index=False)
    print("\n  ✅ Saved CSVs to research/")


if __name__ == "__main__":
    print("🔍 Daily Pattern Scanner — Empirical Market Behavior Analysis")
    print("   365 days × 1h bars × 8 symbols\n")
    run()
