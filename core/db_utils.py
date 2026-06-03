import json
import sqlite3
from datetime import datetime
from typing import Any, Optional


def connect_sqlite(db_path: str) -> sqlite3.Connection:
    """Open SQLite with the same concurrency settings everywhere."""
    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.row_factory = sqlite3.Row
    return conn


def ensure_base_tables(conn: sqlite3.Connection) -> None:
    """Initialize core institutional tables."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            actor TEXT NOT NULL,
            target TEXT,
            before_value TEXT,
            after_value TEXT,
            metadata TEXT DEFAULT '{}',
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            requested_lots REAL NOT NULL,
            requested_price REAL,
            sl REAL,
            tp REAL,
            client_order_id TEXT,
            status TEXT NOT NULL,
            raw_request TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            filled_lots REAL NOT NULL,
            filled_price REAL NOT NULL,
            commission REAL DEFAULT 0,
            swap REAL DEFAULT 0,
            broker_time TEXT,
            raw_response TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(order_id) REFERENCES orders(order_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reconciliation_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            status TEXT NOT NULL,
            deals_count INTEGER DEFAULT 0,
            positions_count INTEGER DEFAULT 0,
            error TEXT,
            started_at TEXT NOT NULL,
            completed_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS broker_reconciliation_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            broker_order_id TEXT,
            broker_position_id TEXT,
            symbol TEXT,
            event_type TEXT NOT NULL,
            payload_json TEXT DEFAULT '{}',
            created_at TEXT NOT NULL
        )
    """)


def write_audit_event(
    conn: sqlite3.Connection,
    event_type: str,
    actor: str,
    target: Optional[str] = None,
    before_value: Any = None,
    after_value: Any = None,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    ensure_base_tables(conn)
    conn.execute(
        """
        INSERT INTO audit_events (
            event_type, actor, target, before_value, after_value, metadata, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_type,
            actor,
            target,
            None if before_value is None else str(before_value),
            None if after_value is None else str(after_value),
            json.dumps(metadata or {}, default=str),
            datetime.utcnow().isoformat(),
        ),
    )
