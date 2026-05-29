# Deployment Assurance: v5.2.0-research

This document details exactly what is inside the refactored system being deployed.

## Current Evidence Boundary

Database audit baseline: `database/backtest_results.db`, Run ID `58`, generated on `2026-05-29`.

- The active ledger shows paper execution only: `7` `PAPER_EXECUTED` orders/fills in `database/signals.db`.
- No active database record proves live broker fills, live slippage, or live profitability.
- SMC Sweep is quarantined by default after Run `58` and aggregate historical runs showed negative expectancy.

## 1. The Safety Layers (Gates)

We are deploying a **Triple-Gate** system. A signal must pass all three to reach your Telegram/MT5:

| Layer | Gate | Purpose |
| :--- | :--- | :--- |
| **Trend Guard** | EMA 200 | Blocks "Counter-Trend" buys below the EMA or sells above it. Ensures we trade with the intermediate-term momentum. |
| **Structural Boost**| ICT Confluence | CRT setups must show a "Sweep Extreme" or high displacement. Without this structural signature, the quality score remains low. |
| **Quality Gate** | 7.0 Threshold | The system blocks any signal with a Quality Score below 7.0. Because we added the "Institutional Boost," only the cleanest CRT setups will pass this gate. |

## 2. Why this is "Safer" than the old VM System

- **Old VM System**: Used a simpler Swing strategy that often ignored the broader H1 trend and lacked a rigorous quality scoring mechanism. It was prone to "price bounce flooding."
- **Refactored System**:
    - **Deduplication**: Uses an MD5 hash of (Symbol + Direction + Timeframe) to ensure you don't get 5 alerts for the same trade.
    - **Regime Awareness**: Detects if the market is "Trending" or "Ranging" and adjusts weights dynamically.
    - **Fixed Execution Bias**: Backtesting now uses the production `ExecutionGate` with timestamp-aware open-position checks.

## 3. New Performance Metrics (R-Multiples)

We are moving away from "Pips" because they are misleading across different symbols.
- **Reporting**: All backtests and live results will show performance in **R**.
- **The edge**: Run-level and strategy-level results must cite an exact database run ID and date range.

## 4. The "Fresh Start" Protocol

- **Empty Database**: Starting with a clean `signals.db`.
- **Portable Code**: Path-independent logic works everywhere.
- **Auto-Deployment**: `fresh_deploy.sh` handles the migration exactly as verified locally.

---

### Assurance Checklist
- [x] EMA 200 Filter: **ACTIVE**
- [x] Quality Score: **ACTIVE** (`min_quality_score=8.0` in active DB)
- [x] MT5 Auto-Trade: **PAPER MODE** (Safe Start)
- [x] Deduplication: **ACTIVE** (45 min window)
- [x] Path Independence: **VERIFIED**
- [x] SMC Sweep: **QUARANTINED BY DEFAULT**
- [ ] Live broker fill evidence: **NOT YET VERIFIED**
