"""
market_data/candle_builder.py
------------------------------
Builds and manages the candle DataFrame used by strategies.

Responsibilities:
- Maintain a rolling window of candles (e.g., last 200)
- Detect when a new candle has closed
- Convert raw broker data to a clean pandas DataFrame
- Add new ticks/candles to the buffer

This is the bridge between raw market data and the strategy engine.
"""

from datetime import datetime, timezone
from typing import Optional
import pandas as pd

from models.candle import Candle
from utils.helpers import timeframe_to_seconds
from utils.logger import get_logger

logger = get_logger(__name__)


class CandleBuilder:
    """
    Maintains a rolling DataFrame of OHLCV candles.

    The strategy always reads from this buffer.
    The bot engine calls update() after each broker poll.
    """

    def __init__(self, symbol: str, timeframe: str, max_candles: int = 300):
        self.symbol = symbol
        self.timeframe = timeframe
        self.max_candles = max_candles
        self.tf_seconds = timeframe_to_seconds(timeframe)

        self._df: Optional[pd.DataFrame] = None
        self._last_candle_time: Optional[datetime] = None

    # ── Data Loading ──────────────────────────────────────────────────────────

    def load_from_broker(self, df: pd.DataFrame) -> None:
        """
        Load initial candle history from broker.

        Args:
            df: DataFrame with columns open, high, low, close, volume
                and DatetimeIndex
        """
        if df.empty:
            logger.warning(f"Empty candle data received for {self.symbol}")
            return

        # Normalize column names to lowercase
        df.columns = [c.lower() for c in df.columns]

        # Ensure required columns exist
        required = {"open", "high", "low", "close", "volume"}
        missing = required - set(df.columns)
        if missing:
            logger.error(f"Missing columns in candle data: {missing}")
            return

        # Keep only the last max_candles rows
        self._df = df.tail(self.max_candles).copy()
        self._last_candle_time = self._df.index[-1]

        logger.info(
            f"CandleBuilder loaded: {self.symbol} {self.timeframe} "
            f"| {len(self._df)} candles | last={self._last_candle_time}"
        )

    def append_candle(self, candle: Candle) -> bool:
        """
        Add a new closed candle to the buffer.

        Returns True if this is a genuinely new candle (not a duplicate).
        """
        if self._df is None:
            logger.warning("CandleBuilder not initialized — call load_from_broker first")
            return False

        ts = pd.Timestamp(candle.timestamp, tz="UTC")

        # Avoid duplicates
        if ts in self._df.index:
            return False

        new_row = pd.DataFrame(
            [{
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
            }],
            index=pd.DatetimeIndex([ts], tz="UTC"),
        )

        self._df = pd.concat([self._df, new_row]).tail(self.max_candles)
        self._last_candle_time = ts

        logger.debug(f"New candle appended: {candle}")
        return True

    def update_last_candle(self, price: float) -> None:
        """
        Update the close price of the current (forming) candle.
        Used for real-time price display — does NOT trigger strategy.
        """
        if self._df is not None and not self._df.empty:
            self._df.iloc[-1, self._df.columns.get_loc("close")] = price

    # ── Candle Close Detection ────────────────────────────────────────────────

    def is_new_candle_closed(self, broker_df: pd.DataFrame) -> bool:
        """
        Check if broker has a new candle that we haven't processed yet.

        Args:
            broker_df: fresh DataFrame from broker.get_candles()

        Returns:
            True if there's a new closed candle to process
        """
        if broker_df.empty or self._df is None:
            return False

        latest_broker_time = broker_df.index[-1]
        return latest_broker_time != self._last_candle_time

    # ── Data Access ───────────────────────────────────────────────────────────

    @property
    def df(self) -> Optional[pd.DataFrame]:
        """Returns the current candle DataFrame."""
        return self._df

    @property
    def is_ready(self) -> bool:
        """True if we have enough data to run the strategy."""
        return self._df is not None and len(self._df) >= 60

    @property
    def last_close(self) -> Optional[float]:
        if self._df is not None and not self._df.empty:
            return float(self._df["close"].iloc[-1])
        return None

    def get_last_n_candles(self, n: int) -> Optional[pd.DataFrame]:
        if self._df is None:
            return None
        return self._df.tail(n)
