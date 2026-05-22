# 🏄 EMA Rider — Trend Following Trading Bot

A professional algorithmic trading bot built in Python with a desktop GUI.  
Designed for **EMA pullback trend following** on Gold (XAUUSD), Nasdaq (NAS100), and S&P 500 (SPX500).

> **Philosophy**: Small losses, let big trends run. The EMA is not just an indicator — it IS the trade.

---

## 📸 Features

- **EMA Pullback Strategy** — price touches EMA, bounces, and rides the trend
- **Dynamic Trailing Stop** — follows EMA as support/resistance, never moves against the trade
- **Risk Management** — fixed fractional sizing, daily loss limits, max positions
- **Paper Trading** — full simulation with synthetic data, no API needed
- **Desktop GUI** — Tkinter dashboard with live candlestick chart, trade history, logs
- **SQLite Persistence** — all trades and events saved locally
- **Multi-Timeframe** — supports 15s, 30s, M1, M5, M15, H1, H4, D1
- **Modular Architecture** — easy to add new strategies, brokers, symbols

---

## 🗂 Project Structure

```
trader/
├── main.py                    # Entry point
├── config.py                  # Central config (reads .env)
├── requirements.txt
├── .env.example               # Environment template
│
├── ui/                        # Tkinter interface
│   ├── app.py                 # Main window + wiring
│   ├── dashboard.py           # Trade history + stats
│   ├── logs_window.py         # Real-time event log
│   └── settings_window.py     # Strategy + risk settings
│
├── strategies/                # Trading strategies
│   ├── base_strategy.py       # Abstract base + Signal dataclass
│   └── ema_trend_strategy.py  # EMA crossover + ATR trailing stop
│
├── brokers/                   # Broker integrations
│   ├── base_broker.py         # Abstract interface
│   ├── paper_broker.py        # Paper trading simulation
│   └── future_broker.py       # Stub + broker factory
│
├── market_data/               # Data pipeline
│   ├── candle_builder.py      # Rolling candle buffer
│   └── market_stream.py       # Bot engine loop
│
├── risk_management/
│   └── risk_manager.py        # Position sizing + risk rules
│
├── database/
│   ├── database.py            # SQLite connection + schema
│   └── trade_repository.py    # Trade CRUD operations
│
├── models/                    # Data classes
│   ├── candle.py
│   ├── trade.py
│   └── position.py
│
├── utils/
│   ├── indicators.py          # pandas-ta wrappers (EMA, ATR, RSI)
│   ├── logger.py              # Rotating file + console logger
│   └── helpers.py             # Utilities (lot sizing, time, etc.)
│
├── tests/
│   └── test_strategy.py       # pytest unit tests
│
├── mql5/                      # MetaTrader 5 Expert Advisors
│   ├── README.md              # MQL5 setup guide
│   └── EMA_Pullback_Pro/      # EMA Pullback Pro EA
│       ├── EMA_Pullback_Pro.mq5
│       └── README.md
│
└── logs/                      # Log files (auto-created)
```

---

## 🚀 Quick Start

### 1. Clone and install

```bash
git clone https://github.com/youruser/algotrader-pro.git
cd algotrader-pro
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
```

### 2. Configure

```bash
copy .env.example .env         # Windows
# cp .env.example .env         # macOS/Linux
```

Edit `.env` with your settings. For paper trading, no API keys are needed.

### 3. Run

```bash
python main.py
```

---

## 📊 Strategy: EMA Pullback Pro

### Overview
**EMA Pullback Pro** is a trend-following strategy that identifies pullbacks (retracements) to the fast EMA within a confirmed trend. It enters when price touches the EMA and bounces, using the EMA as dynamic support/resistance. Positions close when price falls a specific percentage below the EMA.

**Philosophy**: Small losses, let big trends run. The EMA is not just an indicator — it IS the trade.

### Entry Rules (BUY)
1. **Uptrend confirmed**: `EMA_fast > EMA_slow`
2. **EMA touch**: EMA is between candle `open` and `close` (price crossed EMA during the candle)
3. **Bounce confirmed**: `close > EMA_fast` (candle closed above EMA)

**Result**: Price pulls back to the EMA and bounces — entry signal.

### Entry Rules (SELL — optional)
1. **Downtrend confirmed**: `EMA_fast < EMA_slow`
2. **EMA touch**: EMA is between candle `open` and `close`
3. **Bounce down confirmed**: `close < EMA_fast` (candle closed below EMA)

**Result**: Price pulls back to the EMA and bounces down — short entry signal.

### Exit Rules
| Condition | Action |
|-----------|--------|
| Close drops X% below EMA_fast | **CLOSE** position |
| Price hits trailing stop | **CLOSE** position |
| Daily loss limit reached | **HALT** trading |

### Trailing Stop (Dynamic)
```
BUY:  new_stop = current_price × (1 - exit_pct / 100)  [only moves UP]
SELL: new_stop = current_price × (1 + exit_pct / 100)  [only moves DOWN]
```
Stop is recalculated on every tick, following price as it moves in your favor.

**Example (BUY with exit_pct = 0.3%)**:
```
price=2300 → stop = 2293.10  (entry)
price=2320 → stop = 2313.04  (moves up)
price=2350 → stop = 2342.95  (moves up)
price drops to 2342.95 → stop hit → close with profit
```

### Strategy Parameters

| Parameter | Default | Type | Description |
|-----------|---------|------|-------------|
| `ema_fast` | 21 | int | Fast EMA period (entry/exit/stop) |
| `ema_slow` | 50 | int | Slow EMA period (trend filter) |
| `atr_period` | 14 | int | ATR period (for future filters) |
| `touch_tolerance_atr` | 0.5 | float | Touch tolerance in ATR multiples (0.5 = half ATR) |
| `exit_pct_below_ema` | 0.3 | float | % below/above EMA that triggers exit (0.3 = 0.3%) |
| `rsi_period` | 14 | int | RSI period (for optional filter) |
| `use_rsi_filter` | False | bool | Enable RSI filter on entry |
| `allow_short` | False | bool | Enable SELL signals (short selling) |

---

## ⚙️ Configuration

All parameters are configurable from the Settings tab in the UI or via `.env`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ACTIVE_STRATEGY` | EMA Pullback Pro | Active trading strategy |
| `EMA_FAST` | 21 | Fast EMA period (entry/exit/stop) |
| `EMA_SLOW` | 50 | Slow EMA period (trend filter) |
| `ATR_PERIOD` | 14 | ATR period (optional, for future filters) |
| `EXIT_PCT_BELOW_EMA` | 0.3 | % below/above EMA that triggers exit |
| `DEFAULT_RISK_PERCENT` | 1.0 | Risk per trade (% of balance) |
| `MAX_DAILY_LOSS_PERCENT` | 3.0 | Daily loss limit before halt |
| `MAX_OPEN_POSITIONS` | 3 | Maximum concurrent positions |
| `TICK_INTERVAL_SECONDS` | 5 | How often to poll for new data |
| `ALLOW_SHORT` | False | Enable SELL signals (short selling) |

---

## 🧪 Running Tests

```bash
pytest tests/ -v
```

---

## 🔌 Adding a Real Broker

1. Create `brokers/alpaca_broker.py` (or oanda, ibkr, etc.)
2. Inherit from `BaseBroker` and implement all abstract methods
3. Add a case to `create_broker()` in `future_broker.py`
4. Set `BROKER_NAME=alpaca` in your `.env`

The rest of the system (strategy, risk manager, UI) requires zero changes.

---

## 🗺 Roadmap

- [ ] Real broker integration (Alpaca, OANDA, Interactive Brokers)
- [ ] WebSocket streaming for live ticks
- [ ] Backtesting engine with historical data
- [ ] Multiple simultaneous strategies
- [ ] Advanced filters (RSI, MACD, Bollinger Bands)
- [ ] Email/Telegram alerts on trades
- [ ] Machine learning signal filter
- [ ] Cloud deployment (VPS/AWS)
- [ ] Mobile app for monitoring

---

## 🏗 Architecture Notes

### Thread Model
```
Main Thread (Tkinter)
    └── BotEngine Thread (daemon)
            ├── polls broker every N seconds
            ├── calls strategy.generate_signal()
            ├── calls risk_manager.can_open_trade()
            └── emits events → root.after() → UI updates
```

### Adding a New Strategy
1. Create `strategies/my_strategy.py`
2. Inherit from `BaseStrategy`
3. Implement `generate_signal()`, `calculate_stop_loss()`, `update_trailing_stop()`
4. Pass it to `BotEngine` in `app.py`

### Coming from MQL5?
| MQL5 Concept | Python Equivalent |
|---|---|
| `OnTick()` | `BotEngine._tick()` in `market_stream.py` |
| `OnBar()` | Candle close detection in `_tick()` |
| `OrderSend()` | `broker.place_market_order()` |
| `PositionModify()` | `broker.modify_stop_loss()` |
| `iEMA()` | `compute_all()` in `utils/indicators.py` |
| `iATR()` | `compute_all()` in `utils/indicators.py` |
| Expert Advisor | `BotEngine` class + `EmaTrendStrategy` |
| `Print()` | `logger.info()` / `logger.debug()` |

---

## 🤖 MetaTrader 5 Expert Advisors (MQL5)

The same strategies are also available as **MetaTrader 5 Expert Advisors** for trading on any MT5-compatible broker.

### Available EAs

- **EMA Pullback Pro** — Identical logic to the Python strategy
  - Location: `mql5/EMA_Pullback_Pro/EMA_Pullback_Pro.mq5`
  - Works on any symbol and timeframe
  - Same parameters as Python version

### Installation

1. Copy the `.mq5` file to your MT5 `Experts` folder
2. Compile in MetaEditor (F5)
3. Attach to a chart
4. Configure parameters and enable live trading

### Advantages of MQL5 Version

- ✅ Run on any MT5 broker (OANDA, IC Markets, etc.)
- ✅ Lower latency (EA runs on broker's server)
- ✅ Automatic data synchronization
- ✅ Native MT5 alerts and notifications
- ✅ Backtesting in MT5 Strategy Tester

### Synchronization

Both Python and MQL5 versions use **identical logic**:
- Same entry/exit conditions
- Same parameters
- Same trailing stop calculation
- Same risk management rules

You can run both simultaneously and compare results.

See `mql5/README.md` for detailed setup instructions.

---

### Why EMA Pullback?
The EMA acts as **dynamic support/resistance**. When price pulls back to the EMA and bounces, it's a high-probability entry because:
1. The trend is confirmed (EMA_fast > EMA_slow)
2. Price respects the EMA as support
3. The bounce shows buyers are defending that level

### Reading the Logs
When you run the bot, check `logs/trading_bot.log` for signal reasons:

| Log Message | Meaning |
|---|---|
| `EMA touch+bounce: EMA=X between open=Y and close=Z` | BUY entry triggered |
| `EMA touch+bounce DOWN: EMA=X between open=Y and close=Z` | SELL entry triggered |
| `No uptrend: EMA_fast <= EMA_slow` | Market is in downtrend, waiting |
| `No EMA touch: open=X, close=Y, EMA=Z` | EMA not between open/close, no entry |
| `Position intact: open=X, close=Y, EMA=Z` | Position open, no exit yet |
| `BUY exit: close=X < exit_level=Y` | Position closed with profit/loss |
| `Stop hit: XAUUSD BUY price=X stop=Y` | Trailing stop triggered |

### Debugging Tips
1. **No entries?** Check if `EMA_fast > EMA_slow` (uptrend). If not, wait or enable `ALLOW_SHORT`.
2. **Entries too frequent?** Increase `EMA_FAST` or `EMA_SLOW` for fewer, higher-quality signals.
3. **Exits too early?** Increase `EXIT_PCT_BELOW_EMA` to give trades more room.
4. **Stops too tight?** Decrease `EXIT_PCT_BELOW_EMA` to protect capital faster.

---

MIT License — see [LICENSE](LICENSE)

---

## ⚠️ Disclaimer

This software is for educational purposes only.  
Trading financial instruments involves significant risk of loss.  
Past performance does not guarantee future results.  
Always test thoroughly in paper trading before using real capital.
