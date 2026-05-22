"""
models/candle.py
----------------
Represents a single OHLCV candle.
Used throughout the system as the standard data unit.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Candle:
    """A single OHLCV price candle."""

    symbol: str
    timeframe: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    is_closed: bool = False   # True once the candle period has ended

    @property
    def body(self) -> float:
        """Absolute size of the candle body."""
        return abs(self.close - self.open)

    @property
    def range(self) -> float:
        """Full high-low range."""
        return self.high - self.low

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open

    def __repr__(self) -> str:
        direction = "▲" if self.is_bullish else "▼"
        return (
            f"Candle({self.symbol} {self.timeframe} "
            f"{self.timestamp:%Y-%m-%d %H:%M} "
            f"O={self.open} H={self.high} L={self.low} C={self.close} {direction})"
        )
