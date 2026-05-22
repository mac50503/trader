"""
market_data/market_stream.py
-----------------------------
The main bot engine loop.

Responsibilities:
- Run continuously in a background thread
- Poll broker for new candles at each tick
- Detect candle closes
- Call strategy for signals
- Execute trades via broker
- Apply trailing stops
- Enforce risk rules
- Emit events to the UI via callback

Architecture:
    UI Thread  ←──callbacks──  BotEngine Thread
                                    │
                                    ├── CandleBuilder
                                    ├── Strategy
                                    ├── RiskManager
                                    └── Broker

The UI never calls broker or strategy directly.
The bot engine never touches Tkinter widgets directly.
Communication is via thread-safe callbacks and a shared state dict.
"""

import threading
import time
from datetime import datetime
from typing import Callable, Optional, Dict, Any

import pandas as pd

from brokers.base_broker import BaseBroker
from strategies.base_strategy import BaseStrategy, Signal
from risk_management.risk_manager import RiskManager
from market_data.candle_builder import CandleBuilder
from database.trade_repository import TradeRepository
from models.trade import Trade
from models.position import Position
from utils.logger import get_logger
import config

logger = get_logger(__name__)


class BotState:
    """Thread-safe snapshot of bot state for UI display."""
    STOPPED  = "STOPPED"
    RUNNING  = "RUNNING"
    PAUSED   = "PAUSED"
    ERROR    = "ERROR"


class BotEngine:
    """
    Core trading bot engine.

    Runs in a dedicated background thread.
    Communicates with UI via on_event callback.
    """

    def __init__(
        self,
        broker: BaseBroker,
        strategy: BaseStrategy,
        risk_manager: RiskManager,
        trade_repo: TradeRepository,
        symbol: str,
        timeframe: str,
        on_event: Optional[Callable[[str, dict], None]] = None,
    ):
        self.broker = broker
        self.strategy = strategy
        self.risk_manager = risk_manager
        self.trade_repo = trade_repo
        self.symbol = symbol
        self.timeframe = timeframe
        self.on_event = on_event or (lambda event, data: None)
        self.tick_interval = config.TICK_INTERVAL_SECONDS  # updatable from UI

        self.candle_builder = CandleBuilder(symbol, timeframe)

        # State
        self._state = BotState.STOPPED
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()   # Not paused by default

        # Active trade tracking
        self._open_trade: Optional[Trade] = None
        self._open_position: Optional[Position] = None

        # Stats
        self._tick_count = 0
        self._last_signal: Optional[Signal] = None

        # Last computed indicators — updated every tick for live display
        self._last_indicators: dict = {}

    # ── Public Controls ───────────────────────────────────────────────────────

    def start(self) -> bool:
        """Start the bot in a background thread."""
        if self._state == BotState.RUNNING:
            logger.warning("Bot already running")
            return False

        if not self.broker.is_connected:
            if not self.broker.connect():
                self._emit("error", {"message": "Failed to connect to broker"})
                return False

        self._stop_event.clear()
        self._pause_event.set()
        self._state = BotState.RUNNING

        self._thread = threading.Thread(
            target=self._run_loop,
            name="BotEngine",
            daemon=True,
        )
        self._thread.start()

        logger.info(f"Bot started: {self.symbol} {self.timeframe}")
        self._emit("started", {"symbol": self.symbol, "timeframe": self.timeframe})
        return True

    def stop(self) -> None:
        """Stop the bot gracefully."""
        logger.info("Bot stop requested...")
        self._stop_event.set()
        self._pause_event.set()   # Unblock if paused
        self._state = BotState.STOPPED
        self._emit("stopped", {})

    def pause(self) -> None:
        """Pause the bot (keeps thread alive but skips trading)."""
        self._pause_event.clear()
        self._state = BotState.PAUSED
        logger.info("Bot paused")
        self._emit("paused", {})

    def resume(self) -> None:
        """Resume from pause."""
        self._pause_event.set()
        self._state = BotState.RUNNING
        logger.info("Bot resumed")
        self._emit("resumed", {})

    def restart(self) -> None:
        """Stop and restart the bot."""
        self.stop()
        time.sleep(1)
        self.start()

    # ── Manual Trading ────────────────────────────────────────────────────────

    def manual_buy(self, lot_size: float) -> Optional[Trade]:
        """Open a manual BUY position."""
        return self._execute_entry("BUY", lot_size, manual=True)

    def manual_sell(self, lot_size: float) -> Optional[Trade]:
        """Open a manual SELL position."""
        return self._execute_entry("SELL", lot_size, manual=True)

    def manual_close(self) -> bool:
        """Manually close the current open position."""
        if self._open_trade:
            return self._execute_exit("Manual close by user")
        return False

    # ── Main Loop ─────────────────────────────────────────────────────────────

    def _run_loop(self) -> None:
        """
        Main bot loop — runs until stop_event is set.

        Each iteration:
        1. Wait for pause to be lifted
        2. Fetch latest candles from broker
        3. Check if new candle closed
        4. Update trailing stop on open position
        5. Check if stop was hit
        6. Generate strategy signal
        7. Execute signal
        8. Sleep until next tick
        """
        logger.info(f"[{self.symbol}] Bot loop started")

        # Initial data load
        try:
            self._load_initial_data()
            logger.info(f"[{self.symbol}] Initial data loaded successfully")
        except Exception as e:
            logger.error(f"[{self.symbol}] Failed to load initial data: {e}", exc_info=True)
            self._state = BotState.ERROR
            self._emit("error", {"message": str(e)})
            return

        logger.info(f"[{self.symbol}] Entering main loop")
        while not self._stop_event.is_set():
            # Block here if paused
            if not self._pause_event.is_set():
                self._pause_event.wait()

            if self._stop_event.is_set():
                break

            try:
                self._tick()
            except Exception as e:
                logger.error(f"[{self.symbol}] Error in bot tick: {e}", exc_info=True)
                self._emit("error", {"message": str(e)})

            # Sleep between ticks
            self._stop_event.wait(timeout=self.tick_interval)

        logger.info(f"[{self.symbol}] Bot loop ended")

    def _load_initial_data(self) -> None:
        """Load historical candles on startup."""
        logger.info(f"[{self.symbol}] Loading initial candles: {self.symbol} {self.timeframe}")
        df = self.broker.get_candles(self.symbol, self.timeframe, count=200)
        self.candle_builder.load_from_broker(df)
        self._emit("data_loaded", {"candles": len(df)})

    def _tick(self) -> None:
        """Single bot tick — the core logic."""
        self._tick_count += 1

        # 1. Fetch fresh candles (full buffer — broker returns cached + new ones)
        broker_df = self.broker.get_candles(self.symbol, self.timeframe, count=200)
        if broker_df.empty:
            logger.debug(f"[{self.symbol}] Tick {self._tick_count}: No candles from broker")
            return

        # 2. Get current price
        current_price = self.broker.get_current_price(self.symbol)

        # 3. Compute indicators on every tick using current price as live close
        self._compute_live_indicators(broker_df, current_price)

        # 4. Update trailing stop on every tick based on current price
        #    The stop follows the price up (BUY) or down (SELL) in real time
        if self._open_position and self._open_trade:
            self._update_trailing_stop_tick(current_price)

        # 5. Update UI with current price + live indicators
        self._emit_state_update(current_price)

        # 6. Check if open position was stopped out
        if self._open_position and self._open_trade:
            if self.risk_manager.check_stop_hit(self._open_position, current_price):
                self._execute_exit(f"Stop loss hit @ {current_price:.5f}")
                return

        # 7. Check for new closed candle
        new_candle = self.candle_builder.is_new_candle_closed(broker_df)

        if new_candle:
            logger.info(f"[{self.symbol}] New candle closed")
            # Update candle buffer
            self.candle_builder.load_from_broker(broker_df)
            df = self.candle_builder.df

            if df is None or not self.candle_builder.is_ready:
                logger.debug(
                    f"[{self.symbol}] Candle buffer not ready yet "
                    f"({len(df) if df is not None else 0}/60 candles)"
                )
                return

            # 8. Generate signal on candle close
            signal = self.strategy.generate_signal(df, self._open_position)
            self._last_signal = signal

            logger.info(f"[{self.symbol}] Signal: {signal}")
            self._emit("signal", {"signal": str(signal), "symbol": self.symbol})

            # 9. Execute signal
            if signal.is_entry() and self._open_trade is None:
                self._handle_entry_signal(signal, df)

            elif signal.is_exit() and self._open_trade is not None:
                self._execute_exit(signal.reason)

    def _update_trailing_stop_tick(self, current_price: float) -> None:
        """
        Update trailing stop on every tick based on current price.

        stop = current_price × (1 - pct)  for BUY
        stop = current_price × (1 + pct)  for SELL

        Only moves in the favorable direction.
        Saves to DB only when the stop actually changes.
        """
        pct = self.strategy.params.get("exit_pct_below_ema", 0.3) / 100.0

        if self._open_position.direction == "BUY":
            new_stop = round(current_price * (1.0 - pct), 5)
        else:
            new_stop = round(current_price * (1.0 + pct), 5)

        updated = self.risk_manager.apply_trailing_stop(
            self._open_position, new_stop, self.broker, self._open_trade
        )
        if updated:
            self.trade_repo.update_trade(self._open_trade)
            self.trade_repo.log_event(
                "INFO", "TRADE",
                f"Trailing stop → {new_stop:.5f} (price={current_price:.5f})",
                self.symbol,
            )

    def _compute_live_indicators(self, broker_df: pd.DataFrame, current_price: float) -> None:
        """
        Compute indicators every tick using current price as the live close.

        We inject the current price as the close of the last (forming) candle,
        then run the indicators. This gives a live preview of where EMA/ATR/RSI
        are heading before the candle officially closes.

        Results are stored in self._last_indicators for the UI.
        """
        df = self.candle_builder.df
        if df is None or len(df) < 10:
            return

        try:
            # Clone last row with current price as close
            live_df = df.copy()
            live_df.iloc[-1, live_df.columns.get_loc("close")] = current_price

            from utils.indicators import compute_all
            params = self.strategy.params
            enriched = compute_all(
                live_df,
                ema_fast=params["ema_fast"],
                ema_slow=params["ema_slow"],
                atr_period=params["atr_period"],
                rsi_period=params["rsi_period"],
            )

            last = enriched.iloc[-1]

            def safe(col, decimals):
                val = last.get(col)
                if val is None or pd.isna(val):
                    return None
                return round(float(val), decimals)

            self._last_indicators = {
                "ema_fast": safe("ema_fast", 5),
                "ema_slow": safe("ema_slow", 5),
                "atr":      safe("atr",      5),
                "rsi":      safe("rsi",      2),
            }
        except Exception as e:
            logger.debug(f"Live indicator compute error: {e}")

    # ── Trade Execution ───────────────────────────────────────────────────────

    def _handle_entry_signal(self, signal: Signal, df) -> None:
        """Validate risk rules and open a new position."""
        balance = self.broker.get_account_balance()
        open_positions = self.broker.get_open_positions()

        allowed, reason = self.risk_manager.can_open_trade(
            self.symbol, balance, open_positions
        )

        if not allowed:
            logger.info(f"[{self.symbol}] Trade blocked by risk manager: {reason}")
            self._emit("risk_block", {"reason": reason})
            return

        # Calculate position size
        lot_size = self.risk_manager.calculate_position_size(
            balance=balance,
            stop_loss_price=signal.stop_loss,
            entry_price=df["close"].iloc[-1],
            symbol=self.symbol,
        )

        self._execute_entry(signal.action, lot_size, stop_loss=signal.stop_loss)

    def _execute_entry(
        self,
        direction: str,
        lot_size: float,
        stop_loss: Optional[float] = None,
        manual: bool = False,
    ) -> Optional[Trade]:
        """Place order and track the new position."""
        trade = self.broker.place_market_order(
            symbol=self.symbol,
            direction=direction,
            lot_size=lot_size,
            stop_loss=stop_loss,
            comment="manual" if manual else "auto",
        )

        if trade is None:
            logger.error(f"[{self.symbol}] Order placement failed")
            return None

        # Save to DB
        self.trade_repo.save_trade(trade)
        self.trade_repo.log_event(
            "INFO", "TRADE",
            f"OPEN {direction} {lot_size} {self.symbol} @ {trade.entry_price} SL={stop_loss}",
            self.symbol,
        )

        # Track in memory
        self._open_trade = trade
        self._open_position = Position(
            symbol=self.symbol,
            direction=direction,
            entry_price=trade.entry_price,
            lot_size=lot_size,
            entry_time=trade.entry_time,
            stop_loss=stop_loss or 0.0,
            trade_id=trade.id,
        )

        self._emit("trade_opened", {
            "trade_id": trade.id,
            "symbol": self.symbol,
            "direction": direction,
            "price": trade.entry_price,
            "lot_size": lot_size,
            "stop_loss": stop_loss,
            "manual": manual,
        })

        return trade

    def _execute_exit(self, reason: str = "") -> bool:
        """Close the current open position."""
        if not self._open_trade:
            return False

        success = self.broker.close_position(self._open_trade)

        if success:
            self.trade_repo.update_trade(self._open_trade)
            self.trade_repo.log_event(
                "INFO", "TRADE",
                f"CLOSE {self._open_trade.symbol} @ {self._open_trade.exit_price} "
                f"PnL={self._open_trade.pnl:+.2f} | {reason}",
                self.symbol,
            )

            self._emit("trade_closed", {
                "trade_id": self._open_trade.id,
                "symbol": self.symbol,
                "exit_price": self._open_trade.exit_price,
                "pnl": self._open_trade.pnl,
                "reason": reason,
            })

            self._open_trade = None
            self._open_position = None

        return success

    # ── Event Emission ────────────────────────────────────────────────────────

    def _emit(self, event: str, data: dict) -> None:
        """Send event to UI callback (thread-safe)."""
        try:
            self.on_event(event, data)
        except Exception as e:
            logger.error(f"Error in event callback: {e}")

    def _emit_state_update(self, current_price: float) -> None:
        """Emit periodic state update for UI dashboard."""
        balance = self.broker.get_account_balance()
        equity  = self.broker.get_account_equity()

        self._emit("state_update", {
            "symbol":         self.symbol,
            "price":          current_price,
            "balance":        balance,
            "equity":         equity,
            "state":          self._state,
            "open_trade":     self._open_trade.id if self._open_trade else None,
            "unrealized_pnl": (
                self._open_position.unrealized_pnl if self._open_position else 0.0
            ),
            "tick":           self._tick_count,
            "indicators":     self._last_indicators,
            "trailing_stop":  (
                self._open_position.effective_stop if self._open_position else None
            ),
        })

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def state(self) -> str:
        return self._state

    @property
    def is_running(self) -> bool:
        return self._state == BotState.RUNNING
