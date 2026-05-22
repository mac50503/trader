"""
brokers/paper_broker.py
------------------------
Paper trading broker — simulates order execution without real money.

Maintains a persistent candle buffer that advances in real time.
Each call to get_candles() returns the same historical buffer plus
any new candles that have "closed" since the last call, based on
wall-clock time. This lets the CandleBuilder correctly detect
new candle closes without generating random timestamps on every call.
"""

import random
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict
import pandas as pd
import numpy as np

from brokers.base_broker import BaseBroker
from models.trade import Trade
from models.position import Position
from utils.logger import get_logger
from utils.helpers import utc_now, timeframe_to_seconds

logger = get_logger(__name__)


class PaperBroker(BaseBroker):
    """
    Simulated broker for paper trading.

    - Generates realistic synthetic OHLCV data
    - Candle buffer advances with real wall-clock time
    - Simulates order fills at current price
    - Tracks virtual balance and positions
    - No real API calls needed
    """

    BASE_PRICES = {
        "XAUUSD": 2350.0,
        "NAS100": 18500.0,
        "SPX500": 5200.0,
    }

    def __init__(self, initial_balance: float = 10_000.0, **kwargs):
        super().__init__(**kwargs)
        self.initial_balance = initial_balance
        self._balance = initial_balance
        self._positions: List[Position] = []
        self._trade_counter = 0

        # Persistent candle state per symbol+timeframe
        # key: (symbol, timeframe) → {"df": DataFrame, "last_close_time": datetime}
        self._candle_cache: Dict[tuple, dict] = {}
        self._price_cache: Dict[str, float] = {}

    # ── Connection ────────────────────────────────────────────────────────────

    def connect(self) -> bool:
        self._connected = True
        logger.info(f"PaperBroker connected | balance=${self._balance:,.2f}")
        return True

    def disconnect(self) -> None:
        self._connected = False
        logger.info("PaperBroker disconnected.")

    # ── Account ───────────────────────────────────────────────────────────────

    def get_account_balance(self) -> float:
        return self._balance

    def get_account_equity(self) -> float:
        unrealized = sum(p.unrealized_pnl for p in self._positions)
        return self._balance + unrealized

    # ── Market Data ───────────────────────────────────────────────────────────

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        count: int = 200,
    ) -> pd.DataFrame:
        """
        Return a persistent candle DataFrame that grows over time.

        On first call: generates `count` historical candles ending now.
        On subsequent calls: appends any new candles that have closed
        since the last call, based on real wall-clock time.

        This means the CandleBuilder will correctly detect new candle
        closes — a new row only appears when a real candle period ends.
        """
        key = (symbol, timeframe)
        tf_seconds = timeframe_to_seconds(timeframe)
        now = datetime.now(timezone.utc)

        if key not in self._candle_cache:
            # First call — build full history
            df = self._generate_history(symbol, timeframe, count, now)
            self._candle_cache[key] = {
                "df": df,
                "last_close_time": df.index[-1],
                "last_close_price": float(df["close"].iloc[-1]),
            }
            self._price_cache[symbol] = float(df["close"].iloc[-1])
            logger.debug(f"PaperBroker: generated {len(df)} candles for {symbol} {timeframe}")
        else:
            cache = self._candle_cache[key]
            last_close = cache["last_close_time"]

            # How many new candles have closed since last call?
            elapsed = (now - last_close).total_seconds()
            new_candle_count = int(elapsed // tf_seconds)

            if new_candle_count > 0:
                last_price = cache["last_close_price"]
                new_rows = self._generate_new_candles(
                    symbol, timeframe, new_candle_count,
                    last_close, last_price, tf_seconds
                )
                cache["df"] = pd.concat([cache["df"], new_rows]).tail(count)
                cache["last_close_time"] = new_rows.index[-1]
                cache["last_close_price"] = float(new_rows["close"].iloc[-1])
                self._price_cache[symbol] = float(new_rows["close"].iloc[-1])
                logger.debug(
                    f"PaperBroker: +{new_candle_count} new candles for {symbol} {timeframe}"
                )

        return self._candle_cache[key]["df"].copy()

    def _generate_history(
        self,
        symbol: str,
        timeframe: str,
        count: int,
        end_time: datetime,
    ) -> pd.DataFrame:
        """Generate `count` historical candles ending at end_time."""
        tf_seconds = timeframe_to_seconds(timeframe)
        base_price = self.BASE_PRICES.get(symbol, 1000.0)
        volatility = base_price * 0.0015

        # Align end_time to candle boundary
        ts_epoch = int(end_time.timestamp())
        aligned_end = ts_epoch - (ts_epoch % tf_seconds)

        timestamps = [
            datetime.fromtimestamp(aligned_end - tf_seconds * (count - 1 - i), tz=timezone.utc)
            for i in range(count)
        ]

        np.random.seed()  # Use system time for true randomness
        rows = self._build_candle_rows(base_price, volatility, count)

        df = pd.DataFrame(rows, index=pd.DatetimeIndex(timestamps, tz="UTC"))
        return df

    def _generate_new_candles(
        self,
        symbol: str,
        timeframe: str,
        count: int,
        after_time: datetime,
        last_price: float,
        tf_seconds: int,
    ) -> pd.DataFrame:
        """Generate `count` new candles starting after after_time."""
        volatility = last_price * 0.0015

        timestamps = [
            after_time + timedelta(seconds=tf_seconds * (i + 1))
            for i in range(count)
        ]

        rows = self._build_candle_rows(last_price, volatility, count)
        return pd.DataFrame(rows, index=pd.DatetimeIndex(timestamps, tz="UTC"))

    def _build_candle_rows(
        self, start_price: float, volatility: float, count: int
    ) -> list:
        """Build OHLCV rows using a random walk from start_price."""
        closes = [start_price]
        for _ in range(count):
            delta = np.random.normal(0, volatility * 1.5)
            min_move = volatility * 0.1
            if abs(delta) < min_move:
                delta = min_move * (1 if np.random.random() > 0.5 else -1)
            new_close = closes[-1] + delta
            new_close = max(new_close, start_price * 0.3)
            closes.append(new_close)

        # Skip the first element (start_price) and use the generated ones
        closes = closes[1:]

        rows = []
        prev_close = start_price
        for close in closes:
            open_ = prev_close * (1 + np.random.uniform(-0.001, 0.001))
            wick_up   = abs(np.random.normal(0, volatility * 0.8))
            wick_down = abs(np.random.normal(0, volatility * 0.8))
            high = max(open_, close) + wick_up
            low  = min(open_, close) - wick_down
            rows.append({
                "open":   round(open_, 5),
                "high":   round(high,  5),
                "low":    round(low,   5),
                "close":  round(close, 5),
                "volume": round(random.uniform(200, 1000), 2),
            })
            prev_close = close
        return rows

    def get_current_price(self, symbol: str) -> float:
        """Return last known price with a small random tick."""
        base = self._price_cache.get(symbol, self.BASE_PRICES.get(symbol, 1000.0))
        tick = base * random.uniform(-0.0003, 0.0003)
        price = round(base + tick, 5)
        self._price_cache[symbol] = price
        return price

    # ── Order Execution ───────────────────────────────────────────────────────

    def place_market_order(
        self,
        symbol: str,
        direction: str,
        lot_size: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        comment: str = "",
    ) -> Optional[Trade]:
        """Simulate a market order fill at current price."""
        fill_price = self.get_current_price(symbol)
        self._trade_counter += 1

        trade = Trade(
            id=self._trade_counter,
            symbol=symbol,
            direction=direction,
            entry_price=fill_price,
            lot_size=lot_size,
            entry_time=utc_now(),
            stop_loss=stop_loss,
            take_profit=take_profit,
            strategy="paper",
            status="OPEN",
            notes=comment,
        )

        position = Position(
            symbol=symbol,
            direction=direction,
            entry_price=fill_price,
            lot_size=lot_size,
            entry_time=utc_now(),
            stop_loss=stop_loss or 0.0,
            trade_id=trade.id,
        )
        self._positions.append(position)

        logger.info(
            f"[PAPER] Order filled: {direction} {lot_size} {symbol} @ {fill_price} "
            f"SL={stop_loss}"
        )
        return trade

    def close_position(self, trade: Trade, price: Optional[float] = None) -> bool:
        """Simulate closing a position."""
        exit_price = price or self.get_current_price(trade.symbol)
        trade.close(exit_price, utc_now())
        self._balance += trade.pnl
        self._positions = [p for p in self._positions if p.trade_id != trade.id]
        logger.info(
            f"[PAPER] Position closed: {trade.symbol} @ {exit_price} "
            f"PnL={trade.pnl:+.2f}"
        )
        return True

    def modify_stop_loss(self, trade: Trade, new_stop: float) -> bool:
        trade.trailing_stop = new_stop
        for pos in self._positions:
            if pos.trade_id == trade.id:
                pos.update_trailing_stop(new_stop)
                break
        logger.debug(f"[PAPER] Stop updated: {trade.symbol} new_stop={new_stop}")
        return True

    def get_open_positions(self) -> List[Position]:
        return list(self._positions)

