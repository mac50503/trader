"""
strategies/change_of_direction_strategy.py
-------------------------------------------
Change of Direction (COD) Strategy — reversal-based entry with fixed SL/TP.

Philosophy:
    Identify reversals by detecting consecutive candles of one color,
    followed by a reversal candle that breaks the previous direction.
    Enter when the reversal is confirmed by price action.

Entry Logic (SELL):
    1. Find 2+ consecutive RED candles (close < open)
    2. Next candle is GREEN (close > open) AND close_green > open_first_red
    3. Mark open_green as Point of Change Direction (PCD)
    4. Wait for price to break below PCD (low crosses PCD)
    5. Store new lowest point as New PCD
    6. When close <= New PCD → SELL entry
    7. Stop Loss: entry + 15 pips
    8. Take Profit: entry - 45 pips

Entry Logic (BUY):
    Mirror logic for uptrend reversals

Exit Logic:
    - Stop Loss hit: close above SL (for SELL) or below SL (for BUY)
    - Take Profit hit: close below TP (for SELL) or above TP (for BUY)
"""

from typing import Optional
import pandas as pd

from strategies.base_strategy import BaseStrategy, Signal
from models.position import Position
from utils.logger import get_logger
import config

logger = get_logger(__name__)


class ChangeOfDirectionStrategy(BaseStrategy):
    """
    Change of Direction (COD) Strategy.

    Parameters:
        pip_value (float): Value of 1 pip in price units (e.g., 0.01 for XAUUSD)
        stop_loss_pips (int): Stop loss distance in pips (default 15)
        take_profit_pips (int): Take profit distance in pips (default 45)
        min_red_candles (int): Minimum consecutive red candles (default 2)
        min_green_candles (int): Minimum consecutive green candles (default 2)
        allow_short (bool): Enable SELL signals (default True)
        allow_long (bool): Enable BUY signals (default True)
    """

    def __init__(self, params: Optional[dict] = None):
        defaults = {
            "pip_value":           0.01,      # For XAUUSD
            "stop_loss_pips":      15,
            "take_profit_pips":    45,
            "min_red_candles":     2,
            "min_green_candles":   2,
            "allow_short":         True,
            "allow_long":          True,
        }
        if params:
            defaults.update(params)
        super().__init__(defaults)

        # State tracking for COD detection
        self._pcd = None                    # Point of Change Direction
        self._new_pcd = None                # New PCD after breakout
        self._breakout_confirmed = False    # Has price broken the PCD?
        self._last_direction = None         # "UP" or "DOWN"

    # ── Main Signal ───────────────────────────────────────────────────────────

    def generate_signal(
        self,
        df: pd.DataFrame,
        current_position: Optional[Position] = None,
    ) -> Signal:
        """
        Evaluate the last closed candle and return a trading signal.
        """
        min_rows = 10  # Need at least 10 candles to detect pattern
        if len(df) < min_rows:
            return Signal("HOLD", reason=f"Not enough data ({len(df)}/{min_rows} rows)")

        last = df.iloc[-1]

        # ── If we have an open position: check exit first ─────────────────────
        if current_position:
            return self._check_exit(last, current_position)

        # ── Detect Change of Direction Pattern ─────────────────────────────────

        # Check for SELL setup (downtrend reversal)
        if self.params["allow_short"]:
            sell_signal = self._detect_sell_setup(df)
            if sell_signal:
                return sell_signal

        # Check for BUY setup (uptrend reversal)
        if self.params["allow_long"]:
            buy_signal = self._detect_buy_setup(df)
            if buy_signal:
                return buy_signal

        return Signal("HOLD", reason="No COD pattern detected")

    # ── SELL Detection ────────────────────────────────────────────────────────

    def _detect_sell_setup(self, df: pd.DataFrame) -> Optional[Signal]:
        """
        Detect SELL setup:
        1. 2+ red candles
        2. Green candle with close > open_first_red
        3. Price breaks below PCD
        4. Close <= New PCD → SELL
        """
        last = df.iloc[-1]
        current_candle_close = last["close"]
        current_candle_open = last["open"]
        current_candle_low = last["low"]

        # ════════════════════════════════════════════════════════════════
        # PATTERN RECOGNITION
        # ════════════════════════════════════════════════════════════════
        
        # Step 1: Find 2+ consecutive RED candles (close < open)
        consecutive_red_candles = 0
        for i in range(len(df) - 1, -1, -1):
            if df.iloc[i]["close"] < df.iloc[i]["open"]:
                consecutive_red_candles += 1
            else:
                break

        if consecutive_red_candles < self.params["min_red_candles"]:
            return None  # Not enough red candles

        # Get the first red candle in the sequence
        first_red_candle_index = len(df) - consecutive_red_candles - 1
        if first_red_candle_index < 0:
            return None

        first_red = df.iloc[first_red_candle_index]
        first_red_candle_open = first_red["open"]

        # Step 2: Next candle should be GREEN (close > open)
        if current_candle_close <= current_candle_open:  # Not green
            return None

        # Step 3: Condition - close_green > open_first_red
        if current_candle_close <= first_red_candle_open:  # Not higher than first red open
            return None

        # Step 4: Mark open_green as Point of Change Direction (PCD)
        point_of_change_direction = current_candle_open

        logger.debug(
            f"[{df.index[-1]}] COD SELL Pattern Recognition: Found reversal pattern. "
            f"Red candles={consecutive_red_candles}, PCD={point_of_change_direction:.5f}, "
            f"close={current_candle_close:.5f}, open_first_red={first_red_candle_open:.5f}"
        )

        # ════════════════════════════════════════════════════════════════
        # BREAKOUT CONFIRMATION
        # ════════════════════════════════════════════════════════════════
        
        # Step 1: Wait for price to break below PCD (low crosses PCD)
        if current_candle_low >= point_of_change_direction:
            # Price hasn't broken PCD yet
            return Signal(
                "HOLD",
                reason=f"COD SELL Breakout Confirmation: Waiting for breakout below PCD={point_of_change_direction:.5f}, low={current_candle_low:.5f}"
            )

        # Step 2: Store the new lowest point as New PCD
        new_point_of_change_direction = current_candle_low

        # ════════════════════════════════════════════════════════════════
        # ENTRY CONFIRMATION
        # ════════════════════════════════════════════════════════════════
        
        # Step 1: When close <= New PCD → SELL Entry
        if current_candle_close > new_point_of_change_direction:
            return Signal(
                "HOLD",
                reason=f"COD SELL Entry Confirmation: Breakout confirmed but waiting for close <= New PCD. "
                       f"New PCD={new_point_of_change_direction:.5f}, close={current_candle_close:.5f}"
            )

        # ✅ SELL Entry Confirmed - All conditions met!
        pip_value = self.params["pip_value"]
        
        # Step 2: Stop Loss = entry_price + 15 pips
        stop_loss_price = current_candle_close + (self.params["stop_loss_pips"] * pip_value)
        
        # Step 3: Take Profit = entry_price - 45 pips
        take_profit_price = current_candle_close - (self.params["take_profit_pips"] * pip_value)

        return Signal(
            action="SELL",
            stop_loss=stop_loss_price,
            take_profit=take_profit_price,
            reason=(
                f"COD SELL Entry Confirmed: Reversal confirmed. "
                f"close={current_candle_close:.5f}, New PCD={new_point_of_change_direction:.5f}, "
                f"SL={stop_loss_price:.5f}, TP={take_profit_price:.5f}"
            ),
        )

    # ── BUY Detection ─────────────────────────────────────────────────────────

    def _detect_buy_setup(self, df: pd.DataFrame) -> Optional[Signal]:
        """
        Detect BUY setup (mirror of SELL):
        1. 2+ green candles
        2. Red candle with close < open_first_green
        3. Price breaks above PCD
        4. Close >= New PCD → BUY
        """
        last = df.iloc[-1]
        current_candle_close = last["close"]
        current_candle_open = last["open"]
        current_candle_high = last["high"]

        # ════════════════════════════════════════════════════════════════
        # PATTERN RECOGNITION
        # ════════════════════════════════════════════════════════════════
        
        # Step 1: Find 2+ consecutive GREEN candles (close > open)
        consecutive_green_candles = 0
        for i in range(len(df) - 1, -1, -1):
            if df.iloc[i]["close"] > df.iloc[i]["open"]:
                consecutive_green_candles += 1
            else:
                break

        if consecutive_green_candles < self.params["min_green_candles"]:
            return None  # Not enough green candles

        # Get the first green candle in the sequence
        first_green_candle_index = len(df) - consecutive_green_candles - 1
        if first_green_candle_index < 0:
            return None

        first_green = df.iloc[first_green_candle_index]
        first_green_candle_open = first_green["open"]

        # Step 2: Next candle should be RED (close < open)
        if current_candle_close >= current_candle_open:  # Not red
            return None

        # Step 3: Condition - close_red < open_first_green
        if current_candle_close >= first_green_candle_open:  # Not lower than first green open
            return None

        # Step 4: Mark open_red as Point of Change Direction (PCD)
        point_of_change_direction = current_candle_open

        logger.debug(
            f"[{df.index[-1]}] COD BUY Pattern Recognition: Found reversal pattern. "
            f"Green candles={consecutive_green_candles}, PCD={point_of_change_direction:.5f}, "
            f"close={current_candle_close:.5f}, open_first_green={first_green_candle_open:.5f}"
        )

        # ════════════════════════════════════════════════════════════════
        # BREAKOUT CONFIRMATION
        # ════════════════════════════════════════════════════════════════
        
        # Step 1: Wait for price to break above PCD (high crosses PCD)
        if current_candle_high <= point_of_change_direction:
            # Price hasn't broken PCD yet
            return Signal(
                "HOLD",
                reason=f"COD BUY Breakout Confirmation: Waiting for breakout above PCD={point_of_change_direction:.5f}, high={current_candle_high:.5f}"
            )

        # Step 2: Store the new highest point as New PCD
        new_point_of_change_direction = current_candle_high

        # ════════════════════════════════════════════════════════════════
        # ENTRY CONFIRMATION
        # ════════════════════════════════════════════════════════════════
        
        # Step 1: When close >= New PCD → BUY Entry
        if current_candle_close < new_point_of_change_direction:
            return Signal(
                "HOLD",
                reason=f"COD BUY Entry Confirmation: Breakout confirmed but waiting for close >= New PCD. "
                       f"New PCD={new_point_of_change_direction:.5f}, close={current_candle_close:.5f}"
            )

        # ✅ BUY Entry Confirmed - All conditions met!
        pip_value = self.params["pip_value"]
        
        # Step 2: Stop Loss = entry_price - 15 pips
        stop_loss_price = current_candle_close - (self.params["stop_loss_pips"] * pip_value)
        
        # Step 3: Take Profit = entry_price + 45 pips
        take_profit_price = current_candle_close + (self.params["take_profit_pips"] * pip_value)

        return Signal(
            action="BUY",
            stop_loss=stop_loss_price,
            take_profit=take_profit_price,
            reason=(
                f"COD BUY Entry Confirmed: Reversal confirmed. "
                f"close={current_candle_close:.5f}, New PCD={new_point_of_change_direction:.5f}, "
                f"SL={stop_loss_price:.5f}, TP={take_profit_price:.5f}"
            ),
        )

    # ── Exit Check ────────────────────────────────────────────────────────────

    def _check_exit(self, last: pd.Series, position: Position) -> Signal:
        """
        Exit when SL or TP is hit.
        """
        current_candle_close = last["close"]

        if position.direction == "SELL":
            # Check SL (above entry)
            if current_candle_close >= position.stop_loss:
                return Signal(
                    action="CLOSE",
                    reason=(
                        f"COD SELL exit: Stop Loss hit. "
                        f"close={current_candle_close:.5f} >= SL={position.stop_loss:.5f}"
                    ),
                )
            # Check TP (below entry)
            if current_candle_close <= position.take_profit:
                return Signal(
                    action="CLOSE",
                    reason=(
                        f"COD SELL exit: Take Profit hit. "
                        f"close={current_candle_close:.5f} <= TP={position.take_profit:.5f}"
                    ),
                )

        elif position.direction == "BUY":
            # Check SL (below entry)
            if current_candle_close <= position.stop_loss:
                return Signal(
                    action="CLOSE",
                    reason=(
                        f"COD BUY exit: Stop Loss hit. "
                        f"close={current_candle_close:.5f} <= SL={position.stop_loss:.5f}"
                    ),
                )
            # Check TP (above entry)
            if current_candle_close >= position.take_profit:
                return Signal(
                    action="CLOSE",
                    reason=(
                        f"COD BUY exit: Take Profit hit. "
                        f"close={current_candle_close:.5f} >= TP={position.take_profit:.5f}"
                    ),
                )

        return Signal(
            "HOLD",
            reason=f"COD {position.direction}: Position intact. "
                   f"close={current_candle_close:.5f}, SL={position.stop_loss:.5f}, TP={position.take_profit:.5f}"
        )

    def calculate_stop_loss(self, df: pd.DataFrame, direction: str) -> float:
        """
        Initial stop loss is set by the strategy logic.
        This method is not used for COD strategy.
        """
        return 0.0

    def update_trailing_stop(
        self,
        df: pd.DataFrame,
        position: Position,
    ) -> Optional[float]:
        """
        COD strategy uses fixed SL/TP, no trailing stop.
        """
        return None
