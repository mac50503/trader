# Development Rules

## Before Making Any Change
1. READ the relevant file(s) first — never assume what's in them
2. Understand the full context before touching anything
3. If changing strategy logic, explain the change to the user BEFORE implementing
4. Never modify the trading strategy without explicit user approval

## Code Style
- Match existing patterns — don't introduce new libraries or frameworks
- Use `get_logger(__name__)` for all logging
- All prices rounded to 5 decimals: `round(price, 5)`
- All log messages about signals MUST include: open, close, EMA values
- Use `logger.info()` for important events, `logger.debug()` for verbose

## After Every Change
1. Run `python -m pytest tests/test_strategy.py -v` to verify tests pass
2. If tests fail, fix them before presenting the result
3. If changing strategy logic, update tests to match new behavior
4. Restart the app to verify no import errors

## What NOT to Do
- Never use `np.random.seed(42)` in paper_broker — causes fixed/repeated prices
- Never call Tkinter widgets from background thread — use `root.after(0, handler)`
- Never add `.pack()` inside a class `__init__` for panels added to Notebook tabs
  (the caller in app.py must call `.pack(fill=tk.BOTH, expand=True)`)
- Never change strategy entry/exit logic without user confirmation
- Never add Docker, SQLAlchemy, Alembic, or complex frameworks

## Common Bugs to Watch For
- `name 'X' is not defined` in strategy → check all variables are extracted from `last` row
- Canvas size 1x1 → panel not packed with `.pack(fill=tk.BOTH, expand=True)` in app.py
- Timeframe not generating signals → check `timeframe_to_seconds()` in helpers.py has the mapping
- Fixed candle prices → `np.random.seed()` called with fixed value in paper_broker
- Bot not ticking → `_pause_event` not set, or tick_interval too large

## Paper Broker Behavior
- Generates synthetic OHLCV data using random walk
- `_build_candle_rows(start_price, volatility, count)` generates `count` NEW candles
  starting FROM start_price (not including it)
- New candles appear based on real wall-clock time elapsed
- `volatility = base_price * 0.0015` per candle
