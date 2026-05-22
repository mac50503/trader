"""
utils/indicators.py
-------------------
Technical indicators implemented with pure pandas/numpy.

No external TA library needed — these are clean, readable implementations
of the exact same formulas used by pandas-ta, TA-Lib, and TradingView.

All functions accept a pandas DataFrame with columns:
    open, high, low, close, volume
and return a pandas Series.

Why pure pandas?
- No dependency on pandas-ta (which requires numba, incompatible with Python 3.14+)
- Easier to understand and debug
- Same results as any standard TA library
- Easy to swap for pandas-ta later if needed (same API)
"""

import pandas as pd
import numpy as np
from typing import Optional

from utils.logger import get_logger

logger = get_logger(__name__)


def ema(df: pd.DataFrame, period: int, column: str = "close") -> pd.Series:
    """
    Exponential Moving Average.

    Uses pandas ewm() with adjust=False — same formula as TradingView/MT5.
    Alpha = 2 / (period + 1)

    Args:
        df: OHLCV DataFrame
        period: EMA period (e.g. 21, 50, 200)
        column: price column to use

    Returns:
        pd.Series of EMA values
    """
    return df[column].ewm(span=period, adjust=False).mean()


def sma(df: pd.DataFrame, period: int, column: str = "close") -> pd.Series:
    """Simple Moving Average."""
    return df[column].rolling(window=period).mean()


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Average True Range.

    True Range = max(high-low, |high-prev_close|, |low-prev_close|)
    ATR = EMA(True Range, period)

    Used for:
    - Stop loss sizing
    - Volatility filtering
    - Trailing stop distance

    Args:
        df: OHLCV DataFrame with high, low, close columns
        period: ATR period (default 14)

    Returns:
        pd.Series of ATR values
    """
    high  = df["high"]
    low   = df["low"]
    close = df["close"]

    prev_close = close.shift(1)

    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs(),
    ], axis=1).max(axis=1)

    # Use EMA (Wilder's smoothing = EMA with span=period)
    return tr.ewm(span=period, adjust=False).mean()


def rsi(df: pd.DataFrame, period: int = 14, column: str = "close") -> pd.Series:
    """
    Relative Strength Index (Wilder's RSI).

    RSI = 100 - (100 / (1 + RS))
    RS = avg_gain / avg_loss over period

    Args:
        df: OHLCV DataFrame
        period: RSI period (default 14)
        column: price column to use

    Returns:
        pd.Series of RSI values (0-100)
    """
    delta = df[column].diff()

    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_values = 100 - (100 / (1 + rs))

    return rsi_values


def candle_body_size(df: pd.DataFrame) -> pd.Series:
    """Absolute body size of each candle (|close - open|)."""
    return (df["close"] - df["open"]).abs()


def is_trending(
    df: pd.DataFrame,
    ema_fast_period: int,
    ema_slow_period: int,
    min_separation_atr_ratio: float = 0.1,
) -> bool:
    """
    Simple trend detection: fast EMA above slow EMA with minimum separation.

    Args:
        df: OHLCV DataFrame
        ema_fast_period: fast EMA period
        ema_slow_period: slow EMA period
        min_separation_atr_ratio: minimum EMA gap as ratio of ATR

    Returns:
        bool — True = uptrend, False = downtrend or no trend
    """
    if len(df) < ema_slow_period + 5:
        return False

    fast    = ema(df, ema_fast_period)
    slow    = ema(df, ema_slow_period)
    atr_val = atr(df)

    if fast.isna().iloc[-1] or slow.isna().iloc[-1] or atr_val.isna().iloc[-1]:
        return False

    separation = fast.iloc[-1] - slow.iloc[-1]
    min_gap    = atr_val.iloc[-1] * min_separation_atr_ratio

    return separation > min_gap


def compute_all(
    df: pd.DataFrame,
    ema_fast: int,
    ema_slow: int,
    atr_period: int,
    rsi_period: int,
) -> pd.DataFrame:
    """
    Compute all indicators at once and return enriched DataFrame.

    Adds columns: ema_fast, ema_slow, atr, rsi, body_size.
    This is the main function called by strategies before signal evaluation.

    Args:
        df: OHLCV DataFrame
        ema_fast: fast EMA period
        ema_slow: slow EMA period
        atr_period: ATR period
        rsi_period: RSI period

    Returns:
        DataFrame with indicator columns added
    """
    df = df.copy()

    df["ema_fast"]  = ema(df, ema_fast)
    df["ema_slow"]  = ema(df, ema_slow)
    df["atr"]       = atr(df, atr_period)
    df["rsi"]       = rsi(df, rsi_period)
    df["body_size"] = candle_body_size(df)

    return df
