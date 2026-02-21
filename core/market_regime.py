"""
Market Regime Detector (V23.2)
==============================
Automatically classifies the market as TRENDING or RANGING
using ADX and ATR volatility across multiple symbols.

Based on backtested thresholds:
- ADX > 25 → TRENDING  → Quality threshold = 5.0 (normal)
- ADX 20-25 → MIXED    → Quality threshold = 6.5 (moderate filter)
- ADX < 20 → RANGING   → Quality threshold = 8.0 (strict filter)
"""

import numpy as np
import sqlite3
from datetime import datetime

# --- REGIME THRESHOLDS ---
ADX_TRENDING  = 25.0   # Strong trend
ADX_MIXED     = 20.0   # Transitioning
ADX_RANGING   = 20.0   # Choppy / sideways

# Quality scores per regime
QUALITY_TRENDING = 5.0
QUALITY_MIXED    = 6.5
QUALITY_RANGING  = 8.0


def _calc_adx(df, period=14) -> float:
    """Calculate Average Directional Index (ADX) from H1 OHLC data."""
    try:
        high  = df['high'].values if 'high' in df.columns else df['High'].values
        low   = df['low'].values  if 'low'  in df.columns else df['Low'].values
        close = df['close'].values if 'close' in df.columns else df['Close'].values

        n = len(close)
        if n < period + 5:
            return 20.0  # Neutral default

        # True Range
        tr_list = []
        for i in range(1, n):
            tr = max(high[i] - low[i],
                     abs(high[i] - close[i-1]),
                     abs(low[i]  - close[i-1]))
            tr_list.append(tr)

        # Directional Movement
        dm_plus  = [max(high[i] - high[i-1], 0) if (high[i] - high[i-1]) > (low[i-1] - low[i]) else 0 for i in range(1, n)]
        dm_minus = [max(low[i-1] - low[i], 0)   if (low[i-1] - low[i]) > (high[i] - high[i-1]) else 0 for i in range(1, n)]

        # Smooth over period (simple EMA-like)
        def smooth(arr, p):
            result = [sum(arr[:p]) / p]
            for v in arr[p:]:
                result.append(result[-1] * (p-1)/p + v / p)
            return result

        atr   = smooth(tr_list, period)
        pdm   = smooth(dm_plus, period)
        mdm   = smooth(dm_minus, period)

        min_len = min(len(atr), len(pdm), len(mdm))
        di_plus  = [100 * pdm[i] / atr[i] if atr[i] > 0 else 0 for i in range(min_len)]
        di_minus = [100 * mdm[i] / atr[i] if atr[i] > 0 else 0 for i in range(min_len)]
        dx       = [100 * abs(di_plus[i] - di_minus[i]) / (di_plus[i] + di_minus[i])
                    if (di_plus[i] + di_minus[i]) > 0 else 0 for i in range(min_len)]

        adx = smooth(dx, period)
        return round(adx[-1], 2) if adx else 20.0

    except Exception:
        return 20.0  # Neutral fallback


def detect_regime(h1_data_map: dict) -> dict:
    """
    Detect market regime from H1 data across symbols.
    
    Args:
        h1_data_map: {symbol: h1_dataframe} dict

    Returns:
        {
            'regime': 'TRENDING' | 'MIXED' | 'RANGING',
            'adx_avg': float,
            'quality_threshold': float,
            'detail': str
        }
    """
    adx_scores = []

    for symbol, df in h1_data_map.items():
        if df is None or df.empty:
            continue
        adx = _calc_adx(df)
        adx_scores.append(adx)

    if not adx_scores:
        return {
            'regime': 'MIXED',
            'adx_avg': 20.0,
            'quality_threshold': QUALITY_MIXED,
            'detail': 'No data — neutral defaults applied'
        }

    adx_avg = round(np.mean(adx_scores), 2)

    if adx_avg >= ADX_TRENDING:
        regime    = 'TRENDING'
        threshold = QUALITY_TRENDING
        detail    = f"ADX={adx_avg:.1f} — Market is TRENDING. Standard quality filter active."
    elif adx_avg >= ADX_MIXED:
        regime    = 'MIXED'
        threshold = QUALITY_MIXED
        detail    = f"ADX={adx_avg:.1f} — Market is MIXED. Moderate quality filter active."
    else:
        regime    = 'RANGING'
        threshold  = QUALITY_RANGING
        detail    = f"ADX={adx_avg:.1f} — Market is RANGING/CHOPPY. Strict quality filter active."

    return {
        'regime': regime,
        'adx_avg': adx_avg,
        'quality_threshold': threshold,
        'detail': detail
    }


def apply_regime_filter(regime_result: dict, db_clients_path: str):
    """
    Write the detected quality threshold to the system_config DB
    so _load_dynamic_config() picks it up automatically next cycle.
    """
    threshold = regime_result['quality_threshold']
    try:
        conn = sqlite3.connect(db_clients_path)
        conn.execute(
            "UPDATE system_config SET value=? WHERE key='MIN_QUALITY_SCORE'",
            (str(threshold),)
        )
        conn.commit()
        conn.close()
        print(f"🧠 REGIME: {regime_result['regime']} → Quality threshold set to {threshold}")
        print(f"   └─ {regime_result['detail']}")
    except Exception as e:
        print(f"⚠️  Could not apply regime filter: {e}")
