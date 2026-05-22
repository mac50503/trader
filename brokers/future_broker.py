"""
brokers/future_broker.py
-------------------------
Placeholder for a real broker integration (e.g., Alpaca, OANDA, IBKR).

To add a real broker:
1. Copy this file and rename it (e.g., alpaca_broker.py)
2. Implement all abstract methods from BaseBroker
3. Add the broker to the factory in this file
4. Update config.py with the broker name

This file also contains the broker factory function used by the app.
"""

from typing import Optional
from brokers.base_broker import BaseBroker
from brokers.paper_broker import PaperBroker
from utils.logger import get_logger
import config

logger = get_logger(__name__)


class FutureBroker(BaseBroker):
    """
    Stub for a future real broker integration.
    Replace the pass statements with actual API calls.

    Example brokers to implement:
    - Alpaca (stocks/crypto, free paper trading API)
    - OANDA (forex/gold, REST + streaming API)
    - Interactive Brokers (TWS API)
    - MetaTrader 5 (via MetaTrader5 Python package)
    """

    def connect(self) -> bool:
        # TODO: implement real connection
        logger.warning("FutureBroker.connect() not implemented — use PaperBroker")
        return False

    def disconnect(self) -> None:
        pass

    def get_account_balance(self) -> float:
        return 0.0

    def get_account_equity(self) -> float:
        return 0.0

    def get_candles(self, symbol, timeframe, count=200):
        import pandas as pd
        return pd.DataFrame()

    def get_current_price(self, symbol: str) -> float:
        return 0.0

    def place_market_order(self, symbol, direction, lot_size, stop_loss=None, take_profit=None, comment=""):
        return None

    def close_position(self, trade, price=None) -> bool:
        return False

    def modify_stop_loss(self, trade, new_stop: float) -> bool:
        return False

    def get_open_positions(self):
        return []


# ── Broker Factory ────────────────────────────────────────────────────────────

def create_broker(
    broker_name: Optional[str] = None,
    initial_balance: float = 10_000.0,
) -> BaseBroker:
    """
    Factory function — returns the correct broker based on config.

    Args:
        broker_name: override config BROKER_NAME
        initial_balance: starting balance for paper broker

    Returns:
        BaseBroker instance ready to use
    """
    name = (broker_name or config.BROKER_NAME).lower()

    if name == "paper":
        broker = PaperBroker(
            initial_balance=initial_balance,
            mode="demo",
        )
    else:
        # Future: add elif for alpaca, oanda, etc.
        logger.warning(f"Unknown broker '{name}', falling back to PaperBroker")
        broker = PaperBroker(initial_balance=initial_balance, mode="demo")

    logger.info(f"Broker created: {broker}")
    return broker
