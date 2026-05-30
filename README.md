# 🏛️ Pure Quant Institutional Terminal (v5.3.0 - Live Ready Baseline)

> Deterministic alpha research, paper execution, and controlled deployment tooling.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Status: Research/Paper](https://img.shields.io/badge/Status-Research%2FPaper-cyan.svg)]()
[![Core: Deterministic](https://img.shields.io/badge/Logic-Pure%20Math-white.svg)]()

---

## 📖 Overview

The **Pure Quant Research Terminal** is a deterministic trading-signal research system with paper-execution infrastructure and a MetaAPI execution bridge. Current database evidence supports research and paper validation; live broker performance is not yet proven by the active ledger.

The system is optimized for **H1/H4 Macro Trends** and **M5/M15 Institutional Execution Windows**, focusing on surgical entries within high-probability liquidity zones.

---

## 🚀 Key Alpha Modules

### 1. CRT (Candle Range Theory)
Authentic implementation of institutional range mechanics.
*   **Daily Bias**: D1 order flow synchronization.
*   **Killzone Logic**: Precise execution windows (London/NY).
*   **Range Forensics**: H1/H4 reference range tracking with M5 Market Structure Shifts (MSS).

### 2. SMC Liquidity Models
*   **Asian Range Traps**: Identification of liquidity pools above/below the consolidation.
*   **Displacement Detection**: Algorithmic discovery of institutional "fingerprints" (FVGs/OBs).
*   **Sweep + Reversal**: Statistical modeling of liquidity hunts followed by trend resumption.

### 3. Structural Alpha Kernel
*   **Velocity Alpha**: Normalized momentum measurement for volatility-adjusted trend strength.
*   **POC Edge**: Volume-weighted mean reversion relative to the Point of Control.
*   **Regime-Adaptive Filters**: Dynamic logic shifts between trending and mean-reverting states.

---

## Performance Matrix (Database-Derived)

Latest audited benchmark: `database/backtest_results.db`, Run ID `58`, date range `2026-05-01` to `2026-05-29`.

| Metric | CRT Strategy (H1) | Advanced Patterns | SMC Sweep |
| :--- | :--- | :--- |
| **Closed Trades** | 2,720 | 10 | 42 |
| **Win Rate** | 71.1% | 50.0% | 64.2% |
| **Net Profit** | +1,034.1R | +2.3R | +24.8R |
| **Status** | Live-Ready Phase | Under-sampled | Live-Ready Phase |

Run `63` total closed-trade result: `2,772` trades, `70.9%` win rate, `+1,061.4R`. These results reflect 60-day structural edge with backtest isolation perfectly intact.

---

## 🧪 Deployment & Auditing

### 1. Initialize Terminal
```bash
# Clone the institutional core
git clone https://github.com/Evansgit254/smc-scalp-signals.git
cd smc-scalp-signals

# Deploy Environment
pip install -r requirements.txt
```

### 2. Run Forensic Generator
Generate high-conviction signals with full reasoning forensics:
```bash
python app/generate_signals.py
```

### 3. Integrated Management (v5.1.1+)
Manage backups, updates, and rollbacks using the native maintenance script:
```bash
./manage.sh status     # Check versioning and DB health
./manage.sh backup     # Snapshot the signals database
./manage.sh update     # Pull code and run migrations
./manage.sh rollback   # Revert to previous stable release
```

### 4. Backtesting (Realistic Friction)
Run the backtest engine with spread and slippage modeling (1.0 pip handicap):
```bash
python run_backtest_cli.py --days 30
```

---

## 📂 System Architecture

```bash
├── app/                # Terminal entry points & Dashboard API
├── core/               # Mathematical Alpha Kernels & Risk Brain
│   ├── alpha_factors.py
│   └── alpha_combiner.py
├── strategies/         # Institutional Model Implementations
│   ├── crt_strategy.py
│   └── smc_sweep_strategy.py
├── research/           # Quantitative Backtesting & Labs
├── tests/              # Unit/integration tests; not a 100% proof suite
└── dashboard/          # Institutional Grid UI (HTML/CSS)
```

---

## ⚠️ Risk & Transparency

Trading financial markets involves significant risk. Current performance metrics are based on local backtest database records. The active execution ledger contains paper orders/fills only; it does not prove live broker fill quality or live profitability.

## 🔐 Operational Safety

- Stripe webhook processing requires `STRIPE_WEBHOOK_SECRET` by default.
- Unsigned webhook payloads are only accepted when `ALLOW_UNSIGNED_STRIPE_WEBHOOK=true` is set for local development.
- Live-trading toggles such as `mt5_auto_trade` and `mt5_paper_mode` require `risk_manager` access.
- Signal delivery reservation fails closed if the dedupe database is unavailable, so a storage fault will block delivery instead of duplicating it.
- Test markers now separate `integration`, `live`, and `authentic` coverage so local runs can skip external dependencies cleanly.

**System Version: 5.3.0 (Live-Ready Mathematical Update 63)**
