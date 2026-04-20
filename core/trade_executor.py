"""
MT5 Auto-Trade Executor — V1.0
Uses MetaAPI (metaapi.cloud) REST bridge — Linux compatible.

Setup:
  1. pip install metaapi-cloud-sdk
  2. Set in .env:
       METAAPI_TOKEN=your_token_here
       METAAPI_ACCOUNT_ID=your_account_id_here
       MT5_AUTO_TRADE=true
       MT5_PAPER_MODE=true   ← set to false only after paper testing

Paper Mode (default=true): logs trades to console/DB without placing real orders.
"""

import json
import sqlite3
from datetime import datetime
from typing import Optional, Dict, List

from config.config import (
    METAAPI_TOKEN, METAAPI_ACCOUNT_ID,
    MT5_AUTO_TRADE, MT5_PAPER_MODE, DB_SIGNALS
)

# Symbol mapping: yfinance → MT5 broker symbol
SYMBOL_MAP = {
    "EURUSD=X": "EURUSD",
    "GBPUSD=X": "GBPUSD",
    "NZDUSD=X": "NZDUSD",
    "USDJPY=X": "USDJPY",
    "AUDUSD=X": "AUDUSD",
    "GBPJPY=X": "GBPJPY",
    "GC=F":     "XAUUSD",
    "CL=F":     "USOIL",
    "BTC-USD":  "BTCUSD",
}


class TradeExecutor:
    """
    Executes trades on MT5 via MetaAPI REST bridge.
    Falls back to paper logging when MT5_PAPER_MODE=true or MetaAPI is not configured.
    """

    def __init__(self):
        self.paper_mode = MT5_PAPER_MODE
        self.auto_trade = MT5_AUTO_TRADE
        self._api = None
        self._account = None

    async def _connect(self):
        """Lazy-connect to MetaAPI. Only called when a trade is needed."""
        if self._api is not None:
            return True
        if not METAAPI_TOKEN or not METAAPI_ACCOUNT_ID:
            print("⚠️  TradeExecutor: METAAPI_TOKEN or METAAPI_ACCOUNT_ID not set. Running in PAPER mode.")
            self.paper_mode = True
            return False
        try:
            from metaapi_cloud_sdk import MetaApi
            self._api = MetaApi(METAAPI_TOKEN)
            self._account = await self._api.metatrader_account_api.get_account(METAAPI_ACCOUNT_ID)
            state = self._account.state
            if state not in ['DEPLOYING', 'DEPLOYED']:
                await self._account.deploy()
                await self._account.wait_connected()
            print(f"✅ TradeExecutor: Connected to MetaAPI account {METAAPI_ACCOUNT_ID}")
            return True
        except ImportError:
            print("⚠️  TradeExecutor: metaapi-cloud-sdk not installed. Run: pip install metaapi-cloud-sdk")
            self.paper_mode = True
            return False
        except Exception as e:
            print(f"❌ TradeExecutor: MetaAPI connection failed: {e}")
            self.paper_mode = True
            return False

    def _map_symbol(self, yf_symbol: str) -> str:
        return SYMBOL_MAP.get(yf_symbol, yf_symbol.replace("=X", "").replace("-", ""))

    def _log_paper_trade(self, action: str, signal_data: dict, result: dict):
        """Write paper trade to DB for tracking."""
        try:
            conn = sqlite3.connect(DB_SIGNALS)
            conn.execute("""
                UPDATE signals SET
                    status = ?,
                    score_details = json_patch(COALESCE(score_details,'{}'), ?)
                WHERE symbol = ? AND timestamp = ?
            """, (
                "PAPER_EXECUTED",
                json.dumps({"mt5_action": action, "paper_result": result}),
                signal_data.get("symbol"),
                signal_data.get("timestamp")
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"⚠️  Paper log failed: {e}")

    async def execute_trade(self, signal_data: dict) -> dict:
        """
        Place a market order based on a signal dict.
        Returns a result dict with order_id, fill_price, status.

        Paper mode: logs to console + DB but places no real order.
        """
        if not self.auto_trade:
            return {"status": "skipped", "reason": "MT5_AUTO_TRADE=false"}

        symbol    = signal_data.get("symbol", "")
        direction = signal_data.get("direction", "BUY").upper()
        lot_size  = signal_data.get("lot_size", 0.01)
        sl        = signal_data.get("sl")
        tp        = signal_data.get("tp1")  # Use TP1 as conservative target
        mt5_sym   = self._map_symbol(symbol)
        order_type = "ORDER_TYPE_BUY" if direction == "BUY" else "ORDER_TYPE_SELL"

        if self.paper_mode:
            result = {
                "status": "paper",
                "symbol": mt5_sym,
                "direction": direction,
                "lot_size": lot_size,
                "sl": sl,
                "tp": tp,
                "timestamp": datetime.utcnow().isoformat()
            }
            print(f"📝 [PAPER TRADE] {direction} {lot_size} {mt5_sym} | SL={sl} | TP={tp}")
            self._log_paper_trade("OPEN", signal_data, result)
            return result

        # Live execution
        connected = await self._connect()
        if not connected:
            return {"status": "error", "reason": "MetaAPI not connected"}

        try:
            connection = self._account.get_rpc_connection()
            await connection.connect()
            await connection.wait_synchronized()

            order_result = await connection.create_market_buy_order(
                mt5_sym, lot_size, sl, tp,
                {"comment": "CRT-AutoBot"}
            ) if direction == "BUY" else await connection.create_market_sell_order(
                mt5_sym, lot_size, sl, tp,
                {"comment": "CRT-AutoBot"}
            )

            result = {
                "status": "executed",
                "order_id": order_result.get("orderId"),
                "symbol": mt5_sym,
                "direction": direction,
                "lot_size": lot_size,
                "fill_price": order_result.get("openPrice"),
                "timestamp": datetime.utcnow().isoformat()
            }
            print(f"✅ [LIVE TRADE] {direction} {lot_size} {mt5_sym} → OrderID: {result['order_id']}")
            return result

        except Exception as e:
            print(f"❌ Trade execution failed for {mt5_sym}: {e}")
            return {"status": "error", "reason": str(e)}

    async def get_open_positions(self) -> List[Dict]:
        """Fetch all open positions from MT5 via MetaAPI."""
        if self.paper_mode or not METAAPI_TOKEN:
            # Return paper trades from DB
            try:
                conn = sqlite3.connect(DB_SIGNALS)
                conn.row_factory = sqlite3.Row
                rows = conn.execute("""
                    SELECT symbol, direction, entry_price, sl, tp1, trade_type, timestamp
                    FROM signals
                    WHERE status = 'PAPER_EXECUTED'
                    ORDER BY timestamp DESC LIMIT 20
                """).fetchall()
                conn.close()
                return [dict(r) for r in rows]
            except Exception:
                return []

        connected = await self._connect()
        if not connected:
            return []

        try:
            connection = self._account.get_rpc_connection()
            await connection.connect()
            await connection.wait_synchronized()
            positions = await connection.get_positions()
            return [
                {
                    "id": p.get("id"),
                    "symbol": p.get("symbol"),
                    "direction": "BUY" if p.get("type") == "POSITION_TYPE_BUY" else "SELL",
                    "lot_size": p.get("volume"),
                    "open_price": p.get("openPrice"),
                    "current_price": p.get("currentPrice"),
                    "profit": p.get("profit"),
                    "sl": p.get("stopLoss"),
                    "tp": p.get("takeProfit"),
                    "open_time": p.get("time")
                }
                for p in (positions or [])
            ]
        except Exception as e:
            print(f"❌ get_open_positions failed: {e}")
            return []

    async def close_trade(self, position_id: str) -> dict:
        """Close an open position by ID."""
        if self.paper_mode or not METAAPI_TOKEN:
            try:
                conn = sqlite3.connect(DB_SIGNALS)
                conn.execute("UPDATE signals SET status='PAPER_CLOSED' WHERE id=?", (position_id,))
                conn.commit()
                conn.close()
            except Exception:
                pass
            return {"status": "paper_closed", "position_id": position_id}

        connected = await self._connect()
        if not connected:
            return {"status": "error", "reason": "MetaAPI not connected"}

        try:
            connection = self._account.get_rpc_connection()
            await connection.connect()
            await connection.wait_synchronized()
            result = await connection.close_position(position_id, {"comment": "CRT-AutoBot close"})
            return {"status": "closed", "position_id": position_id, "result": result}
        except Exception as e:
            print(f"❌ close_trade failed: {e}")
            return {"status": "error", "reason": str(e)}


# Singleton instance
_executor = None

def get_executor() -> TradeExecutor:
    global _executor
    if _executor is None:
        _executor = TradeExecutor()
    return _executor
