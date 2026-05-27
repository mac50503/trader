"""
ui/pattern_scanner.py
----------------------
Pattern Scanner — runs the active strategy over historical candles
and shows all detected entry signals in a single pass.

Useful for validating strategy logic without waiting for live data.
"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime
from typing import List, Optional
import pandas as pd

from strategies.strategy_registry import StrategyRegistry
from utils.logger import get_logger
import config

logger = get_logger(__name__)


class PatternScanner(tk.Toplevel):
    """
    Scans historical candles and lists all detected entry signals.
    """

    def __init__(self, parent, strategy_name: str, df: Optional[pd.DataFrame] = None):
        super().__init__(parent)
        self.title(f"Pattern Scanner — {strategy_name}")
        self.geometry("700x500")
        self.resizable(True, True)

        self.strategy_name = strategy_name
        self.df = df

        self._create_widgets()
        self.after(100, self._run_scan)

    # ── Widgets ───────────────────────────────────────────────────────────────

    def _create_widgets(self):
        T = {
            "bg":       "#1a1a2e",
            "bg_card":  "#0f3460",
            "text":     "#eaeaea",
            "text_dim": "#8892a4",
            "green":    "#00d4aa",
            "red":      "#ff4757",
            "yellow":   "#ffa502",
        }
        self._T = T
        self.configure(bg=T["bg"])

        # ── Title bar ─────────────────────────────────────────────────────
        title_frame = tk.Frame(self, bg=T["bg_card"], height=40)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)

        self._title_label = tk.Label(
            title_frame,
            text=f"🔍  Pattern Scanner — {self.strategy_name}",
            bg=T["bg_card"], fg=T["text"],
            font=("Segoe UI", 12, "bold"),
        )
        self._title_label.pack(side=tk.LEFT, padx=12, pady=8)

        self._status_label = tk.Label(
            title_frame,
            text="Scanning...",
            bg=T["bg_card"], fg=T["yellow"],
            font=("Segoe UI", 9),
        )
        self._status_label.pack(side=tk.RIGHT, padx=12, pady=8)

        # ── Summary bar ───────────────────────────────────────────────────
        self._summary_frame = tk.Frame(self, bg=T["bg_card"], height=30)
        self._summary_frame.pack(fill=tk.X, padx=10, pady=(8, 0))
        self._summary_frame.pack_propagate(False)

        self._summary_label = tk.Label(
            self._summary_frame,
            text="",
            bg=T["bg_card"], fg=T["text"],
            font=("Consolas", 9),
        )
        self._summary_label.pack(side=tk.LEFT, padx=10, pady=5)

        # ── Results table ─────────────────────────────────────────────────
        table_frame = tk.Frame(self, bg=T["bg"])
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        # Scrollbar
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Treeview
        columns = ("#", "Direction", "Entry", "SL", "TP", "Risk", "Candle", "Time")
        self._tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            yscrollcommand=scrollbar.set,
        )
        scrollbar.config(command=self._tree.yview)

        # Column widths
        widths = [35, 65, 85, 85, 85, 65, 60, 130]
        for col, w in zip(columns, widths):
            self._tree.heading(col, text=col)
            self._tree.column(col, width=w, anchor=tk.CENTER)

        self._tree.pack(fill=tk.BOTH, expand=True)

        # Row colors
        style = ttk.Style()
        style.configure("Treeview",
                        background=T["bg_card"],
                        foreground=T["text"],
                        fieldbackground=T["bg_card"],
                        rowheight=24,
                        font=("Consolas", 9))
        style.configure("Treeview.Heading",
                        background=T["bg"],
                        foreground=T["text_dim"],
                        font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", "#533483")])

        self._tree.tag_configure("sell", foreground=T["red"])
        self._tree.tag_configure("buy",  foreground=T["green"])

    # ── Scan Logic ────────────────────────────────────────────────────────────

    def _run_scan(self):
        """Run the strategy over all historical candles and collect signals."""
        if self.df is None or len(self.df) < 10:
            self._status_label.config(text="No data available", fg=self._T["red"])
            self._summary_label.config(text="Start the bot first to load candle data.")
            return

        total_candles = len(self.df)
        self._status_label.config(text=f"Scanning {total_candles} candles...")
        self.update_idletasks()

        # Fresh strategy instance — no state from live trading
        strategy = StrategyRegistry.get_strategy(self.strategy_name)

        signals_found: List[dict] = []

        # Feed candles one by one — same as the live bot does
        for i in range(5, total_candles + 1):
            df_slice = self.df.iloc[:i]
            signal = strategy.generate_signal(df_slice, current_position=None)

            if signal.action in ("BUY", "SELL"):
                candle = df_slice.iloc[-1]
                entry_price = candle["close"]
                candle_time = df_slice.index[-1]

                risk = abs((signal.stop_loss or 0) - entry_price)
                reward = abs((signal.take_profit or 0) - entry_price)

                signals_found.append({
                    "index":      i,
                    "direction":  signal.action,
                    "entry":      entry_price,
                    "sl":         signal.stop_loss,
                    "tp":         signal.take_profit,
                    "risk":       risk,
                    "reward":     reward,
                    "time":       candle_time,
                })

        # ── Populate table ────────────────────────────────────────────────
        self._tree.delete(*self._tree.get_children())

        for n, s in enumerate(signals_found, 1):
            direction = s["direction"]
            tag = "sell" if direction == "SELL" else "buy"
            arrow = "▼ SELL" if direction == "SELL" else "▲ BUY"

            time_str = s["time"].strftime("%m-%d %H:%M:%S") if hasattr(s["time"], "strftime") else str(s["time"])

            self._tree.insert("", tk.END, tags=(tag,), values=(
                n,
                arrow,
                f"{s['entry']:.2f}",
                f"{s['sl']:.2f}"  if s["sl"]  else "—",
                f"{s['tp']:.2f}"  if s["tp"]  else "—",
                f"{s['risk']:.2f}",
                s["index"],
                time_str,
            ))

        # ── Summary ───────────────────────────────────────────────────────
        sells = sum(1 for s in signals_found if s["direction"] == "SELL")
        buys  = sum(1 for s in signals_found if s["direction"] == "BUY")

        if signals_found:
            avg_risk   = sum(s["risk"]   for s in signals_found) / len(signals_found)
            avg_reward = sum(s["reward"] for s in signals_found) / len(signals_found)
            ratio = f"{avg_reward/avg_risk:.1f}" if avg_risk > 0 else "—"
            summary = (
                f"Candles: {total_candles}  |  "
                f"Patterns: {len(signals_found)}  |  "
                f"▼ SELL: {sells}  ▲ BUY: {buys}  |  "
                f"Avg risk: {avg_risk:.2f}  Avg reward: {avg_reward:.2f}  Ratio: 1:{ratio}"
            )
        else:
            summary = f"Candles: {total_candles}  |  No patterns found in this data."

        self._summary_label.config(text=summary)
        self._status_label.config(
            text=f"Done — {len(signals_found)} pattern(s) found",
            fg=self._T["green"] if signals_found else self._T["yellow"],
        )

        logger.info(
            f"Pattern Scanner [{self.strategy_name}]: "
            f"{len(signals_found)} signals in {total_candles} candles "
            f"(SELL={sells} BUY={buys})"
        )
