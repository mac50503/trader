"""
strategies/base_strategy.py
----------------------------
Abstract base class for all trading strategies.

Every strategy must implement:
- generate_signal(): analyze candles and return a signal
- calculate_stop_loss(): compute initial stop loss
- update_trailing_stop(): update stop as trade progresses

Strategies are stateless — they receive data and return decisions.
State (open positions, balance) lives in the bot engine.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import pandas as pd

from models.position import Position


@dataclass
class Signal:
    """
    Trading signal returned by a strategy.

    action: "BUY" | "SELL" | "CLOSE" | "HOLD"
    stop_loss: suggested initial stop loss price
    reason: human-readable explanation (for logs)
    """
    action: str                      # BUY | SELL | CLOSE | HOLD
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    reason: str = ""
    confidence: float = 1.0          # 0.0 - 1.0, for future ML integration

    def is_entry(self) -> bool:
        return self.action in ("BUY", "SELL")

    def is_exit(self) -> bool:
        return self.action == "CLOSE"

    def is_hold(self) -> bool:
        return self.action == "HOLD"

    def __repr__(self) -> str:
        return f"Signal({self.action} | SL={self.stop_loss} | {self.reason})"


class BaseStrategy(ABC):
    """Abstract base for all strategies."""

    def __init__(self, params: dict):
        """
        Args:
            params: strategy parameters dict (from UI or config)
        """
        self.params = params
        self.name = self.__class__.__name__

    @abstractmethod
    def generate_signal(
        self,
        df: pd.DataFrame,
        current_position: Optional[Position] = None,
    ) -> Signal:
        """
        Analyze candle data and return a trading signal.

        Args:
            df: OHLCV DataFrame with indicator columns already computed
            current_position: open position if any, None otherwise

        Returns:
            Signal with action and stop loss
        """
        ...

    @abstractmethod
    def calculate_stop_loss(
        self,
        df: pd.DataFrame,
        direction: str,
    ) -> float:
        """
        Calculate initial stop loss for a new entry.

        Args:
            df: OHLCV DataFrame with indicators
            direction: "BUY" or "SELL"

        Returns:
            Stop loss price
        """
        ...

    @abstractmethod
    def update_trailing_stop(
        self,
        df: pd.DataFrame,
        position: Position,
    ) -> Optional[float]:
        """
        Calculate updated trailing stop for an open position.

        Args:
            df: latest OHLCV DataFrame with indicators
            position: current open position

        Returns:
            New stop loss price, or None if no update needed
        """
        ...

    def __repr__(self) -> str:
        return f"{self.name}(params={self.params})"
