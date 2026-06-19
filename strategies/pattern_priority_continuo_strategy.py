"""
strategies/pattern_priority_continuo_strategy.py
-------------------------------------------------
Pattern Priority Continuo Strategy — Continuous multi-pattern tracking.
Never resets patterns when one completes. Tracks patterns independently.

Philosophy:
    Track multiple patterns continuously. When one completes, only that pattern
    is removed. Other patterns continue tracking independently.
"""

from typing import Optional, List, Dict, Any
import pandas as pd

from strategies.change_of_direction_strategy import ChangeOfDirectionStrategy, Signal
from models.position import Position
from utils.logger import get_logger

logger = get_logger(__name__)


class PatternState:
    """Represents a single pattern being tracked (SELL or BUY)."""
    def __init__(self, direction: str, pattern_id: int):
        self.id = pattern_id
        self.direction = direction  # "SELL" or "BUY"
        self.phase = "IDLE"
        
        # SELL-specific state
        self.point_1 = None
        self.red_count = 0
        self.green1_count = 0
        self.pullback1_high = None
        self.green2_count = 0
        self.pullback2_high = None
        self.point_2 = None
        
        # BUY-specific state
        self.green_count = 0
        self.red1_count = 0
        self.pullback1_low = None
        self.red2_count = 0
        self.pullback2_low = None


class PatternPriorityContinuoStrategy(ChangeOfDirectionStrategy):
    """
    Pattern Priority Continuo Strategy — continuous multi-pattern tracking.
    Patterns continue independently, no global reset when one completes.
    """

    def __init__(self, params: Optional[dict] = None):
        super().__init__(params)
        # Lists to track multiple patterns simultaneously
        self._sell_patterns: List[PatternState] = []
        self._buy_patterns: List[PatternState] = []
        self._next_pattern_id = 1
        
        # Trading hours filter
        self._use_session_filter = params.get("use_session_filter", True) if params else True
        self._trading_hour_start = params.get("trading_hour_start", 9) if params else 9
        self._trading_hour_end = params.get("trading_hour_end", 4) if params else 4
        self._was_in_session = True  # Track session state changes

    # ── Override generate_signal to track multiple patterns ──────────────────

    def _is_within_trading_hours(self, candle: pd.Series) -> bool:
        """Check if current candle is within allowed trading hours."""
        if not self._use_session_filter:
            return True
        
        # Get hour from timestamp
        from datetime import datetime
        if isinstance(candle["timestamp"], str):
            dt = datetime.fromisoformat(candle["timestamp"])
        else:
            dt = candle["timestamp"]
        
        hour = dt.hour
        
        # Normal session (e.g., 9 to 18)
        if self._trading_hour_start < self._trading_hour_end:
            return self._trading_hour_start <= hour < self._trading_hour_end
        # Overnight session (e.g., 22 to 6)
        else:
            return hour >= self._trading_hour_start or hour < self._trading_hour_end

    # ── Override generate_signal to track multiple patterns ──────────────────

    def generate_signal(
        self,
        df: pd.DataFrame,
        current_position: Optional[Position] = None,
    ) -> Signal:
        """Evaluate all active patterns and return signal from first complete pattern."""
        if len(df) < 45:
            return Signal("HOLD", reason=f"Not enough data ({len(df)}/45 rows)")

        last = df.iloc[-1]

        if current_position:
            return self._check_exit(last, current_position)

        # Check trading hours and reset patterns when session ends
        is_in_session = self._is_within_trading_hours(last)
        
        # Detect session change from active to inactive
        if self._was_in_session and not is_in_session:
            logger.info("Trading session ended. Resetting all patterns.")
            self._reset_all_patterns()
        
        self._was_in_session = is_in_session
        
        # Only process patterns if within trading hours
        if not is_in_session:
            return Signal("HOLD", reason="Outside trading hours")

        # Always update all patterns, trend filter applied at entry time
        # Update all SELL patterns
        if self.params["allow_short"]:
            signal = self._update_all_sell_patterns(last, df)
            if signal:
                # First SELL pattern completed → reset everything
                self._reset_all_patterns()
                return signal

        # Update all BUY patterns
        if self.params["allow_long"]:
            signal = self._update_all_buy_patterns(last, df)
            if signal:
                # First BUY pattern completed → reset everything
                self._reset_all_patterns()
                return signal

        # Report status
        active_sell = len(self._sell_patterns)
        active_buy = len(self._buy_patterns)
        return Signal(
            "HOLD",
            reason=f"COD Multi-Pattern: {active_sell} SELL patterns, {active_buy} BUY patterns tracked",
        )

    # ── Multi-pattern tracking for SELL ──────────────────────────────────────

    def _update_all_sell_patterns(self, candle: pd.Series, df: pd.DataFrame) -> Optional[Signal]:
        """Update all SELL patterns and return signal if any completes."""
        o = candle["open"]
        c = candle["close"]
        h = candle["high"]
        l = candle["low"]
        is_red = c < o
        is_green = c > o

        # Start new pattern if we see red candle
        if is_red:
            new_pattern = PatternState("SELL", self._next_pattern_id)
            self._next_pattern_id += 1
            new_pattern.phase = "PHASE1_DROP"
            new_pattern.point_1 = l
            new_pattern.red_count = 1
            self._sell_patterns.append(new_pattern)
            logger.debug(f"Pattern #{new_pattern.id}: SELL PHASE1 started, point_1={l:.5f}")

        # Update all existing patterns
        completed_patterns = []
        for pattern in self._sell_patterns:
            signal = self._update_single_sell_pattern(pattern, candle)
            if signal:  # Pattern completed
                completed_patterns.append(pattern)
                logger.info(f"Pattern #{pattern.id}: SELL COMPLETED → taking this signal")
                return signal  # First completed wins

        # Remove invalid patterns
        self._sell_patterns = [p for p in self._sell_patterns if p.phase != "INVALID"]
        
        return None

    def _update_single_sell_pattern(self, pattern: PatternState, candle: pd.Series) -> Optional[Signal]:
        """Update a single SELL pattern state machine."""
        o = candle["open"]
        c = candle["close"]
        h = candle["high"]
        l = candle["low"]
        is_red = c < o
        is_green = c > o

        # PHASE1: accumulating consecutive reds
        if pattern.phase == "PHASE1_DROP":
            if is_red:
                pattern.red_count += 1
                pattern.point_1 = min(pattern.point_1, l)
            elif is_green and pattern.red_count >= self.params["min_red_candles"]:
                # Transition to PHASE2
                pattern.phase = "PHASE2_PULLBACK1"
                pattern.green1_count = 1
                pattern.pullback1_high = h
                logger.debug(f"Pattern #{pattern.id}: → PHASE2")
            else:
                # Not enough reds, invalidate
                pattern.phase = "INVALID"
            return None

        # PHASE2: first pullback (greens)
        if pattern.phase == "PHASE2_PULLBACK1":
            if is_green:
                if pattern.green1_count >= 1 and c < pattern.point_1:
                    pattern.phase = "INVALID"  # Green went below point_1
                    return None
                pattern.green1_count += 1
                pattern.pullback1_high = max(pattern.pullback1_high, h)
            elif is_red and pattern.green1_count >= self.params["min_green_candles"]:
                # Transition to PHASE3
                pattern.phase = "PHASE3_BREAK"
                logger.debug(f"Pattern #{pattern.id}: → PHASE3, waiting for break of {pattern.point_1:.5f}")
                # Check if this red already breaks
                if c < pattern.point_1:
                    pattern.phase = "PHASE4_PULLBACK2"
                    pattern.green2_count = 0
                    pattern.pullback2_high = h
                    pattern.point_2 = None
                    logger.debug(f"Pattern #{pattern.id}: → PHASE4 (immediate break)")
            elif is_red:
                pattern.phase = "INVALID"  # Not enough greens
            return None

        # PHASE3: waiting for break of point_1
        if pattern.phase == "PHASE3_BREAK":
            if pattern.pullback1_high and c > pattern.pullback1_high:
                pattern.phase = "INVALID"  # Reset condition
                return None
            if c < pattern.point_1:
                pattern.phase = "PHASE4_PULLBACK2"
                pattern.green2_count = 0
                pattern.pullback2_high = h
                pattern.point_2 = None
                logger.debug(f"Pattern #{pattern.id}: → PHASE4 (point_1 broken)")
            return None

        # PHASE4: second pullback (greens)
        if pattern.phase == "PHASE4_PULLBACK2":
            if pattern.pullback1_high and c > pattern.pullback1_high:
                pattern.phase = "INVALID"  # Reset condition
                return None
            if is_green:
                if pattern.green2_count >= 1 and c < pattern.point_1:
                    pattern.phase = "INVALID"
                    return None
                pattern.green2_count += 1
                pattern.pullback2_high = max(pattern.pullback2_high, h)
                if pattern.point_2 is None:
                    pattern.point_2 = l
                else:
                    pattern.point_2 = min(pattern.point_2, l)
            elif is_red and pattern.green2_count >= self.params["min_green_candles"]:
                # Transition to PHASE5
                pattern.phase = "PHASE5_ENTRY"
                logger.debug(f"Pattern #{pattern.id}: → PHASE5, waiting for entry at {pattern.point_2:.5f}")
                # Check if this red already breaks
                if pattern.point_2 and c <= pattern.point_2:
                    return self._generate_sell_entry(pattern, c)
            return None

        # PHASE5: waiting for entry
        if pattern.phase == "PHASE5_ENTRY":
            if pattern.pullback1_high and c > pattern.pullback1_high:
                pattern.phase = "INVALID"
                return None
            if pattern.point_2 and c <= pattern.point_2:
                return self._generate_sell_entry(pattern, c, df)
            return None

        return None

    def _generate_sell_entry(self, pattern: PatternState, entry_price: float, df: pd.DataFrame) -> Optional[Signal]:
        """Generate SELL entry signal from completed pattern."""
        # Check trend filter before opening position
        if not self._is_trend_sell_allowed(df):
            pattern.phase = "INVALID"
            logger.info(
                f"Pattern #{pattern.id}: SELL BLOCKED by trend filter - invalidating pattern"
            )
            return None
        
        stop_loss = pattern.pullback2_high
        risk = stop_loss - entry_price
        take_profit = entry_price - (risk * 2.0)

        logger.info(
            f"Pattern #{pattern.id}: SELL ENTRY at {entry_price:.5f} | "
            f"SL={stop_loss:.5f} TP={take_profit:.5f} risk={risk:.5f}"
        )

        # Save snapshot for visualizer
        self.last_pattern_snapshot = {
            "direction": "SELL",
            "point_1": pattern.point_1,
            "pullback1_high": pattern.pullback1_high,
            "point_2": pattern.point_2,
            "pullback2_high": stop_loss,
            "entry": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "risk": risk,
        }
        self._save_snapshot()

        return Signal(
            action="SELL",
            stop_loss=round(stop_loss, 5),
            take_profit=round(take_profit, 5),
            reason=f"Pattern #{pattern.id} SELL: entry={entry_price:.5f} SL={stop_loss:.5f} TP={take_profit:.5f}",
        )

    # ── Multi-pattern tracking for BUY ───────────────────────────────────────

    def _update_all_buy_patterns(self, candle: pd.Series, df: pd.DataFrame) -> Optional[Signal]:
        """Update all BUY patterns and return signal if any completes."""
        o = candle["open"]
        c = candle["close"]
        h = candle["high"]
        l = candle["low"]
        is_green = c > o

        # Start new pattern if we see green candle
        if is_green:
            new_pattern = PatternState("BUY", self._next_pattern_id)
            self._next_pattern_id += 1
            new_pattern.phase = "PHASE1_DROP"
            new_pattern.point_1 = h
            new_pattern.green_count = 1
            self._buy_patterns.append(new_pattern)
            logger.debug(f"Pattern #{new_pattern.id}: BUY PHASE1 started, point_1={h:.5f}")

        # Update all existing patterns
        for pattern in self._buy_patterns:
            signal = self._update_single_buy_pattern(pattern, candle)
            if signal:
                logger.info(f"Pattern #{pattern.id}: BUY COMPLETED → taking this signal")
                return signal

        # Remove invalid patterns
        self._buy_patterns = [p for p in self._buy_patterns if p.phase != "INVALID"]
        
        return None

    def _update_single_buy_pattern(self, pattern: PatternState, candle: pd.Series) -> Optional[Signal]:
        """Update a single BUY pattern state machine."""
        o = candle["open"]
        c = candle["close"]
        h = candle["high"]
        l = candle["low"]
        is_green = c > o
        is_red = c < o

        # PHASE1: accumulating consecutive greens
        if pattern.phase == "PHASE1_DROP":
            if is_green:
                pattern.green_count += 1
                pattern.point_1 = max(pattern.point_1, h)
            elif is_red and pattern.green_count >= self.params["min_green_candles"]:
                pattern.phase = "PHASE2_PULLBACK1"
                pattern.red1_count = 1
                pattern.pullback1_low = l
                logger.debug(f"Pattern #{pattern.id}: → PHASE2")
            else:
                pattern.phase = "INVALID"
            return None

        # PHASE2: first pullback (reds)
        if pattern.phase == "PHASE2_PULLBACK1":
            if is_red:
                if pattern.red1_count >= 1 and c > pattern.point_1:
                    pattern.phase = "INVALID"
                    return None
                pattern.red1_count += 1
                pattern.pullback1_low = min(pattern.pullback1_low, l)
            elif is_green and pattern.red1_count >= self.params["min_red_candles"]:
                pattern.phase = "PHASE3_BREAK"
                logger.debug(f"Pattern #{pattern.id}: → PHASE3, waiting for break of {pattern.point_1:.5f}")
                if c > pattern.point_1:
                    pattern.phase = "PHASE4_PULLBACK2"
                    pattern.red2_count = 0
                    pattern.pullback2_low = l
                    pattern.point_2 = None
                    logger.debug(f"Pattern #{pattern.id}: → PHASE4 (immediate break)")
            elif is_green:
                pattern.phase = "INVALID"
            return None

        # PHASE3: waiting for break of point_1
        if pattern.phase == "PHASE3_BREAK":
            if pattern.pullback1_low and c < pattern.pullback1_low:
                pattern.phase = "INVALID"
                return None
            if c > pattern.point_1:
                pattern.phase = "PHASE4_PULLBACK2"
                pattern.red2_count = 0
                pattern.pullback2_low = l
                pattern.point_2 = None
                logger.debug(f"Pattern #{pattern.id}: → PHASE4 (point_1 broken)")
            return None

        # PHASE4: second pullback (reds)
        if pattern.phase == "PHASE4_PULLBACK2":
            if pattern.pullback1_low and c < pattern.pullback1_low:
                pattern.phase = "INVALID"
                return None
            if is_red:
                if pattern.red2_count >= 1 and c > pattern.point_1:
                    pattern.phase = "INVALID"
                    return None
                pattern.red2_count += 1
                pattern.pullback2_low = min(pattern.pullback2_low, l)
                if pattern.point_2 is None:
                    pattern.point_2 = h
                else:
                    pattern.point_2 = max(pattern.point_2, h)
            elif is_green and pattern.red2_count >= self.params["min_red_candles"]:
                pattern.phase = "PHASE5_ENTRY"
                logger.debug(f"Pattern #{pattern.id}: → PHASE5, waiting for entry at {pattern.point_2:.5f}")
                if pattern.point_2 and c >= pattern.point_2:
                    return self._generate_buy_entry(pattern, c, df)
            return None

        # PHASE5: waiting for entry
        if pattern.phase == "PHASE5_ENTRY":
            if pattern.pullback1_low and c < pattern.pullback1_low:
                pattern.phase = "INVALID"
                return None
            if pattern.point_2 and c >= pattern.point_2:
                return self._generate_buy_entry(pattern, c, df)
            return None

        return None

    def _generate_buy_entry(self, pattern: PatternState, entry_price: float, df: pd.DataFrame) -> Optional[Signal]:
        """Generate BUY entry signal from completed pattern."""
        # Check trend filter before opening position
        if not self._is_trend_buy_allowed(df):
            pattern.phase = "INVALID"
            logger.info(
                f"Pattern #{pattern.id}: BUY BLOCKED by trend filter - invalidating pattern"
            )
            return None
        
        stop_loss = pattern.pullback2_low
        risk = entry_price - stop_loss
        take_profit = entry_price + (risk * 2.0)

        logger.info(
            f"Pattern #{pattern.id}: BUY ENTRY at {entry_price:.5f} | "
            f"SL={stop_loss:.5f} TP={take_profit:.5f} risk={risk:.5f}"
        )

        # Save snapshot for visualizer
        self.last_pattern_snapshot = {
            "direction": "BUY",
            "point_1": pattern.point_1,
            "pullback1_low": pattern.pullback1_low,
            "point_2": pattern.point_2,
            "pullback2_low": stop_loss,
            "entry": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "risk": risk,
        }
        self._save_snapshot()

        return Signal(
            action="BUY",
            stop_loss=round(stop_loss, 5),
            take_profit=round(take_profit, 5),
            reason=f"Pattern #{pattern.id} BUY: entry={entry_price:.5f} SL={stop_loss:.5f} TP={take_profit:.5f}",
        )

    # ── Reset all patterns ────────────────────────────────────────────────────

    def _reset_all_patterns(self):
        """Reset all tracked patterns when one completes."""
        self._sell_patterns.clear()
        self._buy_patterns.clear()
        logger.info("All patterns reset after completed entry")

