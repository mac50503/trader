# ⚡ AlgoTrader Pro — Multi-Strategy Trading Bot

A professional algorithmic trading bot built in Python with a desktop GUI.
Supports multiple strategies, paper trading simulation, live candlestick charts,
and MetaTrader 5 Expert Advisors.

> **Philosophy**: Small losses, let big trends run.

---

## 📸 Features

- **Multiple Strategies** — EMA Pullback Pro + Change of Direction (COD), hot-swappable from UI
- **Pattern Visualizer** — visual diagram of each strategy's entry pattern
- **Dynamic Trailing Stop** — follows price in real time, never moves against the trade
- **Risk Management** — fixed fractional sizing, daily loss limits, max positions
- **Paper Trading** — full simulation with synthetic OHLCV data, no API needed
- **Desktop GUI** — Tkinter dashboard with live candlestick chart, trade history, logs
- **SQLite Persistence** — all trades and events saved locally
- **Multi-Timeframe** — supports 15s, 30s, M1, M5, M15, H1, H4, D1
- **MQL5 Expert Advisors** — identical logic available for MetaTrader 5

---

## 🗂 Project Structure

```
trader/
├── main.py                        # Entry point
├── config.py                      # Central config (reads .env)
├── requirements.txt
├── .env.example
│
├── ui/
│   ├── app.py                     # Main window + wiring
│   ├── dashboard.py               # Trade history + stats
│   ├── chart_panel.py             # Live candlestick chart (Tkinter Canvas)
│   ├── logs_window.py             # Real-time event log
│   ├── settings_window.py         # Strategy + risk settings
│   └── pattern_visualizer.py      # Visual entry pattern diagram
│
├── strategies/
│   ├── base_strategy.py           # Abstract base + Signal dataclass
│   ├── ema_trend_strategy.py      # EMA Pullback Pro
│   ├── change_of_direction_strategy.py  # Change of Direction (COD)
│   └── strategy_registry.py       # Strategy registry + hot-swap
│
├── brokers/
│   ├── base_broker.py             # Abstract interface
│   ├── paper_broker.py            # Paper trading simulation
│   └── future_broker.py           # Broker factory
│
├── market_data/
│   ├── candle_builder.py          # Rolling candle buffer
│   └── market_stream.py           # BotEngine — main loop
│
├── risk_management/
│   └── risk_manager.py            # Position sizing + risk rules
│
├── database/
│   ├── database.py                # SQLite connection + schema
│   └── trade_repository.py        # Trade CRUD operations
│
├── models/
│   ├── trade.py
│   ├── position.py
│   └── candle.py
│
├── utils/
│   ├── indicators.py              # EMA, ATR, RSI via pandas-ta
│   ├── logger.py                  # Rotating file + console logger
│   └── helpers.py                 # Utilities
│
├── tests/
│   └── test_strategy.py           # 24 pytest unit tests
│
├── mql5/
│   ├── MQL5_CONVERSION_GUIDE.md   # Guide for converting strategies to MQL5
│   ├── EMA_Pullback_Pro/
│   │   ├── EMA_Pullback_Pro.mq5
│   │   └── README.md
│   └── Change_of_Direction/
│       ├── Change_of_Direction.mq5
│       └── README.md
│
└── logs/
```

---

## 🚀 Quick Start

```bash
git clone https://github.com/youruser/algotrader-pro.git
cd algotrader-pro
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python main.py
```

No API keys needed for paper trading.

---

## 📊 Strategies

### 1. EMA Pullback Pro

Trend-following strategy. Enters when price touches the fast EMA and bounces within a confirmed trend.

**Entry (BUY)**:
1. `EMA_fast > EMA_slow` → uptrend confirmed
2. EMA_fast is between candle `open` and `close` → price touched EMA
3. `close > EMA_fast` → bounce confirmed

**Entry (SELL)** — mirror logic with `EMA_fast < EMA_slow`.

**Exit**: Close when price drops X% below EMA_fast, or trailing stop hit.

**Trailing Stop**: Recalculated every tick.
```
BUY:  stop = price × (1 - exit_pct%)  [only moves UP]
SELL: stop = price × (1 + exit_pct%)  [only moves DOWN]
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ema_fast` | 21 | Fast EMA period |
| `ema_slow` | 50 | Slow EMA period |
| `exit_pct_below_ema` | 0.3 | % from EMA to trigger exit |
| `allow_short` | False | Enable SELL signals |

---

### 2. Change of Direction (COD)

Reversal strategy using a 4-phase state machine. Identifies trend reversals through candle patterns and price action.

**Entry (SELL) — 4 phases**:

```
PHASE 1 — 2+ consecutive RED candles
  → point_1 = lowest low of the reds

PHASE 2 — First pullback (2+ greens, not necessarily consecutive)
  → At least one green must exceed open_first_red
  → pullback1_high = highest high (reset reference for PHASE 4/5)

PHASE 3 — Break of point_1
  → close < point_1 → bearish continuation confirmed

PHASE 4 — Second pullback (2+ greens, not necessarily consecutive)
  → point_2 = lowest low of these greens
  → pullback2_high = highest high → Stop Loss
  → RESET if close > pullback1_high (second pullback can't exceed first)

PHASE 5 — Entry
  → close <= point_2 → SELL
  → SL = pullback2_high
  → TP = entry - (SL - entry) × 2  [1:2 risk/reward]
```

**Entry (BUY)** — mirror logic.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_red_candles` | 2 | Min consecutive red candles (PHASE 1) |
| `min_green_candles` | 2 | Min green candles per pullback |
| `allow_short` | True | Enable SELL signals |
| `allow_long` | True | Enable BUY signals |

---

## ⚙️ Configuration

All parameters configurable from **Settings** tab or `.env`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ACTIVE_STRATEGY` | EMA Pullback Pro | Active strategy (hot-swappable) |
| `DEFAULT_RISK_PERCENT` | 1.0 | Risk per trade (% of balance) |
| `MAX_DAILY_LOSS_PERCENT` | 3.0 | Daily loss limit before halt |
| `MAX_OPEN_POSITIONS` | 1 | Maximum concurrent positions |
| `TICK_INTERVAL_SECONDS` | 5 | Poll interval in seconds |

---

## 🎨 Pattern Visualizer

Click **🎨 Draw Pattern** in Settings to open a visual diagram showing exactly what candle pattern the active strategy is looking for — with annotated price levels, entry arrow, SL and TP zones.

---

## 🧪 Tests

```bash
pytest tests/test_strategy.py -v
```

24 unit tests covering entry signals, exit signals, trailing stops, and risk management.

---

## 🤖 MetaTrader 5 Expert Advisors

Both strategies are available as MQL5 EAs with identical logic.

| EA | File | Paper Mode |
|----|------|------------|
| EMA Pullback Pro | `mql5/EMA_Pullback_Pro/EMA_Pullback_Pro.mq5` | `PAPER_TRADING_MODE=true` |
| Change of Direction | `mql5/Change_of_Direction/Change_of_Direction.mq5` | `PAPER_TRADING_MODE=true` |

**Installation**: Copy `.mq5` to MT5 `Experts` folder → compile in MetaEditor → attach to chart.

See `mql5/MQL5_CONVERSION_GUIDE.md` for best practices when converting Python strategies to MQL5.

---

## 🏗 Architecture

### Thread Model
```
Main Thread (Tkinter UI)
    └── BotEngine Thread (daemon)
            ├── polls broker every N seconds
            ├── detects new closed candle
            ├── calls strategy.generate_signal()
            ├── calls risk_manager.can_open_trade()
            └── emits events → root.after() → UI updates
```

### Adding a New Strategy
1. Create `strategies/my_strategy.py` — inherit from `BaseStrategy`
2. Implement `generate_signal()`, `calculate_stop_loss()`, `update_trailing_stop()`
3. Register in `strategy_registry.py`
4. Select from Settings tab — takes effect immediately (hot-swap)

### Adding a Real Broker
1. Create `brokers/my_broker.py` — inherit from `BaseBroker`
2. Implement all abstract methods
3. Add case to `create_broker()` in `future_broker.py`
4. Set `BROKER_NAME=mybroker` in `.env`

### MQL5 Equivalent
| MQL5 | Python |
|------|--------|
| `OnTick()` | `BotEngine._tick()` |
| `OrderSend()` | `broker.place_market_order()` |
| `PositionModify()` | `broker.modify_stop_loss()` |
| `iEMA()` / `iATR()` | `compute_all()` in `utils/indicators.py` |
| `Print()` | `logger.info()` |

---

## 📋 Log Messages

| Message | Meaning |
|---------|---------|
| `COD: sell=PHASE1_DROP` | COD detected first red candles |
| `COD: sell=PHASE2_PULLBACK1` | COD in first pullback |
| `COD: sell=PHASE3_BREAK` | COD waiting for break of point_1 |
| `COD: sell=PHASE4_PULLBACK2` | COD in second pullback |
| `COD: sell=PHASE5_ENTRY` | COD waiting for entry confirmation |
| `COD SELL ENTRY: close=X <= point_2=Y` | SELL executed |
| `EMA touch+bounce: EMA=X between open=Y close=Z` | EMA BUY entry |
| `Stop hit: XAUUSD BUY price=X stop=Y` | Trailing stop triggered |

---

## 🗺 Roadmap

- [ ] Real broker integration (Alpaca, OANDA, Interactive Brokers)
- [ ] Backtesting engine with historical data
- [ ] WebSocket streaming for live ticks
- [ ] Email/Telegram alerts on trades
- [ ] Additional strategies (Bollinger Bands, MACD divergence)
- [ ] Cloud deployment (VPS/AWS)

---

## ⚠️ Disclaimer

This software is for educational purposes only.
Trading financial instruments involves significant risk of loss.
Always test thoroughly in paper trading before using real capital.

---

MIT License — see [LICENSE](LICENSE)
