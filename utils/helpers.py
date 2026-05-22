"""
utils/helpers.py
----------------
General-purpose utility functions used across the project.
"""

from datetime import datetime, timezone
from typing import Optional
import math

from utils.logger import get_logger
logger = get_logger(__name__)


def utc_now() -> datetime:
    """Returns current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


def round_price(price: float, digits: int = 5) -> float:
    """Round a price to the given number of decimal places."""
    return round(price, digits)


def pips_to_price(pips: float, symbol: str) -> float:
    """
    Convert pips to price units depending on symbol.
    Gold (XAUUSD): 1 pip = 0.01
    Indices (NAS100, SPX500): 1 pip = 1 point
    Forex: 1 pip = 0.0001
    """
    symbol = symbol.upper()
    if symbol == "XAUUSD":
        return pips * 0.01
    elif symbol in ("NAS100", "SPX500"):
        return pips * 1.0
    else:
        return pips * 0.0001


def calculate_lot_size(
    capital: float,
    risk_percent: float,
    stop_loss_pips: float,
    symbol: str,
    pip_value: float = 1.0,
) -> float:
    """
    Calculate position size based on fixed fractional risk.

    Formula: lot_size = (capital * risk%) / (stop_loss_pips * pip_value)

    Args:
        capital: account balance
        risk_percent: risk as percentage (e.g. 1.0 = 1%)
        stop_loss_pips: distance to stop in pips
        symbol: trading symbol (affects pip value)
        pip_value: value per pip per lot (default 1.0 for simplicity)

    Returns:
        float: calculated lot size, minimum 0.01
    """
    if stop_loss_pips <= 0:
        return 0.01

    risk_amount = capital * (risk_percent / 100.0)
    lot_size = risk_amount / (stop_loss_pips * pip_value)

    # Clamp to reasonable range
    lot_size = max(0.01, min(lot_size, 100.0))
    return round(lot_size, 2)


def format_pnl(pnl: float) -> str:
    """Format PnL for display with color indicator."""
    sign = "+" if pnl >= 0 else ""
    return f"{sign}{pnl:.2f}"


def timeframe_to_seconds(timeframe: str) -> int:
    """Convert timeframe string to seconds."""
    mapping = {
        "15S": 15,
        "30S": 30,
        "M1":  60,
        "M5":  300,
        "M15": 900,
        "M30": 1800,
        "H1":  3600,
        "H4":  14400,
        "D1":  86400,
    }
    result = mapping.get(timeframe.upper(), None)
    if result is None:
        logger.warning(f"Unknown timeframe '{timeframe}', defaulting to H1 (3600s)")
        return 3600
    return result


def is_market_hours(symbol: str, dt: Optional[datetime] = None) -> bool:
    """
    Basic market hours check.
    Gold and indices have specific trading hours.
    For paper trading this always returns True.
    """
    # Simplified: always return True for now
    # In production, implement proper market calendar
    return True
