# Backtest Summary

## What was done

1. **Intraday (M5)**
   - Tried tightening: `MIN_QUALITY_SCORE_INTRADAY = 5.5` and higher regime thresholds (0.7 / 0.9 / 1.1).
   - Result: PF and expectancy **worsened** (PF 1.24, expectancy 0.16R). Reverted to shared quality 5.0 and original thresholds (0.6 / 0.8 / 1.0).

2. **Swing (H1)**
   - Added `macro_bias` to the swing signal dict for optional use in sizing or logging.
   - Macro remains advisory-only for swing (does not block).

3. **60-day backtest**
   - With 60-day window, **no data** is returned for any symbol (Yahoo Finance 5m history limit).
   - Diagnostics: "No data loaded for any symbol" when `days=60`. Use **30 days** for a reliable dual backtest.

## Current 30-day results (after revert)

| Strategy   | Trades | Win Rate | Profit Factor | Expectancy |
|-----------|--------|----------|---------------|------------|
| Intraday (M5) | 7,047 | 34.37% | 1.31 | 0.20R |
| Swing (H1)    | 1,376 | 30.09% | **2.15** | **0.81R** |

- **Swing**: Strong (2.15 PF, 0.81R); `macro_bias` in signal for future use.
- **Intraday**: Marginal (1.31 PF, 0.20R); stricter quality/thresholds hurt, so kept current settings.
- **Longer backtest**: 60-day not viable with current data source; 30-day is the reference.

## How to run

```bash
cd smc-scalp-signals
source venv/bin/activate
PYTHONPATH=. python research/dual_backtest.py [days]
# Default 30. Example: python research/dual_backtest.py 30
# 60+ days: no data returned (data source limit); use 30 days.
```

## Documentation

- **README.md**: Updated to v22.0, current 30-day metrics, project structure, backtest command.
- **IMPROVEMENTS.md**: Trade-off addressal; MIN_QUALITY_SCORE default 5.0, MIN_QUALITY_SCORE_INTRADAY noted.
- **BACKTEST_REPORT_V22.md**: Current performance summary, swing fixes (ema_200, macro advisory), 60-day note.
- **.env.template**: MIN_QUALITY_SCORE=5.0, MIN_QUALITY_SCORE_INTRADAY=5.0.
