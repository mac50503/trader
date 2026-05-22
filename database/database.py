"""
database/database.py
--------------------
SQLite connection manager and schema initializer.
Uses the standard library sqlite3 — no ORM needed.

Usage:
    db = Database()
    db.initialize()
    conn = db.get_connection()
"""

import sqlite3
from pathlib import Path
from typing import Optional

import config
from utils.logger import get_logger

logger = get_logger(__name__)


class Database:
    """Manages SQLite connection and schema creation."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or config.DB_PATH
        self._connection: Optional[sqlite3.Connection] = None

    def get_connection(self) -> sqlite3.Connection:
        """Returns a thread-safe connection with row_factory set."""
        if self._connection is None:
            self._connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,   # UI + bot threads share the connection
            )
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA journal_mode=WAL")  # Better concurrency
            self._connection.execute("PRAGMA foreign_keys=ON")
        return self._connection

    def initialize(self) -> None:
        """Create all tables if they don't exist."""
        conn = self.get_connection()
        self._create_tables(conn)
        conn.commit()
        logger.info(f"Database initialized at: {self.db_path}")

    def _create_tables(self, conn: sqlite3.Connection) -> None:
        conn.executescript("""
            -- ── Trades ──────────────────────────────────────────────────────
            CREATE TABLE IF NOT EXISTS trades (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol          TEXT    NOT NULL,
                direction       TEXT    NOT NULL,   -- BUY | SELL
                strategy        TEXT    NOT NULL,
                status          TEXT    NOT NULL,   -- OPEN | CLOSED | CANCELLED
                lot_size        REAL    NOT NULL,
                entry_price     REAL    NOT NULL,
                exit_price      REAL,
                stop_loss       REAL,
                take_profit     REAL,
                trailing_stop   REAL,
                pnl             REAL    DEFAULT 0,
                pnl_pips        REAL    DEFAULT 0,
                entry_time      TEXT    NOT NULL,
                exit_time       TEXT,
                notes           TEXT    DEFAULT ''
            );

            -- ── Bot Events / Logs ────────────────────────────────────────────
            CREATE TABLE IF NOT EXISTS bot_events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT    NOT NULL,
                level       TEXT    NOT NULL,   -- INFO | WARNING | ERROR | TRADE
                category    TEXT    NOT NULL,   -- SIGNAL | TRADE | RISK | SYSTEM
                symbol      TEXT,
                message     TEXT    NOT NULL
            );

            -- ── Daily Stats ──────────────────────────────────────────────────
            CREATE TABLE IF NOT EXISTS daily_stats (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                date            TEXT    NOT NULL UNIQUE,
                starting_capital REAL   NOT NULL,
                ending_capital  REAL,
                total_trades    INTEGER DEFAULT 0,
                winning_trades  INTEGER DEFAULT 0,
                losing_trades   INTEGER DEFAULT 0,
                total_pnl       REAL    DEFAULT 0,
                max_drawdown    REAL    DEFAULT 0
            );
        """)

    def close(self) -> None:
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.info("Database connection closed.")
