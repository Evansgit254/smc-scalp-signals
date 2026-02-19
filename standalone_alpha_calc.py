import yfinance as yf
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from scipy.stats import spearmanr
import warnings

warnings.simplefilter(action='ignore', category=FutureWarning)

def calculate_atr(df, period=14):
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    return true_range.rolling(period).mean()

def calculate_adx(df, period=14):
    """Calculate ADX for trend strength."""
    plus_dm = df['High'].diff()
    minus_dm = df['Low'].diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm > 0] = 0
    
    tr = calculate_atr(df, period=1).rolling(period).sum()
    plus_di = 100 * (plus_dm.ewm(alpha=1/period).mean() / tr)
    minus_di = 100 * (abs(minus_dm).ewm(alpha=1/period).mean() / tr)
    dx = (abs(plus_di - minus_di) / abs(plus_di + minus_di)) * 100
    return dx.rolling(period).mean()

def run_standalone_alpha():
    symbols = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "GC=F", "BTC-USD"]
    print(f"🚀 Starting Standalone Alpha Calculation for {len(symbols)} symbols...")
    
    combined_data = []
    
    for symbol in symbols:
        print(f"Fetching {symbol}...")
        try:
            df = yf.download(symbol, period="60d", interval="1h", progress=False, auto_adjust=True)
            
            if df is None or df.empty:
                print(f"❌ Empty data for {symbol}")
                continue
                
            # Flatten columns if MultiIndex
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            # Calculate Indicators
            df['atr'] = calculate_atr(df)
            df['adx'] = calculate_adx(df)
            
            # Define Regimes
            # ADX > 25 = Trending, ADX < 20 = Ranging (Simplified)
            df['regime'] = np.where(df['adx'] > 25, 'TRENDING', 
                                  np.where(df['adx'] < 20, 'RANGING', 'NORMAL'))
            
            # --- ALPHA FACTORS ---
            # 1. Velocity (Linear Regression Slope normalized by ATR)
            def get_slope(series):
                y = series.values
                x = np.arange(len(y))
                if len(y) < 2: return 0
                return np.polyfit(x, y, 1)[0]
            
            df['slope'] = df['Close'].rolling(20).apply(get_slope, raw=False)
            df['alpha_velocity'] = df['slope'] / df['atr']
            
            # 2. Z-Score (Mean Reversion)
            df['ema_100'] = df['Close'].ewm(span=100).mean()
            df['dist'] = df['Close'] - df['ema_100']
            df['std_100'] = df['Close'].rolling(100).std()
            df['alpha_zscore'] = -1 * (df['dist'] / df['std_100']) # Inverted: Revert to mean!
            
            # 3. Momentum (ROC Divergence)
            df['roc_10'] = df['Close'].pct_change(10)
            df['roc_30'] = df['Close'].pct_change(30)
            # Original was (ROC10 - ROC30), implying acceleration. 
            # If previous IC was negative, maybe it's mean reverting?
            # Let's keep original but rename, and add inverted
            df['alpha_momentum'] = (df['roc_10'] - df['roc_30']) / df['atr']
            df['alpha_momentum_inv'] = -1 * df['alpha_momentum']
            
            # --- FORWARD RETURNS ---
            df['fwd_return'] = df['Close'].shift(-12) / df['Close'] - 1.0 # 12-bar (12h) forward return
            
            df = df.dropna()
            print(f"✅ Processed {len(df)} bars for {symbol}")
            combined_data.append(df)
            
        except Exception as e:
            print(f"❌ Error {symbol}: {e}")

    if not combined_data:
        print("❌ No data collected.")
        return

    full_df = pd.concat(combined_data)
    
    alphas = ['alpha_velocity', 'alpha_zscore', 'alpha_momentum', 'alpha_momentum_inv']
    
    print("\n📊 INFORMATION COEFFICIENT (IC) REPORT (ALL REGIMES)")
    print("="*60)
    print(f"{'Alpha Factor':<25} | {'IC':<8} | {'Strength'}")
    print("-" * 60)
    for alpha in alphas:
        ic, p = spearmanr(full_df[alpha], full_df['fwd_return'])
        strength = "⭐⭐⭐" if abs(ic) > 0.1 else "⭐⭐" if abs(ic) > 0.05 else "⭐"
        print(f"{alpha:<25} | {ic:.4f}   | {strength}")
        
    # Correlation Matrix
    print("\n🔄 FACTOR CORRELATION MATRIX")
    print("="*60)
    corr_matrix = full_df[alphas].corr()
    print(corr_matrix.round(2))

    # Regime Analysis
    print("\n🌍 REGIME-BASED IC ANALYSIS")
    print("="*60)
    for regime in ['TRENDING', 'RANGING', 'NORMAL']:
        subset = full_df[full_df['regime'] == regime]
        print(f"\n--- {regime} ({len(subset)} bars) ---")
        if len(subset) < 100:
            print("  (Insufficient Data)")
            continue
        for alpha in alphas:
            ic, p = spearmanr(subset[alpha], subset['fwd_return'])
            print(f"  {alpha:<20}: {ic:.4f}")

    print("\n🔍 ALIGNMENT AUDIT (Win Rate vs. Factor Count)")
    print("="*60)
    
    # We suspect Velocity + Z-Score (Mean Rev) + Momentum Inv might be the combo
    selected_alphas = ['alpha_velocity', 'alpha_zscore', 'alpha_momentum_inv']
    
    for alpha in selected_alphas:
        full_df[f'{alpha}_sign'] = np.sign(full_df[alpha])
    
    full_df['pos_factors'] = (full_df[[f'{a}_sign' for a in selected_alphas]] > 0).sum(axis=1)
    full_df['is_win'] = full_df['fwd_return'] > 0
    
    print(f"Testing Combination: {', '.join(selected_alphas)}")
    for i in range(len(selected_alphas) + 1):
        subset = full_df[full_df['pos_factors'] == i]
        if len(subset) > 0:
            wr = subset['is_win'].mean()
            print(f"{i} Factors Aligned      | {wr:.2%} ({len(subset)})")

if __name__ == "__main__":
    run_standalone_alpha()
