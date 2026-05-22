# EMA Pullback Pro — MQL5 Expert Advisor

This is the MetaTrader 5 implementation of the **EMA Pullback Pro** strategy, identical to the Python version.

## Strategy Overview

**EMA Pullback Pro** is a trend-following strategy that:
1. Identifies pullbacks (retracements) to the fast EMA within a confirmed trend
2. Enters when price touches the EMA and bounces
3. Uses the EMA as dynamic support/resistance
4. Closes positions when price falls a specific percentage below the EMA

**Philosophy**: Small losses, let big trends run. The EMA is not just an indicator — it IS the trade.

---

## Entry Rules (BUY)

1. **Uptrend confirmed**: `EMA_fast > EMA_slow`
2. **EMA touch**: EMA is between candle `open` and `close` (price crossed EMA during the candle)
3. **Bounce confirmed**: `close > EMA_fast` (candle closed above EMA)

**Result**: Price pulls back to the EMA and bounces — entry signal.

### Entry Rules (SELL — optional)

1. **Downtrend confirmed**: `EMA_fast < EMA_slow`
2. **EMA touch**: EMA is between candle `open` and `close`
3. **Bounce down confirmed**: `close < EMA_fast` (candle closed below EMA)

**Result**: Price pulls back to the EMA and bounces down — short entry signal.

---

## Exit Rules

| Condition | Action |
|-----------|--------|
| Close drops X% below EMA_fast | **CLOSE** position |
| Price hits trailing stop | **CLOSE** position |

---

## Trailing Stop (Dynamic)

Stop is recalculated on every tick:

```
BUY:  new_stop = current_price × (1 - exit_pct / 100)  [only moves UP]
SELL: new_stop = current_price × (1 + exit_pct / 100)  [only moves DOWN]
```

**Example (BUY with exit_pct = 0.3%)**:
```
price=2300 → stop = 2293.10  (entry)
price=2320 → stop = 2313.04  (moves up)
price=2350 → stop = 2342.95  (moves up)
price drops to 2342.95 → stop hit → close with profit
```

---

## Parameters

### Strategy Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `EMA_FAST` | 21 | Fast EMA period (entry/exit/stop) |
| `EMA_SLOW` | 50 | Slow EMA period (trend filter) |
| `EXIT_PCT_BELOW_EMA` | 0.3 | % below/above EMA that triggers exit |
| `ALLOW_SHORT` | false | Enable SELL signals (short selling) |
| `ATR_PERIOD` | 14 | ATR period (for future filters) |

### Risk Management

| Parameter | Default | Description |
|-----------|---------|-------------|
| `RISK_PERCENT` | 1.0 | Risk per trade (% of balance) |
| `MAX_DAILY_LOSS_PCT` | 3.0 | Max daily loss (%) before halt |
| `MAX_OPEN_POSITIONS` | 3 | Max concurrent positions |

### Behavior

| Parameter | Default | Description |
|-----------|---------|-------------|
| `TICK_INTERVAL` | 5 | Seconds between ticks (for testing) |
| `USE_RSI_FILTER` | false | Enable RSI filter on entry |
| `RSI_PERIOD` | 14 | RSI period |

---

## Installation

1. **Copy the file**:
   - Copy `EMA_Pullback_Pro.mq5` to your MetaTrader 5 `Experts` folder
   - Path: `C:\Users\[YourUser]\AppData\Roaming\MetaQuotes\Terminal\[TerminalID]\MQL5\Experts\`

2. **Compile**:
   - Open MetaEditor (F5 in MT5)
   - Open `EMA_Pullback_Pro.mq5`
   - Compile (Ctrl+F5)

3. **Attach to Chart**:
   - Open a chart (e.g., XAUUSD M1, EURUSD H4, etc.)
   - Drag the EA from Navigator onto the chart
   - Configure parameters in the EA settings dialog
   - Enable "Allow live trading" if using real account

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

---

## Logs

Check the "Experts" tab in MT5 for logs:

```
[XAUUSD] EMA Pullback Pro initialized
  EMA_FAST=21 EMA_SLOW=50
  EXIT_PCT=0.3% ALLOW_SHORT=false

[XAUUSD] BUY opened at 2328.17500 SL=2327.55115
[XAUUSD] Trailing stop UP: 2327.55115 → 2328.17500
[XAUUSD] BUY closed: Exit signal
```

---

## Synchronization with Python Bot

Both implementations use identical logic:
- Same entry/exit conditions
- Same parameters
- Same trailing stop calculation
- Same risk management rules

You can run both simultaneously on different accounts/brokers and compare results.

---

## Known Limitations

1. **Position tracking**: Currently tracks only one position per symbol
2. **Daily loss**: Resets at 00:00 UTC
3. **No multi-symbol**: Each EA instance handles one symbol
4. **No backtesting**: Use MT5's built-in tester or the Python bot for backtesting

---

## Troubleshooting

### EA not generating signals
- Check if `EMA_FAST > EMA_SLOW` (uptrend)
- Verify EMA is between open and close
- Check if close is above EMA (for BUY)

### Positions not opening
- Verify "Allow live trading" is enabled
- Check account balance and margin
- Verify stop loss distance is valid

### Trailing stop not updating
- Check if position is open
- Verify price is moving in favorable direction
- Check logs for errors

---

## Support

For issues or questions:
1. Check the logs in MT5 "Experts" tab
2. Compare with Python bot behavior
3. Verify parameters match between Python and MQL5

---

## License

Same as the main project — MIT License
