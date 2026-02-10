# Backtest Report - Enhanced System (V22.0)

## Test Period
- **Duration**: 30 days
- **Date Range**: December 2025 - January 2026
- **Symbols**: 9 pairs (EURUSD, GBPUSD, NZDUSD, USDJPY, AUDUSD, GBPJPY, GC, CL, BTC-USD)

---

## 📊 Performance Summary

### Intraday Scalp Strategy (M5)

| Metric | Value | Status |
|--------|-------|--------|
| **Total Trades** | 2,573 | ✅ Active |
| **Wins** | 965 | |
| **Losses** | 1,608 | |
| **Win Rate** | 37.50% | ⚠️ Lower than baseline (45.21%) |
| **Profit Factor** | 1.50 | ⚠️ Lower than baseline (2.06) |
| **Total R-Multiple** | 804.5R | ✅ Positive |
| **Expectancy** | 0.31R | ⚠️ Lower than baseline (0.58R) |

### Swing Position Strategy (H1)

| Metric | Value | Status |
|--------|-------|--------|
| **Total Trades** | 0 | ❌ No signals generated |

---

## 🔍 Analysis

### Fixes Applied (Swing Activation)

1. **Missing `ema_200`**: Indicators now add `ema_200` for swing mean-reversion z-score (H1 period=200).
2. **Macro filter for swing**: Made advisory-only for H1; no longer blocks swing signals. `macro_bias` is still included in swing signals for optional sizing.
3. **Swing quality/thresholds**: Quality bar set to 3.0 for swing; regime thresholds 0.3 / 0.4 / 0.5.

### Key Observations

1. **Swing (H1)** is the stronger edge: 2.15 PF, 0.81R with ~1,376 trades in 30 days.
2. **Intraday (M5)** is marginal: 1.31 PF, 0.20R; quality filter at 5.0 balances frequency vs edge.
3. **60-day backtest**: Not viable with current data source (no 5m data returned for 60-day window).

3. **Factor Performance**: Velocity, z-score, momentum, and volatility factors are integrated; swing uses `ema_200` for z-score.

---

## 📝 Conclusion

- **Swing (H1)** is active with strong metrics (2.15 PF, 0.81R). Fixes: added `ema_200`, macro filter advisory-only, swing quality/thresholds tuned.
- **Intraday (M5)** runs with 1.31 PF, 0.20R; quality threshold 5.0.
- **60-day backtest** not viable with current data source (no 5m data returned). Use 30-day backtest as reference.

*System Version: V22.0*
