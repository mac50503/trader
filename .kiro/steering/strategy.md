# Trading Strategy — EMA Pullback

## Philosophy
- Small losses, let big trends run
- EMA is not just an indicator — it IS the trade (dynamic support/resistance)
- Trailing stop follows price to capture the full wave

## Entry Logic (EMA Touch + Bounce)

### BUY
1. `EMA_fast > EMA_slow` → uptrend confirmed
2. EMA_fast is between `open` and `close` of the candle → price crossed EMA during candle
3. `close > EMA_fast` → candle closed above EMA (bounce confirmed)

### SELL (only if allow_short=True)
1. `EMA_fast < EMA_slow` → downtrend confirmed
2. EMA_fast is between `open` and `close` of the candle
3. `close < EMA_fast` → candle closed below EMA (bounce down confirmed)

### One position at a time
- If a BUY or SELL is open, NO new entries until it closes
- Code: `if signal.is_entry() and self._open_trade is None`

## Exit Logic
- BUY exits when: `close < EMA_fast * (1 - exit_pct/100)`
- SELL exits when: `close > EMA_fast * (1 + exit_pct/100)`
- `exit_pct_below_ema` default = 0.3% (configurable from UI)

## Trailing Stop
- Calculated on EVERY tick (not just candle close)
- BUY: `stop = current_price * (1 - pct)` — only moves UP
- SELL: `stop = current_price * (1 + pct)` — only moves DOWN
- Stop NEVER moves against the position

## Example (BUY)
```
price=2300 → stop = 2300 * 0.997 = 2293.10  (entry)
price=2320 → stop = 2320 * 0.997 = 2313.04  (moves up)
price=2350 → stop = 2350 * 0.997 = 2342.95  (moves up)
price drops to 2342.95 → stop hit → close with profit
```

## Log Messages (what they mean)
- `EMA touch+bounce: EMA=X between open=Y and close=Z` → BUY entry
- `EMA touch+bounce DOWN: EMA=X between open=Y and close=Z` → SELL entry
- `No EMA touch: open=X, close=Y, EMA=Z` → EMA not between open/close
- `No uptrend: open=X, close=Y, EMA_fast=A <= EMA_slow=B` → no uptrend
- `No downtrend: open=X, close=Y, EMA_fast=A >= EMA_slow=B` → no downtrend
- `No SELL touch: open=X, close=Y, EMA=Z` → downtrend but no touch
- `Position intact: open=X, close=Y, EMA=Z` → position open, no exit yet
- `BUY exit: open=X, close=Y, EMA=Z < exit_level=W` → closing BUY
- `SELL exit: open=X, close=Y, EMA=Z > exit_level=W` → closing SELL
- `Stop hit: XAUUSD BUY price=X stop=Y` → trailing stop triggered

## Indicators (computed in utils/indicators.py via compute_all())
- `ema_fast` — EMA with period `ema_fast` (default 21)
- `ema_slow` — EMA with period `ema_slow` (default 50)
- `atr` — Average True Range, period 14
- `rsi` — RSI, period 14 (optional filter)
- `body_size` — abs(close - open)
