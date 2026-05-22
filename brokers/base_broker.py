"""
brokers/base_broker.py
-----------------------
Abstract base class for all broker integrations.
Every broker (paper, Alpaca, OANDA, etc.) must implement this interface.

This is the "contract" — strategies and the bot engine only talk to this
interface, never to a specific broker implementation directly.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime

import pandas as pd

from models.trade import Trade
from models.position import Position


class BaseBroker(ABC):
    """
    Abstract broker interface.
    Implement this to add support for any broker.
    """

    def __init__(self, api_key: str = "", secret_key: str = "", base_url: str = "", mode: str = "demo"):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = base_url
        self.mode = mode  # "demo" | "live"
        self._connected = False

    # ── Connection ────────────────────────────────────────────────────────────

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to broker. Returns True on success."""
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection cleanly."""
        ...

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ── Account ───────────────────────────────────────────────────────────────

    @abstractmethod
    def get_account_balance(self) -> float:
        """Return current account balance."""
        ...

    @abstractmethod
    def get_account_equity(self) -> float:
        """Return current equity (balance + unrealized PnL)."""
        ...

    # ── Market Data ───────────────────────────────────────────────────────────

    @abstractmethod
    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        count: int = 200,
    ) -> pd.DataFrame:
        """
        Fetch historical candles.

        Returns DataFrame with columns: open, high, low, close, volume
        Index: DatetimeIndex (UTC)
        """
        ...

    @abstractmethod
    def get_current_price(self, symbol: str) -> float:
        """Return latest bid/ask midpoint for symbol."""
        ...

    # ── Order Execution ───────────────────────────────────────────────────────

    @abstractmethod
    def place_market_order(
        self,
        symbol: str,
        direction: str,
        lot_size: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        comment: str = "",
    ) -> Optional[Trade]:
        """
        Place a market order.

        Args:
            symbol: trading symbol
            direction: "BUY" or "SELL"
            lot_size: position size
            stop_loss: stop loss price
            take_profit: take profit price
            comment: optional order comment

        Returns:
            Trade object if successful, None if failed
        """
        ...

    @abstractmethod
    def close_position(self, trade: Trade, price: Optional[float] = None) -> bool:
        """
        Close an open position at market price.

        Returns True if successful.
        """
        ...

    @abstractmethod
    def modify_stop_loss(self, trade: Trade, new_stop: float) -> bool:
        """
        Modify the stop loss of an open position.

        Returns True if successful.
        """
        ...

    # ── Positions ─────────────────────────────────────────────────────────────

    @abstractmethod
    def get_open_positions(self) -> List[Position]:
        """Return list of currently open positions."""
        ...

    # ── Utility ───────────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(mode={self.mode}, connected={self._connected})"
