"""
database/trade_repository.py
-----------------------------
Data access layer for trades and bot events.
All SQL lives here — no SQL in business logic.
"""

import sqlite3
from datetime import datetime
from typing import List, Optional

from models.trade import Trade
from database.database import Database
from utils.logger import get_logger

logger = get_logger(__name__)


class TradeRepository:
    """CRUD operations for trades and bot events."""

    def __init__(self, db: Database):
        self.db = db

    # ── Trades ────────────────────────────────────────────────────────────────

    def save_trade(self, trade: Trade) -> int:
        """Insert a new trade. Returns the new row ID."""
        conn = self.db.get_connection()
        cursor = conn.execute(
            """
            INSERT INTO trades (
                symbol, direction, strategy, status, lot_size,
                entry_price, exit_price, stop_loss, take_profit,
                trailing_stop, pnl, pnl_pips, entry_time, exit_time, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade.symbol,
                trade.direction,
                trade.strategy,
                trade.status,
                trade.lot_size,
                trade.entry_price,
                trade.exit_price,
                trade.stop_loss,
                trade.take_profit,
                trade.trailing_stop,
                trade.pnl,
                trade.pnl_pips,
                trade.entry_time.isoformat(),
                trade.exit_time.isoformat() if trade.exit_time else None,
                trade.notes,
            ),
        )
        conn.commit()
        trade.id = cursor.lastrowid
        logger.debug(f"Trade saved: {trade}")
        return trade.id

    def update_trade(self, trade: Trade) -> None:
        """Update an existing trade (e.g., after close)."""
        conn = self.db.get_connection()
        conn.execute(
            """
            UPDATE trades SET
                status        = ?,
                exit_price    = ?,
                exit_time     = ?,
                trailing_stop = ?,
                pnl           = ?,
                pnl_pips      = ?,
                notes         = ?
            WHERE id = ?
            """,
            (
                trade.status,
                trade.exit_price,
                trade.exit_time.isoformat() if trade.exit_time else None,
                trade.trailing_stop,
                trade.pnl,
                trade.pnl_pips,
                trade.notes,
                trade.id,
            ),
        )
        conn.commit()
        logger.debug(f"Trade updated: {trade}")

    def get_open_trades(self) -> List[Trade]:
        """Return all trades with status=OPEN."""
        conn = self.db.get_connection()
        rows = conn.execute(
            "SELECT * FROM trades WHERE status = 'OPEN' ORDER BY entry_time DESC"
        ).fetchall()
        return [self._row_to_trade(r) for r in rows]

    def get_all_trades(self, limit: int = 200) -> List[Trade]:
        """Return recent trades ordered by entry time."""
        conn = self.db.get_connection()
        rows = conn.execute(
            "SELECT * FROM trades ORDER BY entry_time DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._row_to_trade(r) for r in rows]

    def get_trades_by_symbol(self, symbol: str, limit: int = 100) -> List[Trade]:
        conn = self.db.get_connection()
        rows = conn.execute(
            "SELECT * FROM trades WHERE symbol = ? ORDER BY entry_time DESC LIMIT ?",
            (symbol, limit),
        ).fetchall()
        return [self._row_to_trade(r) for r in rows]

    def get_daily_pnl(self, date_str: str) -> float:
        """Sum of PnL for all closed trades on a given date (YYYY-MM-DD)."""
        conn = self.db.get_connection()
        row = conn.execute(
            """
            SELECT COALESCE(SUM(pnl), 0) as total
            FROM trades
            WHERE status = 'CLOSED'
              AND date(entry_time) = ?
            """,
            (date_str,),
        ).fetchone()
        return float(row["total"])

    # ── Bot Events ────────────────────────────────────────────────────────────

    def log_event(
        self,
        level: str,
        category: str,
        message: str,
        symbol: Optional[str] = None,
    ) -> None:
        """Persist a bot event to the database."""
        conn = self.db.get_connection()
        conn.execute(
            """
            INSERT INTO bot_events (timestamp, level, category, symbol, message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (datetime.utcnow().isoformat(), level, category, symbol, message),
        )
        conn.commit()

    def get_recent_events(self, limit: int = 100) -> List[dict]:
        """Return recent bot events as list of dicts."""
        conn = self.db.get_connection()
        rows = conn.execute(
            "SELECT * FROM bot_events ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _row_to_trade(row: sqlite3.Row) -> Trade:
        """Convert a DB row to a Trade model."""
        return Trade(
            id=row["id"],
            symbol=row["symbol"],
            direction=row["direction"],
            strategy=row["strategy"],
            status=row["status"],
            lot_size=row["lot_size"],
            entry_price=row["entry_price"],
            exit_price=row["exit_price"],
            stop_loss=row["stop_loss"],
            take_profit=row["take_profit"],
            trailing_stop=row["trailing_stop"],
            pnl=row["pnl"] or 0.0,
            pnl_pips=row["pnl_pips"] or 0.0,
            entry_time=datetime.fromisoformat(row["entry_time"]),
            exit_time=(
                datetime.fromisoformat(row["exit_time"]) if row["exit_time"] else None
            ),
            notes=row["notes"] or "",
        )
