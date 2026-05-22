# AlgoTrader Pro — Project Overview

## Stack
- Python 3.14
- Tkinter (UI)
- SQLite (database)
- pandas / numpy (data)
- No matplotlib — chart uses native Tkinter Canvas

## Project Structure
```
trader/
├── main.py                  # Entry point
├── config.py                # All config, reads from .env
├── ui/
│   ├── app.py               # Main window, wires everything together
│   ├── dashboard.py         # Trade history panel
│   ├── chart_panel.py       # Live candlestick chart (Tkinter Canvas)
│   ├── logs_window.py       # Logs panel
│   └── settings_window.py   # Strategy/risk settings
├── strategies/
│   ├── base_strategy.py     # Abstract base, Signal dataclass
│   └── ema_trend_strategy.py # EMA pullback strategy
├── brokers/
│   ├── base_broker.py       # Abstract base
│   ├── paper_broker.py      # Paper trading simulation
│   └── future_broker.py     # Factory function create_broker()
├── market_data/
│   ├── candle_builder.py    # Maintains rolling candle DataFrame
│   └── market_stream.py     # BotEngine — main loop, threading
├── risk_management/
│   └── risk_manager.py      # Position sizing, stop checks
├── database/
│   ├── database.py          # SQLite connection
│   └── trade_repository.py  # CRUD for trades and events
├── models/
│   ├── trade.py             # Trade dataclass
│   ├── position.py          # Position dataclass
│   └── candle.py            # Candle dataclass
├── utils/
│   ├── indicators.py        # compute_all() — EMA, ATR, RSI
│   ├── helpers.py           # timeframe_to_seconds(), utc_now()
│   └── logger.py            # get_logger()
└── tests/
    └── test_strategy.py     # 24 unit tests
```

## Threading Model
- **Main thread**: Tkinter UI
- **Background thread**: BotEngine loop
- Communication: `on_event(event, data)` callback → `root.after(0, handler)` in UI
- NEVER touch Tkinter widgets from background thread

## Key Config Values (config.py)
- `EMA_FAST = 21`, `EMA_SLOW = 50`
- `TICK_INTERVAL_SECONDS = 5`
- `DEFAULT_SYMBOL = "XAUUSD"`, `DEFAULT_TIMEFRAME = "M1"`
- `SUPPORTED_TIMEFRAMES = ["15s", "30s", "M1", "M5", "M15", "H1", "H4", "D1"]`
- `timeframe_to_seconds()` in helpers.py handles all timeframes including "15s", "30s"

## Tkinter Rules
- When adding a new Frame/Panel to a Notebook tab, ALWAYS call `.pack(fill=tk.BOTH, expand=True)` after instantiation
- Canvas widgets inside Notebook tabs have size 1x1 until the tab is shown
- Use `canvas.update_idletasks()` + retry pattern if canvas size is 1x1
