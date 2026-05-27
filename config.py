"""
config.py
---------
Central configuration loader.
Reads from .env file and exposes typed settings to the rest of the app.
All modules import from here — never read os.environ directly elsewhere.
"""

import os
from dotenv import load_dotenv

load_dotenv()


def _get(key: str, default=None, cast=str):
    """Helper to read env var with optional type casting."""
    value = os.getenv(key, default)
    if value is None:
        return None
    try:
        return cast(value)
    except (ValueError, TypeError):
        return default


# ── Broker ────────────────────────────────────────────────────────────────────
BROKER_NAME: str       = _get("BROKER_NAME", "paper")
BROKER_API_KEY: str    = _get("BROKER_API_KEY", "")
BROKER_SECRET_KEY: str = _get("BROKER_SECRET_KEY", "")
BROKER_BASE_URL: str   = _get("BROKER_BASE_URL", "")
BROKER_MODE: str       = _get("BROKER_MODE", "demo")   # demo | live

# ── Trading ───────────────────────────────────────────────────────────────────
DEFAULT_SYMBOL: str         = _get("DEFAULT_SYMBOL", "XAUUSD")
DEFAULT_TIMEFRAME: str      = _get("DEFAULT_TIMEFRAME", "M1")
DEFAULT_RISK_PERCENT: float = _get("DEFAULT_RISK_PERCENT", 1.0, float)
DEFAULT_LOT_SIZE: float     = _get("DEFAULT_LOT_SIZE", 0.01, float)
MAX_DAILY_LOSS_PERCENT: float = _get("MAX_DAILY_LOSS_PERCENT", 3.0, float)
MAX_OPEN_POSITIONS: int     = _get("MAX_OPEN_POSITIONS", 1, int)

# ── Strategy ──────────────────────────────────────────────────────────────────
ACTIVE_STRATEGY: str           = _get("ACTIVE_STRATEGY", "EMA Pullback Pro")
EMA_FAST: int                  = _get("EMA_FAST", 21, int)
EMA_SLOW: int                  = _get("EMA_SLOW", 50, int)
ATR_PERIOD: int                = _get("ATR_PERIOD", 14, int)
ATR_MULTIPLIER: float          = _get("ATR_MULTIPLIER", 2.0, float)
MIN_CANDLE_BODY_PERCENT: float = _get("MIN_CANDLE_BODY_PERCENT", 0.3, float)
RSI_PERIOD: int                = _get("RSI_PERIOD", 14, int)
RSI_OVERBOUGHT: int            = _get("RSI_OVERBOUGHT", 70, int)
RSI_OVERSOLD: int              = _get("RSI_OVERSOLD", 30, int)

# ── Application ───────────────────────────────────────────────────────────────
LOG_LEVEL: str            = _get("LOG_LEVEL", "INFO")
DB_PATH: str              = _get("DB_PATH", "trading_bot.db")
TICK_INTERVAL_SECONDS: int = _get("TICK_INTERVAL_SECONDS", 5, int)

# ── Supported symbols ─────────────────────────────────────────────────────────
SUPPORTED_SYMBOLS = ["XAUUSD", "NAS100", "SPX500"]
SUPPORTED_TIMEFRAMES = ["15s", "30s", "M1", "M5", "M15", "H1", "H4", "D1"]
