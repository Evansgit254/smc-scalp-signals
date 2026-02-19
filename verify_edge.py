import yfinance as yf
import pandas as pd
import numpy as np
from scipy.stats import spearmanr
import warnings

# Suppress warnings
warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

def calculate_atr(df, period=14):
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    return true_range.rolling(period).mean()

def calculate_adx(df, period=14):
    """Calculate ADX for trend strength (Wilder's Smoothing)"""
    high = df['High']
    low = df['Low']
    close = df['Close']
    
    plus_dm = high.diff()
    minus_dm = low.diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm > 0] = 0
    
    tr = calculate_atr(df, period=1) # True Range for 1 period
    
    # Smooth with EMA (alpha=1/period) which mimics Wilder
    tr_smooth = tr.ewm(alpha=1/period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / tr_smooth)
    minus_di = 100 * (abs(minus_dm).ewm(alpha=1/period, adjust=False).mean() / tr_smooth)
    
    dx = (abs(plus_di - minus_di) / abs(plus_di + minus_di)) * 100
    adx = dx.ewm(alpha=1/period, adjust=False).mean()
    return adx

def calculate_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def calculate_slope(series, period=3):
    """Normalized slope for regime detection"""
    shift_val = series.shift(period)
    # Avoid division by zero
    slope = ((series - shift_val) / shift_val.replace(0, np.nan)) * 100
    return slope

# --- ALPHA FACTORS ---

def calculate_velocity_alpha(df, period=20):
    def get_slope(y):
        if len(y) < 2: return 0
        x = np.arange(len(y))
        return np.polyfit(x, y, 1)[0]
    
    slope = df['Close'].rolling(period).apply(get_slope, raw=True)
    atr = df['atr']
    return slope / atr

def calculate_zscore_alpha(df, period=100):
    ema = calculate_ema(df['Close'], period)
    dist = df['Close'] - ema
    std = df['Close'].rolling(period).std()
    return -1 * (dist / std)

def calculate_momentum_alpha(df, short_period=10, long_period=30):
    roc_short = df['Close'].pct_change(short_period)
    roc_long = df['Close'].pct_change(long_period)
    atr = df['atr']
    return (roc_short - roc_long) / (atr * 10000)

# --- CORE LOGIC UPDATE ---

def detect_regime(df):
    """
    Reflects V22.1 Hardened Regime Logic
    """
    # 1. Volatility Ratio
    df['vol_ratio'] = df['atr'] / df['atr'].rolling(50).mean()
    
    # 2. ADX
    df['adx'] = calculate_adx(df)
    
    # 3. Trend Slope
    ema_50 = calculate_ema(df['Close'], 50)
    df['ema_slope'] = calculate_slope(ema_50, 3)
    
    # 4. Vectorized Decision Logic
    # CHOPPY: Vol Ratio < 0.9 OR ADX < 20
    is_choppy = (df['vol_ratio'] < 0.9) | (df['adx'] < 20)
    
    # TRENDING: Vol > 1.2 AND Slope AND ADX > 25
    is_trending = (df['vol_ratio'] > 1.2) & (df['ema_slope'].abs() > 0.05) & (df['adx'] > 25)
    
    conditions = [is_choppy, is_trending]
    choices = ['CHOPPY', 'TRENDING']
    
    df['regime'] = np.select(conditions, choices, default='RANGING')
    return df

def combine_signals(df):
    """
    Reflects V22.1 Optimized Weights
    """
    df['combined_alpha'] = 0.0
    
    # TRENDING: Velocity 0.7, Z 0.1, Mom 0.2
    mask = df['regime'] == 'TRENDING'
    df.loc[mask, 'combined_alpha'] = (
        0.7 * df.loc[mask, 'alpha_velocity'].clip(-4, 4) +
        0.1 * df.loc[mask, 'alpha_zscore'].clip(-4, 4) +
        0.2 * df.loc[mask, 'alpha_momentum'].clip(-4, 4)
    )
    
    # RANGING: Standard
    mask = df['regime'] == 'RANGING'
    df.loc[mask, 'combined_alpha'] = (
        0.3 * df.loc[mask, 'alpha_velocity'].clip(-4, 4) +
        0.5 * df.loc[mask, 'alpha_zscore'].clip(-4, 4) +
        0.1 * df.loc[mask, 'alpha_momentum'].clip(-4, 4)
    )
    
    # CHOPPY: ZERO (Hard Block)
    mask = df['regime'] == 'CHOPPY'
    df.loc[mask, 'combined_alpha'] = 0.0
    
    return df

def run_verify():
    symbols = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "BTC-USD"]
    print(f"🚀 Verifying Edge (HARDENED V22.1) for {len(symbols)} symbols...")
    
    all_data = []
    
    for symbol in symbols:
        try:
            print(f"Fetching {symbol}...")
            df = yf.download(symbol, period="60d", interval="1h", progress=False, auto_adjust=True)
            
            if df.empty: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
                
            df['atr'] = calculate_atr(df)
            df['alpha_velocity'] = calculate_velocity_alpha(df)
            df['alpha_zscore'] = calculate_zscore_alpha(df)
            df['alpha_momentum'] = calculate_momentum_alpha(df)
            
            df = detect_regime(df)
            df = combine_signals(df)
            
            # Forward Returns
            df['fwd_ret'] = df['Close'].shift(-4) / df['Close'] - 1.0
            
            df = df.dropna()
            all_data.append(df)
            
        except Exception as e:
            print(f"❌ Error {symbol}: {e}")
            
    if not all_data: return

    full_df = pd.concat(all_data)
    
    print("\n📊 EDGE VERIFICATION REPORT (HARDENED)")
    print("="*60)
    
    # Filter out CHOPPY for "Active" IC calculation
    active_df = full_df[full_df['regime'] != 'CHOPPY']
    
    IC, p_val = spearmanr(active_df['combined_alpha'], active_df['fwd_ret'])
    print(f"\n🏆 Active Information Coefficient (IC): {IC:.4f} (p={p_val:.4f})")
    print(f"   (Excludes Choppy Regimes)")
    
    print("\n🌍 Regime Breakdown:")
    for regime in ['TRENDING', 'RANGING', 'CHOPPY']:
        subset = full_df[full_df['regime'] == regime]
        count = len(subset)
        if count < 50: 
            print(f"  - {regime:<10}: (Insufficient Data)")
            continue
            
        ic_r, _ = spearmanr(subset['combined_alpha'], subset['fwd_ret'])
        print(f"  - {regime:<10}: IC = {ic_r:.4f} ({count} bars)")

if __name__ == "__main__":
    run_verify()
