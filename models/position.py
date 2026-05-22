"""
models/position.py
------------------
Represents an active open position in memory.
Tracks real-time state: current price, trailing stop, unrealized PnL.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Position:
    """Live open position tracked in memory."""

    symbol: str
    direction: str          # "BUY" | "SELL"
    entry_price: float
    lot_size: float
    entry_time: datetime
    stop_loss: float
    strategy: str = "ema_trend"

    # Updated in real-time
    current_price: float = 0.0
    trailing_stop: Optional[float] = None
    trade_id: Optional[int] = None   # FK to Trade in DB

    @property
    def unrealized_pnl(self) -> float:
        if self.current_price == 0:
            return 0.0
        if self.direction == "BUY":
            return (self.current_price - self.entry_price) * self.lot_size
        else:
            return (self.entry_price - self.current_price) * self.lot_size

    @property
    def pnl_pips(self) -> float:
        if self.current_price == 0:
            return 0.0
        if self.direction == "BUY":
            return self.current_price - self.entry_price
        else:
            return self.entry_price - self.current_price

    def update_trailing_stop(self, new_stop: float) -> bool:
        """
        Update trailing stop only if it moves in the favorable direction.
        Returns True if stop was updated.
        """
        if self.trailing_stop is None:
            self.trailing_stop = new_stop
            return True

        if self.direction == "BUY" and new_stop > self.trailing_stop:
            self.trailing_stop = new_stop
            return True
        elif self.direction == "SELL" and new_stop < self.trailing_stop:
            self.trailing_stop = new_stop
            return True

        return False

    @property
    def effective_stop(self) -> float:
        """Returns trailing stop if set, otherwise initial stop loss."""
        return self.trailing_stop if self.trailing_stop is not None else self.stop_loss

    def is_stopped_out(self, price: float) -> bool:
        """Check if current price has hit the stop."""
        stop = self.effective_stop
        if self.direction == "BUY":
            return price <= stop
        else:
            return price >= stop

    def __repr__(self) -> str:
        return (
            f"Position({self.symbol} {self.direction} "
            f"@ {self.entry_price} | stop={self.effective_stop:.5f} "
            f"upnl={self.unrealized_pnl:.2f})"
        )
