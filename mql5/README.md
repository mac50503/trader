# MQL5 Expert Advisors

This directory contains MetaTrader 5 Expert Advisors (EAs) that implement the same trading strategies as the Python bot.

## Structure

```
mql5/
├── README.md                          # This file
├── EMA_Pullback_Pro/
│   ├── EMA_Pullback_Pro.mq5          # Main EA file
│   ├── README.md                      # Strategy documentation
│   └── parameters.json                # Parameter sync file (optional)
└── [Future strategies]/
    ├── [Strategy].mq5
    └── README.md
```

## Installation

1. Copy the `.mq5` file to your MetaTrader 5 `Experts` folder:
   - Windows: `C:\Users\[YourUser]\AppData\Roaming\MetaQuotes\Terminal\[TerminalID]\MQL5\Experts\`
   - Or use MetaEditor: File → Open Data Folder → MQL5 → Experts

2. Compile the EA in MetaEditor (F5)

3. Attach to a chart:
   - Open a chart (e.g., XAUUSD M1)
   - Drag the EA from Navigator onto the chart
   - Configure parameters in the EA settings dialog
   - Enable "Allow live trading" if using real account

## Parameter Synchronization

Each EA has the same parameters as the Python strategy:
- `EMA_FAST` — Fast EMA period (default 21)
- `EMA_SLOW` — Slow EMA period (default 50)
- `EXIT_PCT_BELOW_EMA` — Exit threshold (default 0.3%)
- `ALLOW_SHORT` — Enable short selling (default false)
- `RISK_PERCENT` — Risk per trade (default 1.0%)

These can be synchronized with the Python bot via JSON files if needed.

## Strategy Details

See individual strategy README files for:
- Entry/exit logic
- Parameter explanations
- Backtesting results
- Known limitations

## Notes

- Each EA is **symbol-agnostic** — it works on any chart it's attached to
- Timeframe is also automatic — determined by the chart timeframe
- All EAs use the same core logic as the Python implementation
- Backtesting recommended before live trading
