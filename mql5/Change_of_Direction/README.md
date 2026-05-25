# Change of Direction — MQL5 Expert Advisor

This is the MetaTrader 5 implementation of the **Change of Direction (COD)** strategy, identical to the Python version.

## Strategy Overview

**Change of Direction (COD)** is a reversal-based strategy that:
1. Identifies trend reversals through specific candle patterns
2. Confirms reversals with price action breakouts
3. Enters with fixed stop loss and take profit levels
4. Manages one position at a time

**Philosophy**: Catch reversals early by identifying when price breaks key support/resistance levels.

---

## Entry Rules (SELL)

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

## Entry Rules (BUY)

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

### Strategy Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `PIP_VALUE` | 0.01 | Value of 1 pip (e.g., 0.01 for XAUUSD) |
| `STOP_LOSS_PIPS` | 15 | Stop loss distance in pips |
| `TAKE_PROFIT_PIPS` | 45 | Take profit distance in pips |
| `MIN_RED_CANDLES` | 2 | Minimum consecutive red candles |
| `MIN_GREEN_CANDLES` | 2 | Minimum consecutive green candles |
| `ALLOW_SHORT` | true | Enable SELL signals |
| `ALLOW_LONG` | true | Enable BUY signals |

### Risk Management

| Parameter | Default | Description |
|-----------|---------|-------------|
| `RISK_PERCENT` | 1.0 | Risk per trade (% of balance) |
| `MAX_DAILY_LOSS_PCT` | 3.0 | Max daily loss (%) before halt |
| `MAX_OPEN_POSITIONS` | 1 | Max concurrent positions (always 1) |

### Paper Trading Mode

| Parameter | Default | Description |
|-----------|---------|-------------|
| `PAPER_TRADING_MODE` | **true** | If true: only print signals (no real orders). If false: execute real orders via OrderSend() |

---

## Installation

1. **Copy the file**:
   - Copy `Change_of_Direction.mq5` to your MetaTrader 5 `Experts` folder
   - Path: `C:\Users\[YourUser]\AppData\Roaming\MetaQuotes\Terminal\[TerminalID]\MQL5\Experts\`

2. **Compile**:
   - Open MetaEditor (F5 in MT5)
   - Open `Change_of_Direction.mq5`
   - Compile (Ctrl+F5)

3. **Attach to Chart**:
   - Open a chart (e.g., XAUUSD M1, EURUSD H4, etc.)
   - Drag the EA from Navigator onto the chart
   - Configure parameters in the EA settings dialog
   - Enable "Allow live trading" if using real account

---

## Paper Trading Mode

The EA includes a **PAPER_TRADING_MODE** parameter that lets you simulate without a real account:

### How It Works

- **PAPER_TRADING_MODE = true** (default):
  - EA generates signals and prints them to the logs
  - **No real orders are placed** — only simulated
  - Perfect for testing strategy logic without risk
  - No demo account needed

- **PAPER_TRADING_MODE = false**:
  - EA executes real orders via `OrderSend()`
  - Requires live or demo account
  - Use only after paper trading validation

### Example Log Output (Paper Mode)

```
[XAUUSD] [PAPER] SIMULATED SELL @ 2328.17500 lot=0.10 SL=2333.32500 TP=2273.02500
[XAUUSD] [PAPER] SIMULATED CLOSE SELL @ 2320.50000 PnL=765.00 | Take Profit hit
```

### Workflow

1. **Start with Paper Mode** (PAPER_TRADING_MODE = true):
   - Attach EA to any chart (no account needed)
   - Monitor logs for 1-2 weeks
   - Verify entry/exit signals match expectations

2. **Switch to Live Mode** (PAPER_TRADING_MODE = false):
   - Attach to demo account first
   - Run for 1 week to confirm real order execution
   - Then move to live account with small position sizes

---

## Usage

### Paper Trading (Recommended First)

1. Attach EA to a chart on a **demo account**
2. Monitor the logs in the "Experts" tab
3. Verify entry/exit signals match your expectations
4. Run for at least 1-2 weeks to see performance

### Live Trading

1. Backtest thoroughly on historical data
2. Paper trade for at least 1 week
3. Start with small position sizes
4. Monitor daily loss limits

---

## Symbol & Timeframe

The EA is **symbol-agnostic**:
- Attach to any chart (XAUUSD, EURUSD, NAS100, etc.)
- Works on any timeframe (M1, M5, H1, H4, D1, etc.)
- Automatically adapts to the chart's symbol and timeframe

**Important**: Adjust `PIP_VALUE` for your symbol:
- XAUUSD: 0.01 (default)
- EURUSD: 0.0001
- NAS100: 1.0
- SPX500: 1.0

---

## Logs

Check the "Experts" tab in MT5 for logs:

```
[XAUUSD] Change of Direction initialized
  SL=15 pips, TP=45 pips
  ALLOW_SHORT=true ALLOW_LONG=true

[XAUUSD] COD SELL: Reversal confirmed. entry=2328.17500 SL=2333.32500 TP=2273.02500
[XAUUSD] SELL opened at 2328.17500 SL=2333.32500 TP=2273.02500
[XAUUSD] SELL closed: Take Profit hit
```

---

## Synchronization with Python Bot

Both implementations use identical logic:
- Same pattern detection
- Same entry/exit conditions
- Same SL/TP calculation
- Same position management

You can run both simultaneously on different accounts/brokers and compare results.

---

## Known Limitations

1. **Position tracking**: Currently tracks only one position per symbol
2. **Daily loss**: Resets at 00:00 UTC
3. **No multi-symbol**: Each EA instance handles one symbol
4. **No backtesting**: Use MT5's built-in tester or the Python bot for backtesting
5. **Fixed SL/TP**: No adaptation to market volatility

---

## Troubleshooting

### EA not generating signals
- Check if pattern is forming (2+ red/green candles)
- Verify reversal candle meets conditions
- Check if price has broken the PCD
- Verify close is at or beyond New PCD

### Positions not opening
- Verify "Allow live trading" is enabled
- Check account balance and margin
- Verify pip value is correct for your symbol
- Check logs for error messages

### Frequent whipsaws
- Increase `MIN_RED_CANDLES` or `MIN_GREEN_CANDLES`
- Increase `STOP_LOSS_PIPS` for more buffer
- Consider adding a trend filter (EMA)
- Test on different timeframes

---

## Improvements (Future)

- [ ] Add volatility filter (ATR-based SL/TP)
- [ ] Add trend filter (EMA confirmation)
- [ ] Add RSI filter (overbought/oversold)
- [ ] Add trailing stop option
- [ ] Add multiple position support

---

## Support

For issues or questions:
1. Check the logs in MT5 "Experts" tab
2. Compare with Python bot behavior
3. Verify parameters match between Python and MQL5
4. Test on demo account first

---

## License

Same as the main project — MIT License
