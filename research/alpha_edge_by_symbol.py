"""
Per-Symbol Alpha Edge Analysis
Calculates IC for each alpha factor broken down by symbol and regime.
This tells us WHICH factors work for WHICH instruments.
"""
import yfinance as yf
import pandas as pd
import numpy as np
from scipy.stats import spearmanr
import warnings

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

FWD_BARS = 4  # 4-hour forward return on 1h data


# ── Helpers ──────────────────────────────────────────────────────────────────

def atr(df, n=14):
    hl = df['High'] - df['Low']
    hc = (df['High'] - df['Close'].shift()).abs()
    lc = (df['Low']  - df['Close'].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.rolling(n).mean()

def adx(df, n=14):
    pdm = df['High'].diff().clip(lower=0)
    ndm = (-df['Low'].diff()).clip(lower=0)
    tr1 = atr(df, 1)
    tr_s  = tr1.ewm(alpha=1/n, adjust=False).mean()
    pdi   = 100 * pdm.ewm(alpha=1/n, adjust=False).mean() / tr_s
    ndi   = 100 * ndm.ewm(alpha=1/n, adjust=False).mean() / tr_s
    dx    = (pdi - ndi).abs() / (pdi + ndi).abs() * 100
    return dx.ewm(alpha=1/n, adjust=False).mean()

def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()

def slope_pct(s, n=3):
    shifted = s.shift(n).replace(0, np.nan)
    return ((s - shifted) / shifted) * 100


# ── Alpha Factors (vectorized) ────────────────────────────────────────────────

def alpha_velocity(df, n=20):
    def _slope(y):
        x = np.arange(len(y))
        return np.polyfit(x, y, 1)[0] if len(y) >= 2 else 0.0
    slp = df['Close'].rolling(n).apply(_slope, raw=True)
    return slp / df['atr']

def alpha_zscore(df, n=100):
    dist = df['Close'] - ema(df['Close'], n)
    std  = df['Close'].rolling(n).std()
    return -1 * (dist / std)   # inverted: high z → expect reversion

def alpha_momentum(df, s=10, l=30):
    roc_s = df['Close'].pct_change(s)
    roc_l = df['Close'].pct_change(l)
    return (roc_s - roc_l) / (df['atr'] * 10000)

def alpha_momentum_inv(df, s=10, l=30):
    return -1 * alpha_momentum(df, s, l)


# ── Regime ────────────────────────────────────────────────────────────────────

def regime(df):
    vr  = df['atr'] / df['atr'].rolling(50).mean()
    adx_s = df['adx']
    slp = slope_pct(ema(df['Close'], 50), 3)

    choppy   = (vr < 0.9) | (adx_s < 20)
    trending = (vr > 1.2) & (slp.abs() > 0.05) & (adx_s > 25)

    return np.select([choppy, trending], ['CHOPPY', 'TRENDING'], default='RANGING')


# ── IC helper ─────────────────────────────────────────────────────────────────

def ic(x, y):
    mask = x.notna() & y.notna()
    if mask.sum() < 50:
        return np.nan
    r, _ = spearmanr(x[mask], y[mask])
    return round(r, 4)


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    rows = []

    for ticker, label in SYMBOLS.items():
        print(f"  Fetching {label} ({ticker})...")
        try:
            df = yf.download(ticker, period="60d", interval="1h",
                             progress=False, auto_adjust=True)
            if df.empty:
                print(f"    ⚠ No data"); continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            df['atr']  = atr(df)
            df['adx']  = adx(df)
            df['regime'] = regime(df)

            df['vel']  = alpha_velocity(df)
            df['zsc']  = alpha_zscore(df)
            df['mom']  = alpha_momentum(df)
            df['momi'] = alpha_momentum_inv(df)

            df['fwd']  = df['Close'].shift(-FWD_BARS) / df['Close'] - 1.0
            df = df.dropna()

            for reg in ['TRENDING', 'RANGING', 'CHOPPY', 'ALL']:
                sub = df if reg == 'ALL' else df[df['regime'] == reg]
                n   = len(sub)
                rows.append({
                    'Symbol':  label,
                    'Regime':  reg,
                    'N':       n,
                    'IC_Vel':  ic(sub['vel'],  sub['fwd']),
                    'IC_ZSc':  ic(sub['zsc'],  sub['fwd']),
                    'IC_Mom':  ic(sub['mom'],  sub['fwd']),
                    'IC_MomI': ic(sub['momi'], sub['fwd']),
                })
        except Exception as e:
            print(f"    ❌ {e}")

    result = pd.DataFrame(rows)

    # ── Print report ──────────────────────────────────────────────────────────
    print("\n" + "="*80)
    print("  PER-SYMBOL ALPHA EDGE REPORT  (IC = Spearman rank correlation)")
    print("  IC > 0.05 = Good  |  IC > 0.10 = Strong  |  Negative = Harmful")
    print("="*80)

    for sym in result['Symbol'].unique():
        sub = result[result['Symbol'] == sym]
        print(f"\n{'─'*80}")
        print(f"  {sym}")
        print(f"  {'Regime':<12} {'N':>5}  {'Velocity':>10}  {'Z-Score':>10}  {'Momentum':>10}  {'Mom-Inv':>10}")
        print(f"  {'─'*70}")
        for _, row in sub.iterrows():
            def fmt(v):
                if pd.isna(v): return "     N/A  "
                star = "🟢" if v > 0.05 else ("🔴" if v < -0.02 else "⚪")
                return f"{star}{v:+.4f}"
            print(f"  {row['Regime']:<12} {int(row['N']):>5}  "
                  f"{fmt(row['IC_Vel']):>12}  {fmt(row['IC_ZSc']):>12}  "
                  f"{fmt(row['IC_Mom']):>12}  {fmt(row['IC_MomI']):>12}")

    print("\n" + "="*80)
    print("  BEST FACTOR PER SYMBOL (TRENDING regime only)")
    print("="*80)
    trend = result[result['Regime'] == 'TRENDING'].copy()
    factor_cols = ['IC_Vel', 'IC_ZSc', 'IC_Mom', 'IC_MomI']
    factor_names = {'IC_Vel': 'Velocity', 'IC_ZSc': 'Z-Score',
                    'IC_Mom': 'Momentum', 'IC_MomI': 'Mom-Inv'}
    for _, row in trend.iterrows():
        vals = {k: row[k] for k in factor_cols if not pd.isna(row[k])}
        if not vals: continue
        best_k = max(vals, key=vals.get)
        print(f"  {row['Symbol']:<10}  Best: {factor_names[best_k]:<12}  IC={vals[best_k]:+.4f}")

    print()

    # Save CSV
    result.to_csv("research/alpha_edge_by_symbol.csv", index=False)
    print("  ✅ Saved to research/alpha_edge_by_symbol.csv")


if __name__ == "__main__":
    print("🚀 Per-Symbol Alpha Edge Analysis")
    print("   60 days × 1h bars × 8 symbols\n")
    run()
