"""
strategies/ema_trend_strategy.py
---------------------------------
EMA Pullback Strategy — ride the EMA as dynamic support.

Philosophy:
    The EMA is not just an indicator — it IS the trade.
    It acts as support on the way up and as the trailing stop on the way down.
    Small losses when the EMA breaks. Big wins when the trend runs.

Entry Rule (Pullback Touch):
    The price pulls back to the EMA from above:
        - Low of the candle touches or crosses the EMA
        - Close of the candle is ABOVE the EMA  ← bounce confirmed
        - EMA_fast > EMA_slow                   ← uptrend filter
    This captures the moment price "kisses" the EMA and bounces.

Exit Rule (EMA Break with buffer):
    Close drops more than `exit_pct_below_ema` % below the EMA.
    Example: exit_pct_below_ema = 0.3 → exit if close < EMA * (1 - 0.003)
    This avoids closing on a tiny wick below the EMA (noise).
    Configurable from the UI.

Trailing Stop Rule (EMA as stop):
    After each closed candle, the stop moves to the current EMA value.
    The stop only moves UP — never down.
    This means: as long as price stays above the EMA, we stay in.
    The moment the EMA itself rises, our protection rises with it.

Visual intuition (coming from MQL5):
    Entry:  price bounces off EMA like a rubber band
    Stop:   = EMA value, updated every candle
    Exit:   price closes clearly below EMA (not just a wick)
"""

from typing import Optional
import pandas as pd

from strategies.base_strategy import BaseStrategy, Signal
from models.position import Position
from utils.indicators import compute_all
from utils.logger import get_logger
import config

logger = get_logger(__name__)


class EmaTrendStrategy(BaseStrategy):
    """
    EMA Pullback + EMA Trailing Stop strategy.

    Parameters (all configurable from UI):
        ema_fast (int):              Fast EMA period used for entry/exit/stop. Default 21.
        ema_slow (int):              Slow EMA period used as trend filter. Default 50.
        atr_period (int):            ATR period for touch tolerance. Default 14.
        touch_tolerance_atr (float): How close price must get to EMA to count as a touch.
                                     Expressed as ATR multiplier. Default 0.5.
        exit_pct_below_ema (float):  % below/above EMA that triggers exit. Default 0.3.
        min_candle_body_pct (float): Min candle body as % of ATR to filter doji. Default 0.1.
        rsi_period (int):            RSI period. Default 14.
        use_rsi_filter (bool):       Enable RSI filter on entry. Default False.
        allow_short (bool):          Enable SELL signals (short selling). Default False.
    """

    def __init__(self, params: Optional[dict] = None):
        defaults = {
            "ema_fast":             config.EMA_FAST,
            "ema_slow":             config.EMA_SLOW,
            "atr_period":           config.ATR_PERIOD,
            "touch_tolerance_atr":  0.5,
            "exit_pct_below_ema":   0.3,
            "rsi_period":           config.RSI_PERIOD,
            "use_rsi_filter":       False,
            "allow_short":          False,
        }
        if params:
            defaults.update(params)
        super().__init__(defaults)

    # ── Main Signal ───────────────────────────────────────────────────────────

    def generate_signal(
        self,
        df: pd.DataFrame,
        current_position: Optional[Position] = None,
    ) -> Signal:
        """
        Evaluate the last closed candle and return a trading signal.
        """
        min_rows = self.params["ema_slow"] + self.params["atr_period"] + 5
        if len(df) < min_rows:
            return Signal("HOLD", reason=f"Not enough data ({len(df)}/{min_rows} rows)")

        # Compute all indicators
        df = compute_all(
            df,
            ema_fast=self.params["ema_fast"],
            ema_slow=self.params["ema_slow"],
            atr_period=self.params["atr_period"],
            rsi_period=self.params["rsi_period"],
        )

        last = df.iloc[-1]

        # Guard: indicators must be ready
        if pd.isna(last["ema_fast"]) or pd.isna(last["ema_slow"]) or pd.isna(last["atr"]):
            return Signal("HOLD", reason="Indicators not ready (NaN values)")

        close    = last["close"]
        low      = last["low"]
        high     = last["high"]
        open_p   = last["open"]
        ema_fast = last["ema_fast"]
        ema_slow = last["ema_slow"]
        atr      = last["atr"]

        # ── If we have an open position: check exit first ─────────────────────
        if current_position:
            return self._check_exit(last, current_position)

        # ── Trend filter: only trade in the direction of the trend ────────────
        # BUY  requires EMA_fast > EMA_slow (uptrend)
        # SELL requires EMA_fast < EMA_slow (downtrend) — checked inside short block
        if not self.params["allow_short"] and ema_fast <= ema_slow:
            return Signal(
                "HOLD",
                reason=f"No uptrend: open={open_p:.5f}, close={close:.5f}, EMA_fast={ema_fast:.5f} <= EMA_slow={ema_slow:.5f}"
            )

        # ── RSI filter (optional) ─────────────────────────────────────────────
        if self.params["use_rsi_filter"]:
            rsi_val = last.get("rsi", float("nan"))
            if not pd.isna(rsi_val) and rsi_val > config.RSI_OVERBOUGHT:
                return Signal(
                    "HOLD",
                    reason=f"RSI overbought ({rsi_val:.1f}), skip entry"
                )

        # ── Entry: EMA Pullback Touch ─────────────────────────────────────────
        #
        # Conditions:
        #   1. EMA is between open and close (price crossed the EMA during the candle)
        #   2. Close is above the EMA (bounce confirmed - uptrend)
        #   3. EMA_fast > EMA_slow (uptrend filter)
        #
        # Logic: If EMA is between open and close, it means the price touched the EMA
        # during the candle formation. Combined with close > EMA, it's a valid entry.
        #
        ema_between_open_close = (
            (open_p <= ema_fast <= close) or 
            (close <= ema_fast <= open_p)
        )
        bounced = close > ema_fast

        if ema_between_open_close and bounced:
            stop = self.calculate_stop_loss(df, "BUY")
            return Signal(
                action="BUY",
                stop_loss=stop,
                reason=(
                    f"EMA touch+bounce: EMA={ema_fast:.5f} between "
                    f"open={open_p:.5f} and close={close:.5f}"
                ),
            )

        # ── SHORT entry (mirror logic, only if allow_short=True) ─────────────
        if self.params["allow_short"]:
            # Downtrend filter: EMA_fast must be BELOW EMA_slow
            if ema_fast < ema_slow:
                # Price touches EMA from above and bounces down
                # EMA is between open and close, close is below EMA
                ema_between_open_close_short = (
                    (open_p <= ema_fast <= close) or 
                    (close <= ema_fast <= open_p)
                )
                bounced_down = close < ema_fast

                if ema_between_open_close_short and bounced_down:
                    stop = self.calculate_stop_loss(df, "SELL")
                    return Signal(
                        action="SELL",
                        stop_loss=stop,
                        reason=(
                            f"EMA touch+bounce DOWN: EMA={ema_fast:.5f} between "
                            f"open={open_p:.5f} and close={close:.5f}"
                        ),
                    )
                else:
                    return Signal(
                        "HOLD",
                        reason=f"No SELL touch: open={open_p:.5f}, close={close:.5f}, EMA={ema_fast:.5f}"
                    )
            else:
                return Signal(
                    "HOLD",
                    reason=f"No downtrend: open={open_p:.5f}, close={close:.5f}, EMA_fast={ema_fast:.5f} >= EMA_slow={ema_slow:.5f}"
                )

        return Signal(
            "HOLD",
            reason=f"No EMA touch: open={open_p:.5f}, close={close:.5f}, EMA={ema_fast:.5f}"
        )

    # ── Exit Check ────────────────────────────────────────────────────────────

    def _check_exit(self, last: pd.Series, position: Position) -> Signal:
        """
        Exit when price moves enough against the EMA.

        BUY  → exit if close drops X% below EMA
        SELL → exit if close rises X% above EMA
        """
        open_p   = last["open"]
        close    = last["close"]
        ema_fast = last["ema_fast"]
        pct      = self.params["exit_pct_below_ema"] / 100.0

        if position.direction == "BUY":
            exit_level = ema_fast * (1.0 - pct)
            if close < exit_level:
                return Signal(
                    action="CLOSE",
                    reason=(
                        f"BUY exit: open={open_p:.5f}, close={close:.5f}, EMA={ema_fast:.5f} "
                        f"< exit_level={exit_level:.5f}"
                    ),
                )

        elif position.direction == "SELL":
            exit_level = ema_fast * (1.0 + pct)
            if close > exit_level:
                return Signal(
                    action="CLOSE",
                    reason=(
                        f"SELL exit: open={open_p:.5f}, close={close:.5f}, EMA={ema_fast:.5f} "
                        f"> exit_level={exit_level:.5f}"
                    ),
                )

        return Signal(
            "HOLD",
            reason=f"Position intact: open={open_p:.5f}, close={close:.5f}, EMA={ema_fast:.5f}"
        )

    # ── Stop Loss (initial) ───────────────────────────────────────────────────

    def calculate_stop_loss(self, df: pd.DataFrame, direction: str) -> float:
        """
        Initial stop loss = entry price ± exit_pct buffer.

        BUY:  stop = entry_price × (1 - exit_pct / 100)
        SELL: stop = entry_price × (1 + exit_pct / 100)
        """
        last  = df.iloc[-1]
        price = float(last["close"])   # entry price = current close
        pct   = self.params["exit_pct_below_ema"] / 100.0

        if direction == "BUY":
            return round(price * (1.0 - pct), 5)
        else:
            return round(price * (1.0 + pct), 5)

    def update_trailing_stop(
        self,
        df: pd.DataFrame,
        position: Position,
    ) -> Optional[float]:
        """
        Trailing stop = current price ± exit_pct buffer.

        As price moves in our favor, the stop follows it.
        The stop ONLY moves in the favorable direction — never back.

        BUY example with exit_pct = 0.3%:
            price=10  → stop = 10 × 0.997 = 9.970   (entry)
            price=11  → stop = 11 × 0.997 = 10.967  (moves up)
            price=12  → stop = 12 × 0.997 = 11.964  (moves up)
            price drops to 11.964 → stop hit → close with profit

        SELL is the mirror: stop = price × (1 + pct), only moves down.
        """
        last          = df.iloc[-1]
        current_price = float(last["close"])
        pct           = self.params["exit_pct_below_ema"] / 100.0

        if position.direction == "BUY":
            new_stop = round(current_price * (1.0 - pct), 5)
            if new_stop > position.effective_stop:
                logger.debug(
                    f"Trailing stop UP: {position.symbol} "
                    f"{position.effective_stop:.5f} → {new_stop:.5f} "
                    f"(price={current_price:.5f} - {self.params['exit_pct_below_ema']}%)"
                )
                return new_stop

        elif position.direction == "SELL":
            new_stop = round(current_price * (1.0 + pct), 5)
            if new_stop < position.effective_stop:
                logger.debug(
                    f"Trailing stop DOWN: {position.symbol} "
                    f"{position.effective_stop:.5f} → {new_stop:.5f} "
                    f"(price={current_price:.5f} + {self.params['exit_pct_below_ema']}%)"
                )
                return new_stop

        return None
