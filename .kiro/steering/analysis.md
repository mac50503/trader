# How to Analyze Changes and Debug

## When the User Reports a Problem

### Step 1 — Read the logs first
- Check `logs/trading_bot.log` for errors
- Look for the LAST relevant log entry before the problem
- Key patterns to look for:
  - `ERROR` → exception, read the traceback
  - `Signal(HOLD | ...)` → strategy not triggering, read the reason
  - `Canvas size 1x1` → UI rendering issue
  - `Bot loop ended` unexpectedly → crash in loop

### Step 2 — Read the relevant file
- Never assume what's in a file — always read it first
- Focus on the specific function/method related to the problem
- Check variable names match what's being used

### Step 3 — Identify root cause
- Don't patch symptoms — find WHY it's happening
- If you've tried the same fix twice and it didn't work, STOP and rethink
- Ask: "What is the simplest explanation for this behavior?"

### Step 4 — Explain before changing
- For strategy changes: always explain to user first, get approval
- For bug fixes: explain what the root cause is
- For UI changes: describe what the user will see

---

## Analyzing Strategy Signals

When the user says "no entries are being generated", check the logs for the HOLD reason:

| Log message | Root cause | Fix |
|---|---|---|
| `No uptrend: EMA_fast <= EMA_slow` | Market is in downtrend | Wait, or enable allow_short |
| `No downtrend: EMA_fast >= EMA_slow` | Market is in uptrend | Wait, or check BUY signals |
| `No EMA touch: open=X, close=Y, EMA=Z` | EMA not between open/close | Normal — wait for crossover candle |
| `No SELL touch: open=X, close=Y, EMA=Z` | Downtrend but no crossover | Normal — wait |
| `Indicators not ready (NaN values)` | Not enough candles | Wait for more data |
| `Not enough data` | Less than ema_slow+atr_period+5 rows | Wait for buffer to fill |

### Checking if EMA touch is valid
Given: `open=2328.94, close=2327.55, EMA=2328.17`
- Is EMA between open and close? → `2327.55 < 2328.17 < 2328.94` → YES
- Is close > EMA? → `2327.55 > 2328.17` → NO → HOLD (no bounce up)
- Is close < EMA? → `2327.55 < 2328.17` → YES → potential SELL if downtrend

---

## Analyzing Trailing Stop Behavior

The trailing stop moves on EVERY tick, not just candle close.
- BUY: `new_stop = price * (1 - pct)` — only updates if `new_stop > current_stop`
- SELL: `new_stop = price * (1 + pct)` — only updates if `new_stop < current_stop`

If stop is moving in wrong direction → check `position.direction` and `effective_stop`

---

## Analyzing UI Issues

### Chart not showing
1. Check if `ChartPanel` is packed: `self.chart_panel.pack(fill=tk.BOTH, expand=True)` in app.py
2. Check canvas size in logs — if 1x1, the pack is missing
3. Check if `update()` is being called — look for chart update logs

### App not opening
1. Run `python -m py_compile ui/chart_panel.py` to check syntax
2. Check imports — a missing import silently crashes the app
3. Remove new UI components one by one to isolate the issue

### Bot not generating signals after timeframe change
1. Check `timeframe_to_seconds()` in helpers.py has the new timeframe
2. Note: `"15s".upper()` = `"15S"` — mapping keys must be uppercase

---

## Before Running the App After Changes

Always verify:
```
python -m pytest tests/test_strategy.py -v
```
All 24 tests must pass. If any fail, fix before running the app.

---

## Debugging Checklist

- [ ] Read the file before changing it
- [ ] Check logs for the actual error message
- [ ] Verify variable names are defined (common: `open_p`, `close`, `ema_fast`)
- [ ] After UI changes: verify `.pack()` is called in app.py
- [ ] After strategy changes: run tests
- [ ] After timeframe changes: verify `timeframe_to_seconds()` mapping
- [ ] After paper_broker changes: verify no `np.random.seed(fixed_value)`
