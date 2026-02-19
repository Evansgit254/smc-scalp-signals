"""
Session Clock Strategy — Time-Based Exit Backtest (V1.2)
======================================================
Tests the pure directional expectancy:
1. Enter at Open of the signal hour.
2. Exit at Close of the SAME hour.
3. No SL/TP (except a catastrophic wide stop for safety).
"""
import asyncio
import yfinance as yf
import pandas as pd
import numpy as np
import warnings

warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

CLOCK_SIGNALS = {
    "CL=F":     [(21, "BUY"), (7, "SELL")],
    "BTC-USD":  [(21, "BUY"), (22, "BUY")],
    "GC=F":     [(16, "BUY"), (11, "BUY")],
    "EURUSD=X": [(8, "BUY"),  (16, "SELL")],
    "AUDUSD=X": [(22, "BUY")],
    "GBPJPY=X": [(21, "SELL"), (18, "BUY"), (23, "BUY")],
    "USDJPY=X": [(21, "SELL"), (18, "BUY")],
}

LABELS = {
    "CL=F": "OIL", "BTC-USD": "BTC", "GC=F": "GOLD",
    "EURUSD=X": "EURUSD", "AUDUSD=X": "AUDUSD",
    "GBPJPY=X": "GBPJPY", "USDJPY=X": "USDJPY",
}

def run():
    all_trades = []

    for ticker, label in LABELS.items():
        print(f"  Fetching {label}...")
        try:
            df = yf.download(ticker, period="365d", interval="1h",
                             progress=False, auto_adjust=True)
            if df.empty: continue
            
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0] for c in df.columns]

            df.index = pd.to_datetime(df.index)
            if df.index.tz is not None:
                df.index = df.index.tz_convert('UTC')

            signals = CLOCK_SIGNALS.get(ticker, [])

            for i in range(len(df)):
                ts  = df.index[i]
                if ts.dayofweek == 4: continue  # Skip Friday

                for (sig_hour, direction) in signals:
                    if ts.hour != sig_hour: continue

                    open_p  = df['Open'].iloc[i]
                    close_p = df['Close'].iloc[i]
                    
                    # Return in percent
                    ret = (close_p - open_p) / open_p * 100
                    if direction == "SELL":
                        ret = -ret
                    
                    all_trades.append({
                        'Symbol':    label,
                        'Timestamp': ts,
                        'Hour':      sig_hour,
                        'Direction': direction,
                        'Return%':   ret,
                        'IsWin':     ret > 0
                    })
        except Exception as e:
            print(f"    ❌ Error for {label}: {e}")

    if not all_trades:
        print("No trades generated.")
        return

    df_t = pd.DataFrame(all_trades)

    print("\n" + "="*70)
    print("  🕐 SESSION CLOCK — TIME-BASED EXIT (V1.2)")
    print("  Enter at Open, Exit at Close (Same Hour)")
    print("="*70)

    total  = len(df_t)
    wins   = df_t['IsWin'].sum()
    wr     = wins / total
    avg_ret = df_t['Return%'].mean()
    total_ret = df_t['Return%'].sum()

    print(f"\n  {'Total Trades':<25} {total}")
    print(f"  {'Win Rate':<25} {wr:.2%}")
    print(f"  {'Avg Return%':<25} {avg_ret:.4f}%")
    print(f"  {'Total Return%':<25} {total_ret:.2f}%")

    print("\n" + "="*70)
    print("  📊 PER-SYMBOL EXPECTANCY")
    print("="*70)
    print(f"  {'Symbol':<10} {'N':>5}  {'WinRate':>8}  {'AvgRet%':>9}")
    print("  " + "-"*45)
    for sym in df_t['Symbol'].unique():
        sub = df_t[df_t['Symbol'] == sym]
        n   = len(sub)
        wr_ = sub['IsWin'].mean()
        ar_ = sub['Return%'].mean()
        flag = "🟢" if ar_ > 0.005 else ("🔴" if ar_ < -0.005 else "⚪")
        print(f"  {flag} {sym:<9} {n:>5}  {wr_:>8.1%}  {ar_:>+9.4f}%")

    print("\n" + "="*70)
    print("  ⏰ PER-HOUR EXPECTANCY")
    print("="*70)
    print(f"  {'Symbol':<10} {'Hour':>5}  {'Dir':<5}  {'N':>5}  {'WinRate':>8}  {'AvgRet%':>9}")
    print("  " + "-"*55)
    grp = df_t.groupby(['Symbol', 'Hour', 'Direction'])
    for (sym, hr, dr), sub in grp:
        n   = len(sub)
        wr_ = sub['IsWin'].mean()
        ar_ = sub['Return%'].mean()
        flag = "🟢" if ar_ > 0.01 else ("🔴" if ar_ < -0.01 else "⚪")
        print(f"  {flag} {sym:<9} {hr:>5}h  {dr:<5}  {n:>5}  {wr_:>8.1%}  {ar_:>+9.4f}%")


if __name__ == "__main__":
    run()
