# Change of Direction (COD) Strategy

## Overview

**Change of Direction (COD)** is a reversal-based strategy that identifies trend changes through specific candle patterns and price action confirmation.

**Philosophy**: Catch reversals early by identifying when price breaks key support/resistance levels established by candle patterns.

---

## Entry Logic (SELL)

### Pattern Recognition
1. **Find 2+ consecutive RED candles** (close < open)
2. **Next candle is GREEN** (close > open)
3. **Condition**: `close_green > open_first_red` ✅
4. Mark `open_green` as **Point of Change Direction (PCD)**

### Breakout Confirmation
1. Wait for price to **break below PCD** (low crosses PCD)
2. Store the new lowest point as **New PCD**

### Entry Confirmation
1. When `close <= New PCD` → **SELL Entry**
2. **Stop Loss**: entry_price + 15 pips
3. **Take Profit**: entry_price - 45 pips

### Example (SELL)
```
Candle 1: RED   (close=2330, open=2335)
Candle 2: RED   (close=2325, open=2330)
Candle 3: GREEN (close=2340, open=2325) ← PCD = 2325
          ✓ close(2340) > open_first_red(2335)

Candle 4: Price breaks below 2325 → New PCD = 2320
Candle 5: close=2318 <= New PCD(2320) → SELL Entry
          SL = 2318 + 15 pips = 2333
          TP = 2318 - 45 pips = 2273
```

---

## Entry Logic (BUY)

### Pattern Recognition
1. **Find 2+ consecutive GREEN candles** (close > open)
2. **Next candle is RED** (close < open)
3. **Condition**: `close_red < open_first_green` ✅
4. Mark `open_red` as **Point of Change Direction (PCD)**

### Breakout Confirmation
1. Wait for price to **break above PCD** (high crosses PCD)
2. Store the new highest point as **New PCD**

### Entry Confirmation
1. When `close >= New PCD` → **BUY Entry**
2. **Stop Loss**: entry_price - 15 pips
3. **Take Profit**: entry_price + 45 pips

### Example (BUY)
```
Candle 1: GREEN (close=2340, open=2335)
Candle 2: GREEN (close=2345, open=2340)
Candle 3: RED   (close=2330, open=2345) ← PCD = 2345
          ✓ close(2330) < open_first_green(2335)

Candle 4: Price breaks above 2345 → New PCD = 2350
Candle 5: close=2352 >= New PCD(2350) → BUY Entry
          SL = 2352 - 15 pips = 2337
          TP = 2352 + 45 pips = 2397
```

---

## Exit Rules

| Condition | Action |
|-----------|--------|
| SELL: close >= Stop Loss | **CLOSE** (SL hit) |
| SELL: close <= Take Profit | **CLOSE** (TP hit) |
| BUY: close <= Stop Loss | **CLOSE** (SL hit) |
| BUY: close >= Take Profit | **CLOSE** (TP hit) |

---

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `pip_value` | 0.01 | Value of 1 pip (e.g., 0.01 for XAUUSD) |
| `stop_loss_pips` | 15 | Stop loss distance in pips |
| `take_profit_pips` | 45 | Take profit distance in pips |
| `min_red_candles` | 2 | Minimum consecutive red candles |
| `min_green_candles` | 2 | Minimum consecutive green candles |
| `allow_short` | True | Enable SELL signals |
| `allow_long` | True | Enable BUY signals |

---

## Position Management

- **One position at a time**: No new entries until current position closes
- **Fixed SL/TP**: No trailing stop, fixed distances
- **Automatic exit**: Closes when SL or TP is hit

---

## Advantages

✅ **Clear entry signals**: Pattern-based, easy to understand
✅ **Fixed risk/reward**: 15 pips risk, 45 pips reward (1:3 ratio)
✅ **Reversal-focused**: Catches trend changes early
✅ **Works on any timeframe**: M1, M5, H1, H4, D1, etc.
✅ **Works on any symbol**: XAUUSD, EURUSD, NAS100, etc.

---

## Disadvantages

❌ **Whipsaws**: False breakouts can trigger premature entries
❌ **Fixed SL/TP**: May not adapt to market volatility
❌ **Pattern dependency**: Requires specific candle patterns
❌ **No trend filter**: Can enter against strong trends

---

## Improvements (Future)

- [ ] Add volatility filter (ATR-based SL/TP)
- [ ] Add trend filter (EMA confirmation)
- [ ] Add RSI filter (overbought/oversold)
- [ ] Add trailing stop option
- [ ] Add multiple position support

---

## Comparison with EMA Pullback Pro

| Aspect | COD | EMA Pullback Pro |
|--------|-----|-----------------|
| Type | Reversal | Trend-following |
| Entry | Pattern-based | EMA-based |
| SL/TP | Fixed | Dynamic trailing |
| Risk/Reward | 1:3 | Variable |
| Timeframe | Any | Any |
| Complexity | Low | Medium |

---

## Testing Recommendations

1. **Backtest** on 1-2 weeks of historical data
2. **Paper trade** for 1-2 weeks
3. **Monitor** win rate and average profit/loss
4. **Adjust** pip values if needed for your symbol
5. **Compare** with EMA Pullback Pro performance

---

## Notes

- COD strategy is **symbol-agnostic** — adjust `pip_value` for your symbol
- Works best on **liquid symbols** (XAUUSD, EURUSD, etc.)
- Can be combined with other strategies for diversification
- Consider market conditions (trending vs. ranging)

---

## License

Same as the main project — MIT License
