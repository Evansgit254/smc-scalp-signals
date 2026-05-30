#!/bin/bash

# Discovery: Get the directory where the script is located
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

case "$1" in
    status)
        echo "🏛️  Checking Pure Quant System Integrity..."
        python3 version.py
        echo "----------------------------------------"
        echo "Database Health:"
        [ -f "database/backtest_results.db" ] && echo "✅ Backtest results found" || echo "❌ Backtest results missing"
        [ -f "database/signals.db" ] && echo "✅ Signals ledger found" || echo "❌ Signals ledger missing"
        ;;
    backup)
        TIMESTAMP=$(date +%Y%m%d_%H%M%S)
        echo "💾 Archiving signals to backups/signals_backup_$TIMESTAMP.db"
        mkdir -p backups
        cp database/signals.db backups/signals_backup_$TIMESTAMP.db
        ;;
    test)
        pytest -m authentic
        ;;
    *)
        echo "Usage: ./manage.sh {status|backup|test}"
        ;;
esac
