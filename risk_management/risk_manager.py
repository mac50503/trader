"""
risk_management/risk_manager.py
--------------------------------
Enforces all risk rules before any trade is executed.

Responsibilities:
- Calculate position size based on risk %
- Check daily loss limits
- Check max open positions
- Validate stop loss distance
- Monitor trailing stops
- Trigger emergency stop if limits breached

The bot engine asks the risk manager for approval before every trade.
"""

from datetime import datetime
from typing import Optional, Tuple

from models.position import Position
from models.trade import Trade
from database.trade_repository import TradeRepository
from utils.logger import get_logger
from utils.helpers import calculate_lot_size, pips_to_price
import config

logger = get_logger(__name__)


class RiskManager:
    """
    Central risk control system.

    All risk parameters are configurable and can be updated from the UI.
    """

    def __init__(
        self,
        trade_repo: TradeRepository,
        risk_percent: float = None,
        max_daily_loss_pct: float = None,
        max_open_positions: int = None,
        atr_multiplier: float = None,
    ):
        self.trade_repo = trade_repo
        self.risk_percent = risk_percent or config.DEFAULT_RISK_PERCENT
        self.max_daily_loss_pct = max_daily_loss_pct or config.MAX_DAILY_LOSS_PERCENT
        self.max_open_positions = max_open_positions or config.MAX_OPEN_POSITIONS
        self.atr_multiplier = atr_multiplier or config.ATR_MULTIPLIER

        self._daily_loss_triggered = False
        self._emergency_stop = False

    # ── Pre-trade Checks ──────────────────────────────────────────────────────

    def can_open_trade(
        self,
        symbol: str,
        balance: float,
        open_positions: list,
    ) -> Tuple[bool, str]:
        """
        Check all risk rules before opening a new trade.

        Returns:
            (allowed: bool, reason: str)
        """
        if self._emergency_stop:
            return False, "Emergency stop is active"

        if self._daily_loss_triggered:
            return False, "Daily loss limit reached — trading halted for today"

        # Max positions check
        if len(open_positions) >= self.max_open_positions:
            return False, f"Max open positions reached ({self.max_open_positions})"

        # Daily loss check
        today = datetime.utcnow().strftime("%Y-%m-%d")
        daily_pnl = self.trade_repo.get_daily_pnl(today)
        max_loss = balance * (self.max_daily_loss_pct / 100.0)

        if daily_pnl <= -max_loss:
            self._daily_loss_triggered = True
            logger.warning(
                f"Daily loss limit hit: PnL={daily_pnl:.2f}, limit={-max_loss:.2f}"
            )
            return False, f"Daily loss limit hit: {daily_pnl:.2f}"

        return True, "OK"

    def calculate_position_size(
        self,
        balance: float,
        stop_loss_price: float,
        entry_price: float,
        symbol: str,
    ) -> float:
        """
        Calculate lot size using fixed fractional risk.

        Risk amount = balance * risk_percent / 100
        Lot size = risk_amount / stop_distance_in_price_units
        """
        stop_distance = abs(entry_price - stop_loss_price)

        if stop_distance <= 0:
            logger.warning("Stop distance is zero, using minimum lot size")
            return 0.01

        risk_amount = balance * (self.risk_percent / 100.0)
        lot_size = risk_amount / stop_distance

        # Clamp to reasonable range
        lot_size = max(0.01, min(lot_size, 10.0))
        lot_size = round(lot_size, 2)

        logger.debug(
            f"Position size: balance={balance:.2f}, risk={self.risk_percent}%, "
            f"stop_dist={stop_distance:.5f}, lot={lot_size}"
        )
        return lot_size

    # ── Trailing Stop Management ──────────────────────────────────────────────

    def check_stop_hit(self, position: Position, current_price: float) -> bool:
        """
        Check if current price has hit the position's stop.
        Returns True if stop was hit (position should be closed).
        """
        position.current_price = current_price

        if position.is_stopped_out(current_price):
            logger.info(
                f"Stop hit: {position.symbol} {position.direction} "
                f"price={current_price} stop={position.effective_stop}"
            )
            return True
        return False

    def apply_trailing_stop(
        self,
        position: Position,
        new_stop: Optional[float],
        broker,
        trade: Trade,
    ) -> bool:
        """
        Apply a new trailing stop to a position if it improves the stop.

        Returns True if stop was updated.
        """
        if new_stop is None:
            return False

        updated = position.update_trailing_stop(new_stop)
        if updated:
            broker.modify_stop_loss(trade, new_stop)
            trade.trailing_stop = new_stop
            logger.info(
                f"Trailing stop updated: {position.symbol} "
                f"new_stop={new_stop:.5f}"
            )
            return True
        return False

    # ── Emergency Controls ────────────────────────────────────────────────────

    def trigger_emergency_stop(self, reason: str = "") -> None:
        """Halt all trading immediately."""
        self._emergency_stop = True
        logger.critical(f"EMERGENCY STOP triggered: {reason}")

    def reset_emergency_stop(self) -> None:
        """Re-enable trading after emergency stop."""
        self._emergency_stop = False
        logger.info("Emergency stop reset — trading re-enabled")

    def reset_daily_loss_flag(self) -> None:
        """Reset daily loss flag (call at start of new trading day)."""
        self._daily_loss_triggered = False
        logger.info("Daily loss flag reset for new trading day")

    @property
    def is_trading_allowed(self) -> bool:
        return not self._emergency_stop and not self._daily_loss_triggered

    def update_params(self, **kwargs) -> None:
        """Update risk parameters from UI."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
                logger.info(f"Risk param updated: {key}={value}")
