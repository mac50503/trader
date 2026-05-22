"""
models/trade.py
---------------
Represents a completed or open trade record.
This is what gets persisted to SQLite.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Trade:
    """A single trade record (entry + optional exit)."""

    symbol: str
    direction: str                    # "BUY" | "SELL"
    entry_price: float
    lot_size: float
    entry_time: datetime

    # Filled on close
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    trailing_stop: Optional[float] = None

    # Metadata
    strategy: str = "ema_trend"
    status: str = "OPEN"              # "OPEN" | "CLOSED" | "CANCELLED"
    pnl: float = 0.0
    pnl_pips: float = 0.0
    notes: str = ""

    # DB primary key (None until saved)
    id: Optional[int] = None

    def close(self, exit_price: float, exit_time: datetime) -> None:
        """Mark trade as closed and calculate PnL."""
        self.exit_price = exit_price
        self.exit_time = exit_time
        self.status = "CLOSED"

        if self.direction == "BUY":
            self.pnl_pips = exit_price - self.entry_price
        else:
            self.pnl_pips = self.entry_price - exit_price

        # Simplified PnL in account currency (lot_size * pips)
        self.pnl = self.pnl_pips * self.lot_size

    @property
    def is_open(self) -> bool:
        return self.status == "OPEN"

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.exit_time and self.entry_time:
            return (self.exit_time - self.entry_time).total_seconds()
        return None

    def __repr__(self) -> str:
        return (
            f"Trade(#{self.id} {self.symbol} {self.direction} "
            f"@ {self.entry_price} | status={self.status} pnl={self.pnl:.2f})"
        )
