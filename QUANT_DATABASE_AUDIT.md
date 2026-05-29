# Quant Database Audit

Audit date: 2026-05-29

System version: `5.2.0-research`

Primary evidence sources:

- `database/backtest_results.db`
- `database/signals.db`
- `database/clients.db`

## Backtest Baseline

Latest benchmark run: Run ID `58`

Date range: `2026-05-01` to `2026-05-29`

Closed-trade totals:

| Metric | Value |
| :--- | ---: |
| Closed trades | 8,901 |
| Win rate | 58.68% |
| Net result | +856.59R |
| Profit factor | 1.23 |
| Computed max drawdown | 463.56R |

Strategy breakdown:

| Strategy | Closed Trades | Win Rate | Net R | Avg R | Profit Factor | Status |
| :--- | ---: | ---: | ---: | ---: | ---: | :--- |
| CRT H1 | 8,115 | 61.77% | +1,029.52 | +0.127 | 1.33 | Research-active |
| Advanced Patterns | 19 | 73.68% | +15.90 | +0.837 | 4.18 | Promising but under-sampled |
| SMC Sweep | 767 | 25.55% | -188.82 | -0.246 | 0.67 | Quarantined |

## Engineering Interpretation

The current database supports continued research on CRT and Session Clock style models. It does not support live-profitability claims. Run `58` is positive overall, but drawdown and trade density are too large for institutional-readiness claims without stricter exposure modeling and broker-side execution evidence.

SMC Sweep is negative in Run `58` and negative in aggregate historical backtests. It is disabled by default and excluded from default backtests unless explicitly requested.

## Active Ledger Evidence

`database/signals.db` currently shows:

- 14 signals
- 10 blocked signals
- 4 open signals with `execution_status=NONE`
- 7 orders
- 7 fills
- all orders/fills are `PAPER_EXECUTED`
- no active live broker fills

Execution evidence is paper-only. Any production/live claims must wait for broker-side orders, fills, slippage, commission, swap, and reconciliation records.

## Current Known Limitations

- `yfinance` remains a fallback market-data source.
- SQLite is still the active control/execution database.
- Backtest trade density remains high and must be interpreted as research output.
- Quality score is not yet a calibrated probability or monotonic edge ranker.
- Paper account balance and client account balance are not the same ledger.
