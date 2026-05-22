"""
main.py
--------
Application entry point.

Run with:
    python main.py

This file is intentionally minimal — it just boots the app.
All logic lives in the appropriate modules.
"""

import sys
from pathlib import Path

# Ensure project root is in Python path
sys.path.insert(0, str(Path(__file__).parent))

from utils.logger import get_logger

logger = get_logger(__name__)


def main() -> None:
    logger.info("=" * 60)
    logger.info("AlgoTrader Pro — Starting up")
    logger.info("=" * 60)

    try:
        from ui.app import TradingBotApp
        app = TradingBotApp()
        app.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
