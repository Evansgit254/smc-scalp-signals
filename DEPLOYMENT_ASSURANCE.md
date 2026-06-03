# Deployment Assurance: v5.3.0-stable

This document details exactly what is inside the refactored system being deployed.

## Current Evidence Boundary

Database audit baseline: `database/backtest_results.db`, Run ID `63`, generated on `2026-05-29`.

- The active ledger shows paper execution only.
- Run `63` definitively resolved the cross-run ExecutionGate pollution bug.
- Current win rate baseline: **70.9%** across 2,772 trades.
- Active strategy scope is limited to CRT and Advanced Pattern.

## Current Safety Controls

- Stripe webhook handling now requires `STRIPE_WEBHOOK_SECRET` unless `ALLOW_UNSIGNED_STRIPE_WEBHOOK=true` is explicitly set for development.
- `mt5_auto_trade` and `mt5_paper_mode` are treated as live-trading controls and require `risk_manager` access to change through the admin API.
- Signal delivery reservation now fails closed when the dedupe database is unavailable, preventing duplicate broadcast or execution on storage faults.
- Test coverage is split into `authentic`, `integration`, and `live` markers so external dependencies can be isolated from default local runs.

## 1. The Safety Layers (Gates)

We are deploying a **Triple-Gate** system. A signal must pass all three to reach your Telegram/MT5:

| Layer | Gate | Purpose |
| :--- | :--- | :--- |
| **Trend Guard** | EMA 200 | Blocks "Counter-Trend" buys below the EMA or sells above it. Ensures we trade with the intermediate-term momentum. |
| **Structural Boost**| ICT Confluence | CRT setups must show a "Sweep Extreme" or high displacement. Without this structural signature, the quality score remains low. |
| **Quality Gate** | 7.0 Threshold | The system blocks any signal with a Quality Score below 7.0. Because we added the "Institutional Boost," only the cleanest CRT setups will pass this gate. |

## 2. Why this is "Safer" than the old VM System

- **Old VM System**: Used broader legacy strategy surfaces that often ignored the tighter CRT/Advanced Pattern evidence boundary.
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
- [x] Stripe webhook signature enforcement: **ACTIVE**
- [x] Live trading config protection: **ACTIVE**
- [x] Delivery reservation fail-closed: **ACTIVE**
- [x] Path Independence: **VERIFIED**
- [x] Strategy scope: **CRT + ADVANCED PATTERN ONLY**
- [ ] Live broker fill evidence: **NOT YET VERIFIED**
