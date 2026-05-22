"""
tests/test_strategy.py
-----------------------
Unit tests for the EMA Pullback strategy.

Strategy logic under test:
  Entry BUY  : EMA_fast is between open and close AND close > EMA (bounce up)
               AND EMA_fast > EMA_slow (uptrend)
  Entry SELL : EMA_fast is between open and close AND close < EMA (bounce down)
               AND EMA_fast < EMA_slow (downtrend) AND allow_short=True
  Exit       : close < EMA * (1 - exit_pct%) for BUY
               close > EMA * (1 + exit_pct%) for SELL
  Trailing   : stop = current_price * (1 - pct), only moves favorably
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

from strategies.ema_trend_strategy import EmaTrendStrategy
from strategies.base_strategy import Signal
from models.position import Position


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_candles(n: int = 200, trend: str = "up", base: float = 2350.0) -> pd.DataFrame:
    """Generate synthetic OHLCV candles."""
    np.random.seed(42)
    now = datetime.now(timezone.utc)
    timestamps = [now - timedelta(hours=n - i) for i in range(n)]

    closes = [base]
    for _ in range(n - 1):
        if trend == "up":
            delta = np.random.uniform(0.5, 3.0)
        elif trend == "down":
            delta = np.random.uniform(-3.0, -0.5)
        else:
            delta = np.random.uniform(-1.5, 1.5)
        closes.append(max(closes[-1] + delta, base * 0.5))

    rows = []
    for i, close in enumerate(closes):
        open_ = closes[i - 1] if i > 0 else close
        wick  = abs(np.random.uniform(0, 1.5))
        rows.append({
            "open":   open_,
            "high":   max(open_, close) + wick,
            "low":    min(open_, close) - wick,
            "close":  close,
            "volume": 500.0,
        })

    return pd.DataFrame(rows, index=pd.DatetimeIndex(timestamps, tz="UTC"))


def make_position(direction: str = "BUY", entry: float = 2350.0, stop: float = 2330.0) -> Position:
    return Position(
        symbol="XAUUSD",
        direction=direction,
        entry_price=entry,
        lot_size=0.01,
        entry_time=datetime.now(timezone.utc),
        stop_loss=stop,
    )


@pytest.fixture
def strategy():
    return EmaTrendStrategy(params={
        "ema_fast":            21,
        "ema_slow":            50,
        "atr_period":          14,
        "touch_tolerance_atr": 0.5,
        "exit_pct_below_ema":  0.3,
        "rsi_period":          14,
        "use_rsi_filter":      False,
        "allow_short":         False,
    })


@pytest.fixture
def strategy_short():
    return EmaTrendStrategy(params={
        "ema_fast":            21,
        "ema_slow":            50,
        "atr_period":          14,
        "touch_tolerance_atr": 0.5,
        "exit_pct_below_ema":  0.3,
        "rsi_period":          14,
        "use_rsi_filter":      False,
        "allow_short":         True,
    })


# ── Entry Tests ───────────────────────────────────────────────────────────────

class TestEntry:

    def test_buy_when_ema_between_open_and_close_uptrend(self, strategy):
        """BUY when EMA is between open and close, close > EMA, uptrend."""
        df = make_candles(200, trend="up")
        from utils.indicators import compute_all
        df = compute_all(df, 21, 50, 14, 14)

        ema_val = float(df["ema_fast"].iloc[-1])

        # open below EMA, close above EMA → EMA is between them
        df.iloc[-1, df.columns.get_loc("open")]  = ema_val - 2.0
        df.iloc[-1, df.columns.get_loc("close")] = ema_val + 2.0

        signal = strategy.generate_signal(df, current_position=None)
        assert signal.action == "BUY", f"Expected BUY, got {signal.action}: {signal.reason}"

    def test_no_buy_when_ema_not_between_open_close(self, strategy):
        """HOLD when EMA is not between open and close."""
        df = make_candles(200, trend="up")
        from utils.indicators import compute_all
        df = compute_all(df, 21, 50, 14, 14)

        ema_val = float(df["ema_fast"].iloc[-1])

        # Both open and close above EMA — no cross
        df.iloc[-1, df.columns.get_loc("open")]  = ema_val + 5.0
        df.iloc[-1, df.columns.get_loc("close")] = ema_val + 10.0

        signal = strategy.generate_signal(df, current_position=None)
        assert signal.action == "HOLD"

    def test_no_buy_when_close_below_ema(self, strategy):
        """HOLD when EMA is between open/close but close < EMA (no bounce up)."""
        df = make_candles(200, trend="up")
        from utils.indicators import compute_all
        df = compute_all(df, 21, 50, 14, 14)

        ema_val = float(df["ema_fast"].iloc[-1])

        # open above EMA, close below EMA → EMA between them but close < EMA
        df.iloc[-1, df.columns.get_loc("open")]  = ema_val + 2.0
        df.iloc[-1, df.columns.get_loc("close")] = ema_val - 2.0

        signal = strategy.generate_signal(df, current_position=None)
        assert signal.action == "HOLD", f"Expected HOLD, got {signal.action}: {signal.reason}"

    def test_no_buy_in_downtrend(self, strategy):
        """HOLD when EMA_fast < EMA_slow (downtrend) and allow_short=False."""
        df = make_candles(200, trend="down")
        signal = strategy.generate_signal(df, current_position=None)
        assert signal.action == "HOLD"

    def test_not_enough_data(self, strategy):
        """HOLD when not enough candles for indicators."""
        df = make_candles(10)
        signal = strategy.generate_signal(df)
        assert signal.action == "HOLD"
        assert "Not enough data" in signal.reason

    def test_buy_signal_has_stop_loss(self, strategy):
        """BUY signal must include a stop loss below entry price."""
        df = make_candles(200, trend="up")
        from utils.indicators import compute_all
        df = compute_all(df, 21, 50, 14, 14)

        ema_val = float(df["ema_fast"].iloc[-1])
        df.iloc[-1, df.columns.get_loc("open")]  = ema_val - 2.0
        df.iloc[-1, df.columns.get_loc("close")] = ema_val + 2.0

        signal = strategy.generate_signal(df)
        if signal.action == "BUY":
            assert signal.stop_loss is not None
            entry = float(df["close"].iloc[-1])
            pct   = strategy.params["exit_pct_below_ema"] / 100.0
            assert signal.stop_loss == pytest.approx(entry * (1.0 - pct), abs=0.001)
            assert signal.stop_loss < entry


# ── Exit Tests ────────────────────────────────────────────────────────────────

class TestExit:

    def test_close_buy_when_price_breaks_below_ema(self, strategy):
        """CLOSE BUY when close drops more than exit_pct% under EMA."""
        df = make_candles(200, trend="up")
        from utils.indicators import compute_all
        df = compute_all(df, 21, 50, 14, 14)

        ema_val    = float(df["ema_fast"].iloc[-1])
        pct        = strategy.params["exit_pct_below_ema"] / 100.0
        exit_level = ema_val * (1.0 - pct)

        df.iloc[-1, df.columns.get_loc("close")]    = exit_level - 5.0
        df.iloc[-1, df.columns.get_loc("ema_fast")] = ema_val

        position = make_position("BUY", entry=ema_val + 10)
        signal   = strategy.generate_signal(df, current_position=position)
        assert signal.action == "CLOSE", f"Expected CLOSE, got {signal.action}: {signal.reason}"

    def test_hold_buy_within_buffer(self, strategy):
        """HOLD when close is slightly below EMA but within buffer."""
        df = make_candles(200, trend="up")
        from utils.indicators import compute_all
        df = compute_all(df, 21, 50, 14, 14)

        ema_val = float(df["ema_fast"].iloc[-1])
        pct     = strategy.params["exit_pct_below_ema"] / 100.0
        df.iloc[-1, df.columns.get_loc("close")] = ema_val * (1.0 - pct * 0.5)

        position = make_position("BUY", entry=ema_val + 10)
        signal   = strategy.generate_signal(df, current_position=position)
        assert signal.action == "HOLD"

    def test_hold_when_price_above_ema(self, strategy):
        """HOLD when price is above EMA — trend intact."""
        df = make_candles(200, trend="up")
        from utils.indicators import compute_all
        df = compute_all(df, 21, 50, 14, 14)

        ema_val = float(df["ema_fast"].iloc[-1])
        df.iloc[-1, df.columns.get_loc("close")] = ema_val + 5.0

        position = make_position("BUY", entry=ema_val)
        signal   = strategy.generate_signal(df, current_position=position)
        assert signal.action == "HOLD"


# ── Trailing Stop Tests ───────────────────────────────────────────────────────

class TestTrailingStop:

    def test_trailing_stop_uses_current_price(self, strategy):
        """Trailing stop = current_price × (1 - pct)."""
        df = make_candles(200, trend="up")
        from utils.indicators import compute_all
        df = compute_all(df, 21, 50, 14, 14)

        current_price = float(df["close"].iloc[-1])
        pct           = strategy.params["exit_pct_below_ema"] / 100.0
        expected_stop = round(current_price * (1.0 - pct), 5)

        position = make_position("BUY", entry=current_price - 20, stop=current_price - 50)
        new_stop = strategy.update_trailing_stop(df, position)

        assert new_stop is not None
        assert new_stop == pytest.approx(expected_stop, abs=0.001)

    def test_trailing_stop_only_moves_up_for_buy(self, strategy):
        """Trailing stop for BUY must never decrease."""
        df = make_candles(200, trend="up")
        from utils.indicators import compute_all
        df = compute_all(df, 21, 50, 14, 14)

        current_price = float(df["close"].iloc[-1])
        pct           = strategy.params["exit_pct_below_ema"] / 100.0
        high_stop     = round(current_price * (1.0 - pct) + 100, 5)

        position = make_position("BUY", entry=current_price, stop=high_stop)
        position.trailing_stop = high_stop

        new_stop = strategy.update_trailing_stop(df, position)
        assert new_stop is None  # no update — current stop already higher

    def test_trailing_stop_updates_when_price_rises(self, strategy):
        """Stop updates when price rises above previous stop level."""
        df = make_candles(200, trend="up")
        from utils.indicators import compute_all
        df = compute_all(df, 21, 50, 14, 14)

        current_price = float(df["close"].iloc[-1])
        pct           = strategy.params["exit_pct_below_ema"] / 100.0

        position = make_position("BUY", entry=current_price - 20, stop=0.01)
        position.trailing_stop = 0.01

        new_stop = strategy.update_trailing_stop(df, position)
        assert new_stop is not None
        assert new_stop == pytest.approx(current_price * (1.0 - pct), abs=0.001)
        assert new_stop > position.trailing_stop


# ── Position Model Tests ──────────────────────────────────────────────────────

class TestPosition:

    def test_unrealized_pnl_buy(self):
        pos = make_position("BUY", entry=2350.0)
        pos.current_price = 2370.0
        assert pos.unrealized_pnl == pytest.approx(0.20, rel=0.01)

    def test_stop_hit_buy(self):
        pos = make_position("BUY", entry=2350.0, stop=2330.0)
        assert pos.is_stopped_out(2329.0) is True
        assert pos.is_stopped_out(2331.0) is False

    def test_trailing_stop_only_moves_favorably(self):
        pos = make_position("BUY", entry=2350.0, stop=2330.0)
        pos.trailing_stop = 2340.0

        assert pos.update_trailing_stop(2345.0) is True
        assert pos.trailing_stop == 2345.0

        assert pos.update_trailing_stop(2335.0) is False
        assert pos.trailing_stop == 2345.0  # unchanged


# ── Signal Tests ──────────────────────────────────────────────────────────────

class TestSignal:

    def test_buy_is_entry(self):
        s = Signal("BUY", stop_loss=2330.0, reason="test")
        assert s.is_entry() and not s.is_exit() and not s.is_hold()

    def test_close_is_exit(self):
        s = Signal("CLOSE", reason="test")
        assert s.is_exit() and not s.is_entry()

    def test_hold(self):
        s = Signal("HOLD", reason="no signal")
        assert s.is_hold()

    def test_signal_always_has_reason(self):
        df = make_candles(200, trend="up")
        strategy = EmaTrendStrategy()
        signal = strategy.generate_signal(df)
        assert len(signal.reason) > 0


# ── Short Selling Tests ───────────────────────────────────────────────────────

class TestShort:

    def test_no_sell_when_allow_short_false(self, strategy):
        """Never SELL when allow_short=False."""
        df = make_candles(200, trend="down")
        signal = strategy.generate_signal(df, current_position=None)
        assert signal.action != "SELL"

    def test_sell_when_ema_between_open_close_downtrend(self, strategy_short):
        """SELL when EMA between open/close, close < EMA, downtrend."""
        df = make_candles(200, trend="down")
        from utils.indicators import compute_all
        df = compute_all(df, 21, 50, 14, 14)

        ema_val = float(df["ema_fast"].iloc[-1])

        # Ensure downtrend: ema_fast < ema_slow
        df.iloc[-1, df.columns.get_loc("ema_slow")] = ema_val + 10.0

        # open above EMA, close below EMA → EMA between them, close < EMA
        df.iloc[-1, df.columns.get_loc("open")]  = ema_val + 2.0
        df.iloc[-1, df.columns.get_loc("close")] = ema_val - 2.0

        signal = strategy_short.generate_signal(df, current_position=None)
        assert signal.action == "SELL", f"Expected SELL, got {signal.action}: {signal.reason}"

    def test_sell_signal_has_stop_loss(self, strategy_short):
        """SELL signal must include a stop loss."""
        df = make_candles(200, trend="down")
        from utils.indicators import compute_all
        df = compute_all(df, 21, 50, 14, 14)

        ema_val = float(df["ema_fast"].iloc[-1])
        df.iloc[-1, df.columns.get_loc("ema_slow")] = ema_val + 10.0
        df.iloc[-1, df.columns.get_loc("open")]     = ema_val + 2.0
        df.iloc[-1, df.columns.get_loc("close")]    = ema_val - 2.0

        signal = strategy_short.generate_signal(df)
        if signal.action == "SELL":
            assert signal.stop_loss is not None

    def test_close_sell_when_price_rises_above_ema(self, strategy_short):
        """CLOSE SELL when price rises X% above EMA."""
        df = make_candles(200, trend="down")
        from utils.indicators import compute_all
        df = compute_all(df, 21, 50, 14, 14)

        ema_val    = float(df["ema_fast"].iloc[-1])
        pct        = strategy_short.params["exit_pct_below_ema"] / 100.0
        exit_level = ema_val * (1.0 + pct)

        df.iloc[-1, df.columns.get_loc("close")]    = exit_level + 5.0
        df.iloc[-1, df.columns.get_loc("ema_fast")] = ema_val

        position = make_position("SELL", entry=ema_val - 10, stop=ema_val + 20)
        signal   = strategy_short.generate_signal(df, current_position=position)
        assert signal.action == "CLOSE"

    def test_trailing_stop_moves_down_for_sell(self, strategy_short):
        """Trailing stop for SELL should only move DOWN."""
        df = make_candles(200, trend="down")
        from utils.indicators import compute_all
        df = compute_all(df, 21, 50, 14, 14)

        ema_val  = float(df["ema_fast"].iloc[-1])
        position = make_position("SELL", entry=ema_val - 20, stop=ema_val + 50)
        position.trailing_stop = ema_val + 50

        new_stop = strategy_short.update_trailing_stop(df, position)
        assert new_stop is not None
        assert new_stop < position.trailing_stop
