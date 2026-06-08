"""
strategies/change_of_direction_strategy.py
-------------------------------------------
Change of Direction (COD) Strategy — reversal-based entry using a
4-phase state machine.

Philosophy:
    Identify a bearish move (consecutive red candles), wait for a pullback
    that confirms the reversal, then wait for price to break the first low,
    form a second pullback, and enter when that second low is broken.

Entry Logic (SELL):
    PHASE 1 — Initial drop (consecutive red candles)
        • 2+ consecutive red candles
        • point_1       = lowest low of the red candles
        • first_red_open = open of the first red candle (pullback reference)
        • reset_level   = high of the very first red candle

    PHASE 2 — First pullback (2+ greens, not necessarily consecutive)
        • At least one green must exceed first_red_open
        • pullback_high = highest high of the pullback (not used for SL here)
        • Ends when price turns red again

    PHASE 3 — Break of point_1
        • Wait for close < point_1 → confirms bearish continuation

    PHASE 4 — Second pullback (2+ greens, not necessarily consecutive)
        • second_pullback_high = highest high → Stop Loss
        • point_2              = lowest low of this pullback

    ENTRY — when close <= point_2 → SELL
        • SL  = second_pullback_high
        • TP  = entry - (SL - entry) × 2

    RESET → if close > reset_level at any phase → back to IDLE

Entry Logic (BUY):
    Mirror of SELL.
"""

from typing import Optional
import json
import os
import pandas as pd

from strategies.base_strategy import BaseStrategy, Signal
from models.position import Position
from utils.logger import get_logger

logger = get_logger(__name__)

# File where the last detected pattern is persisted between sessions
_SNAPSHOT_FILE = os.path.join(os.path.dirname(__file__), "..", "logs", "last_pattern_snapshot.json")

# ── State machine phases ──────────────────────────────────────────────────────
_IDLE              = "IDLE"
_PHASE1_DROP       = "PHASE1_DROP"       # accumulating consecutive red candles
_PHASE2_PULLBACK1  = "PHASE2_PULLBACK1"  # first pullback (greens)
_PHASE3_BREAK      = "PHASE3_BREAK"      # waiting for break of point_1
_PHASE4_PULLBACK2  = "PHASE4_PULLBACK2"  # second pullback (greens)
_PHASE5_ENTRY      = "PHASE5_ENTRY"      # waiting for break of point_2


class ChangeOfDirectionStrategy(BaseStrategy):
    """
    Change of Direction (COD) Strategy — 4-phase state machine.

    Parameters:
        min_red_candles   (int):  Minimum consecutive red candles (default 2)
        min_green_candles (int):  Minimum green candles per pullback (default 2)
        allow_short       (bool): Enable SELL signals (default True)
        allow_long        (bool): Enable BUY signals  (default True)
    """

    def __init__(self, params: Optional[dict] = None):
        defaults = {
            "min_red_candles":    2,
            "min_green_candles":  2,
            "allow_short":        True,
            "allow_long":         True,
            "ema_buffer_pct":     0.2,  # EMA neutral zone buffer (%)
            # kept for compatibility with bot infrastructure
            "exit_pct_below_ema": 0.3,
            "ema_fast":           21,
            "ema_slow":           50,
            "atr_period":         14,
            "rsi_period":         14,
        }
        if params:
            defaults.update(params)
        super().__init__(defaults)
        self._reset_sell_state()
        self._reset_buy_state()

        # ── Last detected pattern snapshot (for visualizer) ───────────────
        # Populated every time a SELL or BUY entry is confirmed
        # Persisted to disk so it survives between sessions
        self.last_pattern_snapshot: dict = self._load_snapshot()

    # ── Main Signal ───────────────────────────────────────────────────────────

    def generate_signal(
        self,
        df: pd.DataFrame,
        current_position: Optional[Position] = None,
    ) -> Signal:
        """Evaluate the last closed candle and return a trading signal."""
        if len(df) < 45:  # Need at least 40 for EMA40 + buffer
            return Signal("HOLD", reason=f"Not enough data ({len(df)}/45 rows)")

        last = df.iloc[-1]

        if current_position:
            return self._check_exit(last, current_position)

        # ── Trend direction filter using EMA40 on M5 ──────────────────────
        # Note: df is already M5 data from broker, we compute EMA40 on it
        trend_buy_allowed  = self._is_trend_buy_allowed(df)
        trend_sell_allowed = self._is_trend_sell_allowed(df)

        if self.params["allow_short"] and trend_sell_allowed:
            sig = self._update_sell_state(last)
            if sig:
                return sig

        if self.params["allow_long"] and trend_buy_allowed:
            sig = self._update_buy_state(last)
            if sig:
                return sig

        return Signal(
            "HOLD",
            reason=f"COD: sell={self._sell_phase} buy={self._buy_phase} | "
                   f"trend_buy={trend_buy_allowed} trend_sell={trend_sell_allowed}",
        )

    # ── SELL State Machine ────────────────────────────────────────────────────

    def _update_sell_state(self, candle: pd.Series) -> Optional[Signal]:
        o = candle["open"]
        c = candle["close"]
        h = candle["high"]
        l = candle["low"]

        is_red   = c < o
        is_green = c > o

        # ── RESET: only in PHASE4/PHASE5 — second pullback must not exceed pullback1_high ──
        if self._sell_phase in (_PHASE4_PULLBACK2, _PHASE5_ENTRY):
            if self._sell_pullback1_high is not None and c > self._sell_pullback1_high:
                logger.debug(
                    f"COD SELL RESET: close={c:.5f} > pullback1_high={self._sell_pullback1_high:.5f}"
                )
                self._reset_sell_state()
                return None

        # ── IDLE ──────────────────────────────────────────────────────────
        if self._sell_phase == _IDLE:
            if is_red:
                self._sell_phase         = _PHASE1_DROP
                self._sell_point_1       = l        # lowest low so far
                self._sell_red_count     = 1
                logger.debug(
                    f"COD SELL PHASE1: first red. point_1={l:.5f}"
                )
            return None

        # ── PHASE 1: consecutive red candles ─────────────────────────────
        if self._sell_phase == _PHASE1_DROP:
            if is_red:
                self._sell_red_count += 1
                self._sell_point_1 = min(self._sell_point_1, l)
                logger.debug(
                    f"COD SELL PHASE1: red #{self._sell_red_count} "
                    f"point_1={self._sell_point_1:.5f}"
                )
            elif is_green and self._sell_red_count >= self.params["min_red_candles"]:
                # Enough consecutive reds → start first pullback
                self._sell_phase              = _PHASE2_PULLBACK1
                self._sell_green1_count       = 1
                self._sell_pullback1_high     = h
                logger.debug(
                    f"COD SELL PHASE2: first pullback started."
                )
            else:
                # Green before enough reds → reset
                logger.info(
                    f"COD SELL RESET PHASE1: green interrupted reds "
                    f"(had {self._sell_red_count}/{self.params['min_red_candles']} reds) "
                    f"close={c:.5f} open={o:.5f}"
                )
                self._reset_sell_state()
            return None

        # ── PHASE 2: first pullback (greens, not necessarily consecutive) ─
        if self._sell_phase == _PHASE2_PULLBACK1:
            if is_green:
                # Validate: from 2nd green onwards, close must NOT go below point_1
                if self._sell_green1_count >= 1 and c < self._sell_point_1:
                    logger.info(
                        f"COD SELL RESET PHASE2: green #{self._sell_green1_count + 1} close below point_1 "
                        f"(close={c:.5f} < point_1={self._sell_point_1:.5f})"
                    )
                    self._reset_sell_state()
                    return None
                self._sell_green1_count += 1
                self._sell_pullback1_high = max(self._sell_pullback1_high, h)
                logger.debug(
                    f"COD SELL PHASE2: green #{self._sell_green1_count} "
                    f"ph1={self._sell_pullback1_high:.5f}"
                )
            elif is_red:
                if self._sell_green1_count >= self.params["min_green_candles"]:
                    # Valid first pullback → wait for break of point_1
                    self._sell_phase = _PHASE3_BREAK
                    logger.info(
                        f"COD SELL PHASE3: waiting for break of "
                        f"point_1={self._sell_point_1:.5f} "
                        f"pullback1_high={self._sell_pullback1_high:.5f}"
                    )
                    # Check if this red candle already breaks point_1
                    return self._check_sell_break(candle)
                else:
                    logger.info(
                        f"COD SELL RESET PHASE2: not enough greens "
                        f"({self._sell_green1_count}/{self.params['min_green_candles']})"
                    )
                    self._reset_sell_state()
            return None

        # ── PHASE 3: wait for close < point_1 ────────────────────────────
        if self._sell_phase == _PHASE3_BREAK:
            return self._check_sell_break(candle)

        # ── PHASE 4: second pullback (greens, not necessarily consecutive) 
        if self._sell_phase == _PHASE4_PULLBACK2:
            if is_green:
                # Validate: from 2nd green onwards, close must NOT go below point_1
                if self._sell_green2_count >= 1 and c < self._sell_point_1:
                    logger.info(
                        f"COD SELL RESET PHASE4: green #{self._sell_green2_count + 1} close below point_1 "
                        f"(close={c:.5f} < point_1={self._sell_point_1:.5f})"
                    )
                    self._reset_sell_state()
                    return None
                self._sell_green2_count   += 1
                self._sell_pullback2_high  = max(self._sell_pullback2_high, h)
                # point_2 = lowest low of the green pullback candles only
                if self._sell_point_2 is None:
                    self._sell_point_2 = l
                else:
                    self._sell_point_2 = min(self._sell_point_2, l)
                logger.info(
                    f"COD SELL PHASE4: green #{self._sell_green2_count} "
                    f"close={c:.5f} low={l:.5f} ph2={self._sell_pullback2_high:.5f} "
                    f"point_2={self._sell_point_2:.5f} point_1={self._sell_point_1:.5f}"
                )
            elif is_red:
                if self._sell_green2_count >= self.params["min_green_candles"]:
                    # Valid second pullback → wait for entry
                    self._sell_phase = _PHASE5_ENTRY
                    logger.info(
                        f"COD SELL PHASE5: waiting for break of "
                        f"point_2={self._sell_point_2:.5f} "
                        f"SL={self._sell_pullback2_high:.5f}"
                    )
                    return self._check_sell_entry(candle)
                else:
                    # Not enough greens → keep accumulating (stay in PHASE4)
                    logger.info(
                        f"COD SELL PHASE4: red candle but only "
                        f"{self._sell_green2_count}/{self.params['min_green_candles']} greens — waiting for more"
                    )
            return None

        # ── PHASE 5: wait for close <= point_2 ───────────────────────────
        if self._sell_phase == _PHASE5_ENTRY:
            return self._check_sell_entry(candle)

        return None

    def _check_sell_break(self, candle: pd.Series) -> Optional[Signal]:
        """Check if price broke below point_1 (phase 3 → phase 4)."""
        c = candle["close"]
        h = candle["high"]

        if c < self._sell_point_1:
            # Break confirmed → start second pullback tracking
            # point_2 starts at None — will be set by the first GREEN candle in PHASE4
            self._sell_phase          = _PHASE4_PULLBACK2
            self._sell_green2_count   = 0
            self._sell_pullback2_high = h
            self._sell_point_2        = None   # set by first green in PHASE4
            logger.info(
                f"COD SELL PHASE4: point_1 broken! "
                f"close={c:.5f} < point_1={self._sell_point_1:.5f}"
            )
        else:
            logger.info(
                f"COD SELL PHASE3 waiting: close={c:.5f} "
                f">= point_1={self._sell_point_1:.5f}"
            )
        return None

    def _check_sell_entry(self, candle: pd.Series) -> Optional[Signal]:
        """Check if price broke below point_2 → SELL entry."""
        c = candle["close"]

        # point_2 not set yet (no green candle in PHASE4 yet)
        if self._sell_point_2 is None:
            return None

        if c <= self._sell_point_2:
            entry_price    = c
            stop_loss      = self._sell_pullback2_high
            point_2        = self._sell_point_2
            risk           = stop_loss - entry_price
            take_profit    = entry_price - (risk * 2.0)

            logger.info(
                f"COD SELL ENTRY: close={entry_price:.5f} <= point_2={point_2:.5f} | "
                f"SL={stop_loss:.5f} TP={take_profit:.5f} risk={risk:.5f}"
            )

            # ── Save pattern snapshot for visualizer ──────────────────────
            self.last_pattern_snapshot = {
                "direction":      "SELL",
                "point_1":        self._sell_point_1,
                "pullback1_high": self._sell_pullback1_high,
                "point_2":        point_2,
                "pullback2_high": stop_loss,
                "entry":          entry_price,
                "stop_loss":      stop_loss,
                "take_profit":    take_profit,
                "risk":           risk,
                "candle":         candle,
            }
            self._save_snapshot()

            self._reset_sell_state()
            return Signal(
                action="SELL",
                stop_loss=round(stop_loss, 5),
                take_profit=round(take_profit, 5),
                reason=(
                    f"COD SELL: close={entry_price:.5f} <= point_2={point_2:.5f} | "
                    f"SL={stop_loss:.5f} TP={take_profit:.5f}"
                ),
            )

        logger.info(
            f"COD SELL PHASE5 waiting: close={c:.5f} > point_2={self._sell_point_2:.5f}"
        )
        return None

    def _reset_sell_state(self):
        self._sell_phase              = _IDLE
        self._sell_point_1            = None
        self._sell_red_count          = 0
        self._sell_green1_count       = 0
        self._sell_pullback1_high     = None
        self._sell_green2_count       = 0
        self._sell_pullback2_high     = None
        self._sell_point_2            = None

    # ── BUY State Machine (mirror of SELL) ───────────────────────────────────

    def _update_buy_state(self, candle: pd.Series) -> Optional[Signal]:
        o = candle["open"]
        c = candle["close"]
        h = candle["high"]
        l = candle["low"]

        is_green = c > o
        is_red   = c < o

        # ── RESET: only in PHASE4/PHASE5 — second pullback must not go below pullback1_low ──
        if self._buy_phase in (_PHASE4_PULLBACK2, _PHASE5_ENTRY):
            if self._buy_pullback1_low is not None and c < self._buy_pullback1_low:
                logger.debug(
                    f"COD BUY RESET: close={c:.5f} < pullback1_low={self._buy_pullback1_low:.5f}"
                )
                self._reset_buy_state()
                return None

        # ── IDLE ──────────────────────────────────────────────────────────
        if self._buy_phase == _IDLE:
            if is_green:
                self._buy_phase            = _PHASE1_DROP
                self._buy_point_1          = h
                self._buy_green_count      = 1
            return None

        # ── PHASE 1: consecutive green candles ────────────────────────────
        if self._buy_phase == _PHASE1_DROP:
            if is_green:
                self._buy_green_count += 1
                self._buy_point_1 = max(self._buy_point_1, h)
            elif is_red and self._buy_green_count >= self.params["min_green_candles"]:
                self._buy_phase              = _PHASE2_PULLBACK1
                self._buy_red1_count         = 1
                self._buy_pullback1_low      = l
            else:
                self._reset_buy_state()
            return None

        # ── PHASE 2: first pullback (reds, not necessarily consecutive) ───
        if self._buy_phase == _PHASE2_PULLBACK1:
            if is_red:
                # Validate: from 2nd red onwards, close must NOT exceed point_1
                if self._buy_red1_count >= 1 and c > self._buy_point_1:
                    logger.debug(
                        f"COD BUY RESET PHASE2: red #{self._buy_red1_count + 1} close above point_1 "
                        f"(close={c:.5f} > point_1={self._buy_point_1:.5f})"
                    )
                    self._reset_buy_state()
                    return None
                self._buy_red1_count += 1
                self._buy_pullback1_low = min(self._buy_pullback1_low, l)
            elif is_green:
                if self._buy_red1_count >= self.params["min_red_candles"]:
                    self._buy_phase = _PHASE3_BREAK
                    return self._check_buy_break(candle)
                else:
                    self._reset_buy_state()
            return None

        # ── PHASE 3: wait for close > point_1 ────────────────────────────
        if self._buy_phase == _PHASE3_BREAK:
            return self._check_buy_break(candle)

        # ── PHASE 4: second pullback (reds, not necessarily consecutive) ──
        if self._buy_phase == _PHASE4_PULLBACK2:
            if is_red:
                # Validate: from 2nd red onwards, close must NOT exceed point_1
                if self._buy_red2_count >= 1 and c > self._buy_point_1:
                    logger.debug(
                        f"COD BUY RESET PHASE4: red #{self._buy_red2_count + 1} close above point_1 "
                        f"(close={c:.5f} > point_1={self._buy_point_1:.5f})"
                    )
                    self._reset_buy_state()
                    return None
                self._buy_red2_count    += 1
                self._buy_pullback2_low  = min(self._buy_pullback2_low, l)
                # point_2 = highest high of the red pullback candles only
                if self._buy_point_2 is None:
                    self._buy_point_2 = h
                else:
                    self._buy_point_2 = max(self._buy_point_2, h)
                logger.info(
                    f"COD BUY PHASE4: red #{self._buy_red2_count} "
                    f"close={c:.5f} high={h:.5f} pb2_low={self._buy_pullback2_low:.5f} "
                    f"point_2={self._buy_point_2:.5f} point_1={self._buy_point_1:.5f}"
                )
            elif is_green:
                if self._buy_red2_count >= self.params["min_red_candles"]:
                    self._buy_phase = _PHASE5_ENTRY
                    return self._check_buy_entry(candle)
            return None

        # ── PHASE 5: wait for close >= point_2 ───────────────────────────
        if self._buy_phase == _PHASE5_ENTRY:
            return self._check_buy_entry(candle)

        return None

    def _check_buy_break(self, candle: pd.Series) -> Optional[Signal]:
        """Check if price broke above point_1 (phase 3 → phase 4)."""
        c = candle["close"]
        l = candle["low"]

        if c > self._buy_point_1:
            self._buy_phase         = _PHASE4_PULLBACK2
            self._buy_red2_count    = 0
            self._buy_pullback2_low = l
            self._buy_point_2       = None   # set by first red in PHASE4
            logger.debug(
                f"COD BUY PHASE4: point_1 broken. "
                f"close={c:.5f} > point_1={self._buy_point_1:.5f}"
            )
        else:
            logger.debug(
                f"COD BUY PHASE3 waiting: close={c:.5f} "
                f"<= point_1={self._buy_point_1:.5f}"
            )
        return None

    def _check_buy_entry(self, candle: pd.Series) -> Optional[Signal]:
        c = candle["close"]

        if self._buy_point_2 is None:
            return None

        if c >= self._buy_point_2:
            entry_price = c
            stop_loss   = self._buy_pullback2_low
            point_2     = self._buy_point_2
            risk        = entry_price - stop_loss
            take_profit = entry_price + (risk * 2.0)

            logger.info(
                f"COD BUY ENTRY: close={entry_price:.5f} >= point_2={point_2:.5f} | "
                f"SL={stop_loss:.5f} TP={take_profit:.5f}"
            )

            # ── Save pattern snapshot for visualizer ──────────────────────
            self.last_pattern_snapshot = {
                "direction":      "BUY",
                "point_1":        self._buy_point_1,
                "pullback1_low":  self._buy_pullback1_low,
                "point_2":        point_2,
                "pullback2_low":  stop_loss,
                "entry":          entry_price,
                "stop_loss":      stop_loss,
                "take_profit":    take_profit,
                "risk":           risk,
                "candle":         candle,
            }
            self._save_snapshot()

            self._reset_buy_state()

            return Signal(
                action="BUY",
                stop_loss=round(stop_loss, 5),
                take_profit=round(take_profit, 5),
                reason=(
                    f"COD BUY: close={entry_price:.5f} >= point_2={point_2:.5f} | "
                    f"SL={stop_loss:.5f} TP={take_profit:.5f}"
                ),
            )
        return None

    def _reset_buy_state(self):
        self._buy_phase              = _IDLE
        self._buy_point_1            = None
        self._buy_green_count        = 0
        self._buy_red1_count         = 0
        self._buy_pullback1_low      = None
        self._buy_red2_count         = 0
        self._buy_pullback2_low      = None
        self._buy_point_2            = None

    # ── Trend Filter (EMA40 M5) ───────────────────────────────────────────────

    def _is_trend_buy_allowed(self, df: pd.DataFrame) -> bool:
        """Returns True if current price is ABOVE upper zone (clear uptrend)."""
        if len(df) < 40:
            return True  # Not enough data, allow by default
        
        ema40 = df["close"].ewm(span=40, adjust=False).mean().iloc[-1]
        current_price = df["close"].iloc[-1]
        
        buffer_pct = self.params.get("ema_buffer_pct", 0.4)
        upper_zone = ema40 * (1.0 + buffer_pct / 100.0)
        lower_zone = ema40 * (1.0 - buffer_pct / 100.0)
        
        # Only allow BUY if price is ABOVE the upper zone (clear uptrend)
        if current_price > upper_zone:
            logger.debug(
                f"BUY allowed: price={current_price:.5f} > upper_zone={upper_zone:.5f}"
            )
            return True
        
        logger.debug(
            f"BUY blocked: price={current_price:.5f} in neutral zone "
            f"[{lower_zone:.5f} - {upper_zone:.5f}]"
        )
        return False

    def _is_trend_sell_allowed(self, df: pd.DataFrame) -> bool:
        """Returns True if current price is BELOW lower zone (clear downtrend)."""
        if len(df) < 40:
            return True  # Not enough data, allow by default
        
        ema40 = df["close"].ewm(span=40, adjust=False).mean().iloc[-1]
        current_price = df["close"].iloc[-1]
        
        buffer_pct = self.params.get("ema_buffer_pct", 0.4)
        upper_zone = ema40 * (1.0 + buffer_pct / 100.0)
        lower_zone = ema40 * (1.0 - buffer_pct / 100.0)
        
        # Only allow SELL if price is BELOW the lower zone (clear downtrend)
        if current_price < lower_zone:
            logger.debug(
                f"SELL allowed: price={current_price:.5f} < lower_zone={lower_zone:.5f}"
            )
            return True
        
        logger.debug(
            f"SELL blocked: price={current_price:.5f} in neutral zone "
            f"[{lower_zone:.5f} - {upper_zone:.5f}]"
        )
        return False

    # ── Exit Check ────────────────────────────────────────────────────────────

    def _check_exit(self, last: pd.Series, position: Position) -> Signal:
        c = last["close"]

        if position.direction == "SELL":
            if c >= position.stop_loss:
                return Signal(
                    action="CLOSE",
                    reason=f"COD SELL exit: SL hit. close={c:.5f} >= SL={position.stop_loss:.5f}",
                )
            if c <= position.take_profit:
                return Signal(
                    action="CLOSE",
                    reason=f"COD SELL exit: TP hit. close={c:.5f} <= TP={position.take_profit:.5f}",
                )

        elif position.direction == "BUY":
            if c <= position.stop_loss:
                return Signal(
                    action="CLOSE",
                    reason=f"COD BUY exit: SL hit. close={c:.5f} <= SL={position.stop_loss:.5f}",
                )
            if c >= position.take_profit:
                return Signal(
                    action="CLOSE",
                    reason=f"COD BUY exit: TP hit. close={c:.5f} >= TP={position.take_profit:.5f}",
                )

        return Signal(
            "HOLD",
            reason=(
                f"COD {position.direction}: intact. "
                f"close={c:.5f} SL={position.stop_loss:.5f} TP={position.take_profit:.5f}"
            ),
        )

    # ── Required abstract methods ─────────────────────────────────────────────

    def calculate_stop_loss(self, df: pd.DataFrame, direction: str) -> float:
        return 0.0

    def update_trailing_stop(self, df: pd.DataFrame, position: Position) -> Optional[float]:
        return None

    # ── Snapshot persistence ──────────────────────────────────────────────────

    def _save_snapshot(self) -> None:
        """Save last_pattern_snapshot to disk as JSON."""
        try:
            # Convert pandas Series to dict if present
            data = {k: v for k, v in self.last_pattern_snapshot.items() if k != "candle"}
            with open(_SNAPSHOT_FILE, "w") as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Pattern snapshot saved to {_SNAPSHOT_FILE}")
        except Exception as e:
            logger.debug(f"Could not save snapshot: {e}")

    def _load_snapshot(self) -> dict:
        """Load last_pattern_snapshot from disk if it exists."""
        try:
            if os.path.exists(_SNAPSHOT_FILE):
                with open(_SNAPSHOT_FILE, "r") as f:
                    data = json.load(f)
                logger.info(
                    f"Pattern snapshot loaded: direction={data.get('direction')} "
                    f"entry={data.get('entry')}"
                )
                return data
        except Exception as e:
            logger.debug(f"Could not load snapshot: {e}")
        return {}
