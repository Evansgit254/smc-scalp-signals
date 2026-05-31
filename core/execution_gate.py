import sqlite3
import math
from datetime import datetime
from typing import Dict, Optional
from core.db_utils import connect_sqlite

class ExecutionGate:
    """
    Standardizes signal validation and inventory management.
    Ensures data integrity across live and simulated trading environments.
    """

    @staticmethod
    def validate(signal: Dict, db_signals: str, db_clients: str,
                 table_name: str = 'signals', current_ts: Optional[datetime] = None) -> Dict[str, str]:
        """
        Validates a signal against institutional risk and inventory rules.
        """
        try:
            # 1. Load Configuration
            symbol = signal.get('symbol')
            if not symbol:
                return {"status": "BLOCKED", "reason": "MISSING_SYMBOL"}
            
            entry_price = signal.get('entry_price')
            if entry_price is None or float(entry_price) <= 0.0:
                return {"status": "BLOCKED", "reason": "MISSING_EXECUTABLE_ENTRY"}
            
            # 2. Safety Check: Mandatory Risk Margin
            sl = signal.get('sl')
            try:
                if sl is None:
                    return {"status": "BLOCKED", "reason": "MISSING_STOP_LOSS"}
                
                entry_f = float(entry_price)
                sl_f = float(sl)
                risk_dist = abs(entry_f - sl_f)
                
                is_crypto = any(coin in symbol for coin in ["BTC", "ETH", "SOL", "BNB"])
                min_dist = 10.0 if is_crypto else 0.00005 # 10 points for crypto, 0.5 pips for FX
                
                if risk_dist < min_dist:
                    return {"status": "BLOCKED", "reason": f"INSUFFICIENT_RISK_MARGIN: {risk_dist:.5f} < {min_dist}"}
            except (TypeError, ValueError):
                return {"status": "BLOCKED", "reason": "INVALID_PRICE_DATA"}

            # 3. Inventory Check (No Pyramiding)
            run_id = signal.get('run_id')
            if ExecutionGate._has_open_position(symbol, db_signals, table_name, current_ts, run_id):
                return {"status": "BLOCKED", "reason": f"EXISTING_POSITION_IN_{symbol}"}

            # 3. Quality Assurance
            quality = float(signal.get('quality_score', 0.0) or 0.0)
            if math.isnan(quality):
                return {"status": "BLOCKED", "reason": "CORRUPT_SIGNAL_QUALITY (NaN)"}

            # 4. Threshold Validation
            thresholds = ExecutionGate._get_thresholds(db_clients)
            min_quality = thresholds.get('MIN_EXECUTION_QUALITY', 5.0)
            if quality < min_quality:
                return {"status": "BLOCKED", "reason": f"INSUFFICIENT_QUALITY ({quality:.2f})"}

            max_daily_loss = thresholds.get('MAX_DAILY_LOSS_PCT')
            if max_daily_loss is not None and ExecutionGate._daily_loss_breached(db_signals, max_daily_loss, current_ts):
                return {"status": "BLOCKED", "reason": f"DAILY_LOSS_LIMIT_REACHED ({max_daily_loss:.2f}%)"}

            # 5. Volatility (ATR) Gate
            current_atr = signal.get('current_atr')
            avg_atr = signal.get('avg_atr')
            try:
                if current_atr and avg_atr and avg_atr > 0.0:
                    if current_atr < (avg_atr * 0.95):
                        return {"status": "BLOCKED", "reason": f"LOW_VOLATILITY_CHOP ({current_atr:.5f} < {avg_atr*0.95:.5f})"}
            except Exception as e:
                import traceback
                print("ATR GATE ERROR:")
                traceback.print_exc()

            # 6. Trailing Drawdown Kill-Switch (Dynamic System Defense)
            strategy_name = signal.get('trade_type') or signal.get('strategy_name', '')
            try:
                with connect_sqlite(db_signals) as conn:
                    strategy_col = "strategy_name"
                    try:
                        cols = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
                        col_names = {row["name"] for row in cols}
                        if "strategy_name" not in col_names and "strategy" in col_names:
                            strategy_col = "strategy"
                    except Exception:
                        pass
                    run_id_clause = " AND run_id = ? " if run_id is not None else ""
                    params = [symbol, strategy_name]
                    if run_id is not None:
                        params.append(run_id)

                    history = conn.execute(f"""
                        SELECT result_pips, closed_at, timestamp
                        FROM {table_name}
                        WHERE symbol = ? AND {strategy_col} = ? AND gate_status = 'PASSED'
                        {run_id_clause}
                        ORDER BY timestamp DESC LIMIT 10
                    """, tuple(params)).fetchall()

                    if len(history) >= 5:
                        net_r = sum(float(row[0] or 0.0) for row in history)
                        if net_r <= -3.0:
                            last_closed_str = history[0][1] # Closed_at
                            time_ref = last_closed_str or history[0][2] # fallback to timestamp
                            if time_ref:
                                # Safe timezone stripping
                                last_dt = datetime.fromisoformat(time_ref.replace('Z', '+00:00'))
                                if last_dt.tzinfo is not None:
                                    last_dt = last_dt.replace(tzinfo=None)

                                current_sys_time = current_ts or datetime.utcnow()
                                if current_sys_time.tzinfo is not None:
                                    current_sys_time = current_sys_time.replace(tzinfo=None)

                                if (current_sys_time - last_dt).total_seconds() < 172800:
                                    return {"status": "BLOCKED", "reason": f"REGIME_BLEED_KILL_SWITCH ({net_r:.1f}R)"}
            except Exception as e:
                import traceback
                print("KILL SWITCH ERROR:")
                traceback.print_exc()

            return {"status": "PASSED", "reason": "VALIDATION_SUCCESS"}

        except Exception as e:
            return {"status": "BLOCKED", "reason": f"GATE_SYSTEM_ERROR: {str(e)}"}

    @staticmethod
    def validate_and_reserve(signal: Dict, db_signals: str, db_clients: str,
                             table_name: str = 'signals', current_ts: Optional[datetime] = None) -> Dict[str, str]:
        """
        Atomically validates and reserves symbol inventory before execution.
        This closes the check-then-insert race when multiple workers see the same burst.
        """
        gate = ExecutionGate.validate(signal, db_signals, db_clients, table_name, current_ts)
        if gate.get("status") != "PASSED":
            return gate

        symbol = signal.get("symbol")
        direction = signal.get("direction", "")
        signal_uid = signal.get("signal_uid") or ExecutionGate._signal_uid(signal)
        now = (current_ts or datetime.utcnow()).isoformat()

        try:
            with connect_sqlite(db_signals) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS trade_reservations (
                        symbol TEXT PRIMARY KEY,
                        direction TEXT,
                        signal_uid TEXT,
                        status TEXT DEFAULT 'ACTIVE',
                        created_at TEXT,
                        updated_at TEXT
                    )
                """)
                conn.execute("BEGIN IMMEDIATE")
                active = conn.execute("""
                    SELECT signal_uid, direction
                    FROM trade_reservations
                    WHERE symbol = ? AND status = 'ACTIVE'
                """, (symbol,)).fetchone()
                if active and active[0] != signal_uid:
                    conn.rollback()
                    return {
                        "status": "BLOCKED",
                        "reason": f"ACTIVE_RESERVATION_IN_{symbol}"
                    }
                conn.execute("""
                    INSERT INTO trade_reservations (symbol, direction, signal_uid, status, created_at, updated_at)
                    VALUES (?, ?, ?, 'ACTIVE', ?, ?)
                    ON CONFLICT(symbol) DO UPDATE SET
                        direction = excluded.direction,
                        signal_uid = excluded.signal_uid,
                        status = 'ACTIVE',
                        updated_at = excluded.updated_at
                """, (symbol, direction, signal_uid, now, now))
                conn.commit()
                signal["signal_uid"] = signal_uid
                return gate
        except Exception as e:
            return {"status": "BLOCKED", "reason": f"RESERVATION_ERROR: {str(e)}"}

    @staticmethod
    def release_reservation(symbol: str, db_signals: str, signal_uid: Optional[str] = None, status: str = "RELEASED") -> None:
        if not symbol:
            return
        try:
            with sqlite3.connect(db_signals, timeout=30) as conn:
                conn.execute("PRAGMA busy_timeout=30000")
                if signal_uid:
                    conn.execute("""
                        UPDATE trade_reservations
                        SET status = ?, updated_at = ?
                        WHERE symbol = ? AND signal_uid = ?
                    """, (status, datetime.utcnow().isoformat(), symbol, signal_uid))
                else:
                    conn.execute("""
                        UPDATE trade_reservations
                        SET status = ?, updated_at = ?
                        WHERE symbol = ?
                    """, (status, datetime.utcnow().isoformat(), symbol))
                conn.commit()
        except Exception:
            pass

    @staticmethod
    def _has_open_position(symbol: str, db_path: str, table_name: str, current_ts: Optional[datetime] = None, run_id: Optional[int] = None) -> bool:
        """Queries the signal database for active trades on the given symbol."""
        try:
            with connect_sqlite(db_path) as conn:
                run_id_clause = " AND run_id = ? " if run_id is not None else ""
                
                if current_ts is not None:
                    current_iso = current_ts.isoformat()
                    try:
                        sql = f"""
                            SELECT COUNT(*) FROM {table_name}
                            WHERE symbol = ?
                            AND COALESCE(gate_status, 'PASSED') != 'BLOCKED'
                            AND timestamp <= ?
                            AND (
                                closed_at IS NULL
                                OR closed_at = ''
                                OR closed_at > ?
                            )
                            {run_id_clause}
                        """
                        params = [symbol, current_iso, current_iso]
                        if run_id is not None:
                            params.append(run_id)
                            
                        res = conn.execute(sql, tuple(params)).fetchone()
                        if res and res[0] > 0:
                            return True
                    except sqlite3.OperationalError:
                        pass

                sql = f"""
                    SELECT COUNT(*) FROM {table_name}
                    WHERE symbol = ?
                    AND (
                        COALESCE(result, 'OPEN') = 'OPEN'
                        OR COALESCE(status, 'OPEN') IN (
                            'OPEN', 'PENDING_EXECUTION', 'PAPER_EXECUTED',
                            'LIVE_EXECUTED', 'EXECUTED', 'PARTIAL'
                        )
                    )
                    AND COALESCE(gate_status, 'PASSED') != 'BLOCKED'
                    {run_id_clause}
                """
                params = [symbol]
                if run_id is not None:
                    params.append(run_id)
                    
                res = conn.execute(sql, tuple(params)).fetchone()
                if res and res[0] > 0:
                    return True
                try:
                    reservation = conn.execute("""
                        SELECT 1 FROM trade_reservations
                        WHERE symbol = ? AND status = 'ACTIVE'
                        LIMIT 1
                    """, (symbol,)).fetchone()
                    return reservation is not None
                except sqlite3.OperationalError:
                    return False
        except Exception:
            return False

    @staticmethod
    def _get_thresholds(db_path: str) -> Dict[str, float]:
        """Loads operational thresholds from the client configuration database."""
        thresholds = {}
        try:
            with connect_sqlite(db_path) as conn:
                conn.row_factory = sqlite3.Row
                try:
                    rows = conn.execute("SELECT event_type, multiplier FROM weight_overrides WHERE COALESCE(is_active, 1) = 1").fetchall()
                    for row in rows:
                        thresholds[row['event_type']] = float(row['multiplier'])
                except sqlite3.OperationalError:
                    pass
                rows = conn.execute("SELECT key, value FROM system_config").fetchall()
                for row in rows:
                    key = str(row["key"]).upper()
                    if key in ("MIN_EXECUTION_QUALITY", "MIN_QUALITY_SCORE"):
                        thresholds["MIN_EXECUTION_QUALITY"] = float(row["value"])
                    elif key == "MAX_DAILY_LOSS_PCT":
                        thresholds["MAX_DAILY_LOSS_PCT"] = float(row["value"])
        except Exception:
            pass
        return thresholds

    @staticmethod
    def _daily_loss_breached(db_path: str, max_loss_pct: float, current_ts: Optional[datetime]) -> bool:
        try:
            today = (current_ts or datetime.utcnow()).date().isoformat()
            with connect_sqlite(db_path) as conn:
                acct = conn.execute("SELECT balance, equity FROM paper_account WHERE id = 1").fetchone()
                if acct and acct[0]:
                    drawdown_pct = max(0.0, (float(acct[0]) - float(acct[1])) / float(acct[0]) * 100)
                    if drawdown_pct >= max_loss_pct:
                        return True
                row = conn.execute("""
                    SELECT COALESCE(SUM(result_pips), 0)
                    FROM signals
                    WHERE closed_at LIKE ? AND result_pips < 0
                """, (f"{today}%",)).fetchone()
                return bool(row and abs(float(row[0] or 0)) >= max_loss_pct)
        except Exception:
            return False

    @staticmethod
    def _signal_uid(signal: Dict) -> str:
        import hashlib
        key = "|".join([
            str(signal.get("symbol", "")),
            str(signal.get("direction", "")),
            str(signal.get("timeframe", "")),
            str(signal.get("entry_price", "")),
            str(signal.get("sl", "")),
            str(signal.get("tp1", "")),
        ])
        return hashlib.sha256(key.encode()).hexdigest()[:24]
