"""
strategies/strategy_registry.py
-------------------------------
Registry of available trading strategies.
Allows dynamic selection and loading of strategies at runtime.
"""

from typing import Dict, Type, Optional
from strategies.base_strategy import BaseStrategy
from strategies.ema_trend_strategy import EmaTrendStrategy
from utils.logger import get_logger

logger = get_logger(__name__)


class StrategyRegistry:
    """
    Central registry for all available trading strategies.
    Supports dynamic strategy selection and instantiation.
    """

    _strategies: Dict[str, Type[BaseStrategy]] = {
        "EMA Pullback Pro": EmaTrendStrategy,
    }

    @classmethod
    def register(cls, name: str, strategy_class: Type[BaseStrategy]) -> None:
        """
        Register a new strategy.

        Args:
            name: Human-readable strategy name
            strategy_class: Strategy class (must inherit from BaseStrategy)
        """
        if not issubclass(strategy_class, BaseStrategy):
            raise TypeError(f"{strategy_class} must inherit from BaseStrategy")
        cls._strategies[name] = strategy_class
        logger.info(f"Strategy registered: {name}")

    @classmethod
    def get_strategy(cls, name: str, params: Optional[dict] = None) -> BaseStrategy:
        """
        Get an instance of a strategy by name.

        Args:
            name: Strategy name (must be registered)
            params: Optional parameters to override defaults

        Returns:
            Instantiated strategy object

        Raises:
            ValueError: If strategy name not found
        """
        if name not in cls._strategies:
            available = ", ".join(cls._strategies.keys())
            raise ValueError(
                f"Strategy '{name}' not found. Available: {available}"
            )
        strategy_class = cls._strategies[name]
        return strategy_class(params)

    @classmethod
    def list_strategies(cls) -> list[str]:
        """
        Get list of all available strategy names.

        Returns:
            List of strategy names
        """
        return list(cls._strategies.keys())

    @classmethod
    def get_default_strategy(cls) -> str:
        """
        Get the default strategy name (first registered).

        Returns:
            Default strategy name
        """
        return list(cls._strategies.keys())[0] if cls._strategies else None
