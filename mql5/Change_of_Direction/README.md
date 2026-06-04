# Change of Direction — MQL5 Expert Advisors

MetaTrader 5 implementations of the **Change of Direction (COD)** strategy with multiple versions.

## 📁 Available Versions

| Version | File | Description | Python Equivalent |
|---------|------|-------------|-------------------|
| **V6** | `Change_of_Direction_V6.mq5` | ✅ **Base version** — Single pattern tracking | `change_of_direction_strategy.py` |
| **V7** | `Change_of_Direction_V7.mq5` | ⚠️ **Experimental** — Additional validation | *(testing only)* |
| **V8** | `Change_of_Direction_MultiPattern.mq5` | 🆕 **Multi-pattern** — Tracks all patterns | `pattern_priority_strategy.py` |

**Recommended for production:** V6 or V8  
**For detailed comparison:** See [VERSION_COMPARISON.md](VERSION_COMPARISON.md)

---

## Strategy Overview

**Change of Direction (COD)** is a reversal-based strategy using a **4-phase state machine**:

### The 4 Phases

1. **PHASE 1 — Initial Move**
   - SELL: 2+ consecutive RED candles (bearish drop)
   - BUY: 2+ consecutive GREEN candles (bullish rally)
   - Marks `point_1` (lowest low for SELL, highest high for BUY)

2. **PHASE 2 — First Pullback**
   - SELL: 2+ GREEN candles (pullback up, not necessarily consecutive)
   - BUY: 2+ RED candles (pullback down, not necessarily consecutive)
   - Marks `pullback1_high` (SELL) or `pullback1_low` (BUY)

3. **PHASE 3 — Break Confirmation**
   - Wait for price to break `point_1`
   - SELL: `close < point_1` → bearish continuation confirmed
   - BUY: `close > point_1` → bullish continuation confirmed

4. **PHASE 4 — Second Pullback**
   - SELL: 2+ GREEN candles → marks `point_2` (lowest low of pullback)
   - BUY: 2+ RED candles → marks `point_2` (highest high of pullback)
   - SL = `pullback2_high` (SELL) or `pullback2_low` (BUY)

5. **ENTRY — Final Breakout**
   - SELL: `close <= point_2` → SELL Entry
   - BUY: `close >= point_2` → BUY Entry
   - **TP** = entry + (risk × 2) → **1:2 risk/reward ratio**

### Trend Filter

All versions use **EMA40 on M5 timeframe** as trend filter:
- **SELL allowed** only when `price < EMA40_M5` (downtrend)
- **BUY allowed** only when `price > EMA40_M5` (uptrend)

**Philosophy**: Catch reversals that align with the broader M5 trend.

---

## Quick Start

### 1. Choose Your Version

- **Want stability?** → Use **V6** (proven, single pattern tracking)
- **Want more opportunities?** → Use **V8** (multi-pattern, more aggressive)  
- **Testing only?** → V7 (not recommended for production)

### 2. Installation

1. **Copy** the `.mq5` file to: `...\MQL5\Experts\`
2. **Compile** in MetaEditor (F7)
3. **Attach** to XAUUSD M5 chart
4. **Configure** parameters (start with `PAPER_TRADING_MODE = true`)

### 3. Monitor

Check "Experts" tab for logs showing pattern progression and entries.

---

## Common Parameters (All Versions)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MIN_RED_CANDLES` | 2 | Min consecutive red candles (PHASE1) |
| `MIN_GREEN_CANDLES` | 2 | Min green candles per pullback |
| `ALLOW_SHORT` | true | Enable SELL signals |
| `ALLOW_LONG` | true | Enable BUY signals |
| `RISK_PERCENT` | 1.0 | Risk per trade (% of balance) |
| `MAX_OPEN_POSITIONS` | 1 | Max concurrent positions |
| `PAPER_TRADING_MODE` | false | Paper trading (logs only, no orders) |
| `DEBUG_LOGS` | false | Show detailed phase transition logs |

---

## Paper Trading Mode

Perfect for testing without risk:

- **PAPER_TRADING_MODE = true**:
  - Prints signals to logs
  - No real orders placed
  - No account required

- **PAPER_TRADING_MODE = false**:
  - Executes real orders via `OrderSend()`
  - Requires live/demo account

### Example Logs (Paper Mode)

```
[XAUUSD] Pattern #2 SELL ENTRY: close=2610.00 SL=2618.50 TP=2593.00 risk=8.50
[XAUUSD] [PAPER] SELL @ 2610.00 lot=0.10 SL=2618.50 TP=2593.00
[XAUUSD] [PAPER] SELL closed @ 2593.00 PnL=+170.00 | Take Profit hit
```

---

## Symbol & Timeframe

The EAs are **symbol-agnostic**:
- Attach to any chart (XAUUSD, EURUSD, NAS100, etc.)
- Works on any timeframe (M1, M5, H1, D1, etc.)
- **Note**: EMA40 M5 trend filter always uses M5 data regardless of chart timeframe

**Recommended**: XAUUSD M5

---

## Synchronization with Python Bot

Both implementations use identical logic:

| Aspect | Python | MQL5 |
|--------|--------|------|
| **Single Pattern** | `change_of_direction_strategy.py` | V6 |
| **Multi-Pattern** | `pattern_priority_strategy.py` | V8 |
| **State Machine** | 4 phases (IDLE → PHASE5) | 4 phases (IDLE → PHASE5) |
| **Trend Filter** | EMA40 M5 | EMA40 M5 |
| **Risk/Reward** | 1:2 ratio | 1:2 ratio |

You can run both simultaneously on different accounts/brokers and compare results.

---

## Troubleshooting

### EA not generating signals
- Check if pattern is forming (2+ red/green candles)
- Verify trend filter allows direction (price vs EMA40 M5)
- Enable `DEBUG_LOGS = true` to see phase transitions
- Check logs for "waiting" messages

### Positions not opening
- Verify "Allow live trading" is enabled
- Check account balance and margin
- Verify `PAPER_TRADING_MODE = false` for real orders
- Check logs for error messages

### Too many false signals (V8)
- This is normal for multi-pattern tracking
- Many patterns start but few complete
- Only the first completed pattern executes
- Invalid patterns are auto-removed

---

## Version History

- **V6** (2025): Base version with single pattern tracking + EMA40 M5 filter
- **V7** (2025): Experimental validation (not recommended for production)
- **V8** (2026): Multi-pattern tracking, first-to-complete wins

---

## Support

For issues or questions:
1. Check the [VERSION_COMPARISON.md](VERSION_COMPARISON.md) for version details
2. Compare with Python bot behavior
3. Test on demo account first
4. Review logs in MT5 "Experts" tab

---

## License

MIT License — Same as main project
