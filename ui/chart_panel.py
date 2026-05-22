"""
ui/chart_panel.py
------------------
Live candlestick chart using native Tkinter Canvas.
"""

import tkinter as tk
from tkinter import ttk
import pandas as pd
import numpy as np
from utils.logger import get_logger

logger = get_logger(__name__)


class ChartPanel(tk.Frame):

    def __init__(self, parent, theme: dict):
        super().__init__(parent, bg=theme["bg"])
        self.theme = theme
        self.num_candles = 50
        self._df = None
        self._current_price = None

        # Controls bar
        bar = tk.Frame(self, bg=theme["bg_panel"])
        bar.pack(fill=tk.X, padx=4, pady=4)

        tk.Label(bar, text="Candles:", bg=theme["bg_panel"],
                 fg=theme["text_dim"], font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=8)

        self._candle_var = tk.StringVar(value="50")
        for n in [20, 50, 100, 200]:
            tk.Radiobutton(
                bar, text=str(n), variable=self._candle_var, value=str(n),
                bg=theme["bg_panel"], fg=theme["text"],
                selectcolor=theme["accent2"],
                activebackground=theme["bg_panel"],
                font=("Segoe UI", 9),
                command=lambda: self._canvas.after(50, self._draw),
            ).pack(side=tk.LEFT, padx=4)

        self._title_var = tk.StringVar(value="Start bot to see chart")
        tk.Label(bar, textvariable=self._title_var,
                 bg=theme["bg_panel"], fg=theme["green"],
                 font=("Segoe UI", 10, "bold")).pack(side=tk.RIGHT, padx=12)

        # Canvas — same as test_chart4
        self._canvas = tk.Canvas(self, bg=theme["bg_panel"], highlightthickness=0)
        self._canvas.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

    def update(self, df, current_price, indicators, symbol, timeframe):
        """Store data and schedule draw."""
        if df is None or len(df) < 10:
            return
        self._df = df.copy()
        self._current_price = current_price
        self._title_var.set(f"{symbol} {timeframe}  |  Price: {current_price:.2f}")
        self._canvas.after(50, self._draw)

    def force_redraw(self):
        """Called when tab is selected."""
        self._canvas.after(100, self._draw)

    def _draw(self):
        """Draw candles and EMAs on canvas."""
        if self._df is None:
            return

        c = self._canvas
        c.update_idletasks()
        W = c.winfo_width()
        H = c.winfo_height()

        if W < 10 or H < 10:
            c.after(200, self._draw)
            return

        c.delete("all")
        T = self.theme

        try:
            self.num_candles = int(self._candle_var.get())
        except Exception:
            pass

        df = self._df.tail(self.num_candles).reset_index(drop=True)
        n = len(df)
        if n == 0:
            return

        # Margins
        ML, MR, MT, MB = 65, 15, 15, 30
        PW = W - ML - MR
        PH = H - MT - MB

        # Price range
        lo = df["low"].min()
        hi = df["high"].max()
        if "ema_fast" in df.columns:
            lo = min(lo, df["ema_fast"].dropna().min() if len(df["ema_fast"].dropna()) else lo)
            hi = max(hi, df["ema_fast"].dropna().max() if len(df["ema_fast"].dropna()) else hi)
        if "ema_slow" in df.columns:
            lo = min(lo, df["ema_slow"].dropna().min() if len(df["ema_slow"].dropna()) else lo)
            hi = max(hi, df["ema_slow"].dropna().max() if len(df["ema_slow"].dropna()) else hi)
        if self._current_price:
            lo = min(lo, self._current_price)
            hi = max(hi, self._current_price)

        rng = hi - lo
        if rng < 1e-6:
            rng = 1.0
        lo -= rng * 0.05
        hi += rng * 0.05
        rng = hi - lo

        def py(price):
            return MT + PH * (1.0 - (price - lo) / rng)

        def px(i):
            return ML + (i + 0.5) * PW / n

        cw = max(2, PW / n * 0.6)

        # Grid
        for i in range(5):
            y = MT + i * PH / 4
            price = hi - i * rng / 4
            c.create_line(ML, y, W - MR, y, fill=T["border"], dash=(2, 4))
            c.create_text(ML - 4, y, text=f"{price:.1f}",
                         fill=T["text_dim"], font=("Consolas", 8), anchor="e")

        # Candles
        for i, row in df.iterrows():
            o = float(row["open"])
            cl = float(row["close"])
            h = float(row["high"])
            l = float(row["low"])
            x = px(i)
            color = T["green"] if cl >= o else T["red"]

            c.create_line(x, py(h), x, py(l), fill=color, width=1)

            y1 = py(max(o, cl))
            y2 = py(min(o, cl))
            if abs(y2 - y1) < 1:
                y1 -= 1
                y2 += 1
            c.create_rectangle(x - cw/2, y1, x + cw/2, y2,
                               fill=color, outline=color)

        # EMA Fast
        if "ema_fast" in df.columns:
            pts = []
            for i, row in df.iterrows():
                v = row["ema_fast"]
                if not pd.isna(v):
                    pts += [px(i), py(float(v))]
            if len(pts) >= 4:
                c.create_line(*pts, fill=T["green"], width=2, smooth=True)
                c.create_text(W - MR - 2, pts[-1],
                             text="EMA F", fill=T["green"],
                             font=("Consolas", 8), anchor="e")

        # EMA Slow
        if "ema_slow" in df.columns:
            pts = []
            for i, row in df.iterrows():
                v = row["ema_slow"]
                if not pd.isna(v):
                    pts += [px(i), py(float(v))]
            if len(pts) >= 4:
                c.create_line(*pts, fill=T["accent2"], width=2,
                             smooth=True, dash=(6, 3))
                c.create_text(W - MR - 2, pts[-1] + 12,
                             text="EMA S", fill=T["accent2"],
                             font=("Consolas", 8), anchor="e")

        # Current price line
        if self._current_price:
            y = py(self._current_price)
            c.create_line(ML, y, W - MR, y,
                         fill=T["yellow"], width=1, dash=(4, 4))
            c.create_text(ML - 4, y, text=f"{self._current_price:.1f}",
                         fill=T["yellow"], font=("Consolas", 8, "bold"), anchor="e")

        # Border
        c.create_rectangle(ML, MT, W - MR, H - MB, outline=T["border"])
