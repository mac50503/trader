"""
ui/pattern_visualizer.py
------------------------
Pattern Visualizer - Shows example candle patterns for each strategy.

Displays:
- Example candles that match the strategy's entry conditions
- Key price levels (PCD, EMA, breakout points, etc.)
- Annotations explaining what the strategy detects
"""

import tkinter as tk
from tkinter import ttk
import pandas as pd
import numpy as np

from utils.indicators import compute_all
from utils.logger import get_logger

logger = get_logger(__name__)


class PatternVisualizer(tk.Toplevel):
    """
    Toplevel window showing example candle patterns for strategies.
    """

    def __init__(self, parent, strategy_name="Change of Direction", snapshot: dict = None):
        super().__init__(parent)
        self.title(f"Pattern Visualizer — {strategy_name}")
        self.geometry("900x620")
        self.resizable(True, True)
        self.strategy_name = strategy_name
        self.snapshot = snapshot or {}

        self._create_widgets()

        # ✅ Esperar a que la ventana esté completamente renderizada antes de dibujar
        self.after(100, self._generate_and_draw_pattern)

    # ── Widgets ───────────────────────────────────────────────────────────────

    def _create_widgets(self):
        """Build the window layout."""
        T = {
            "bg":       "#1a1a2e",
            "bg_card":  "#0f3460",
            "text":     "#eaeaea",
            "text_dim": "#8892a4",
            "green":    "#00d4aa",
            "red":      "#ff4757",
            "yellow":   "#ffa502",
            "blue":     "#4a9eff",
            "orange":   "#ff8c00",
        }
        self._T = T
        self.configure(bg=T["bg"])

        # ── Title bar ─────────────────────────────────────────────────────
        title_frame = tk.Frame(self, bg=T["bg_card"], height=40)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)

        tk.Label(
            title_frame,
            text=f"📊  Entry Pattern — {self.strategy_name}",
            bg=T["bg_card"], fg=T["text"],
            font=("Segoe UI", 12, "bold"),
        ).pack(side=tk.LEFT, padx=12, pady=8)

        # ── Canvas (chart area) ───────────────────────────────────────────
        canvas_frame = tk.Frame(self, bg=T["bg"], bd=0)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 4))

        self.canvas = tk.Canvas(
            canvas_frame,
            bg="#0d1117",
            highlightthickness=1,
            highlightbackground=T["bg_card"],
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # ── Info panel (bottom) ───────────────────────────────────────────
        info_frame = tk.Frame(self, bg=T["bg_card"], bd=0)
        info_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.info_text = tk.Text(
            info_frame,
            height=7,
            bg=T["bg_card"], fg=T["text"],
            font=("Consolas", 9),
            relief=tk.FLAT,
            wrap=tk.WORD,
            padx=10, pady=6,
        )
        self.info_text.pack(fill=tk.BOTH, expand=True)

        # Color tags for info text
        self.info_text.tag_config("header",  foreground=T["yellow"], font=("Consolas", 9, "bold"))
        self.info_text.tag_config("ok",      foreground=T["green"])
        self.info_text.tag_config("label",   foreground=T["text_dim"])
        self.info_text.tag_config("value",   foreground=T["text"])

    # ── Pattern Generation ────────────────────────────────────────────────────

    def _generate_and_draw_pattern(self):
        """Generate example candles and draw them on the canvas."""
        # Forzar actualización del canvas para obtener tamaño real
        self.canvas.update_idletasks()
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()

        # Si el canvas aún no tiene tamaño, reintentar
        if w <= 1 or h <= 1:
            self.after(100, self._generate_and_draw_pattern)
            return

        # If we have a real snapshot from the live strategy, use it
        if self.snapshot and "direction" in self.snapshot:
            self._draw_from_snapshot(w, h)
        elif "Change of Direction" in self.strategy_name:
            self._draw_cod_pattern(w, h)
        elif "EMA" in self.strategy_name:
            self._draw_ema_pattern(w, h)
        else:
            self._draw_cod_pattern(w, h)

    # ── Snapshot Drawing ──────────────────────────────────────────────────────

    def _draw_from_snapshot(self, w, h):
        """Draw the last real detected pattern from the live strategy."""
        T = self._T
        s = self.snapshot
        direction = s["direction"]

        point_1   = s.get("point_1")
        point_2   = s.get("point_2")
        entry     = s.get("entry")
        sl        = s.get("stop_loss")
        tp        = s.get("take_profit")
        risk      = s.get("risk", 0)

        if direction == "SELL":
            pb1_high = s.get("pullback1_high")
            pb2_high = s.get("pullback2_high")

            # Build synthetic candles that represent the pattern levels
            candles = [
                # open,      high,        low,         close,       role
                (pb1_high,   pb1_high*1.001, point_1*0.999, point_1*1.001, "red1"),
                (point_1*1.001, point_1*1.002, point_1*0.998, point_1*0.999, "red2"),
                (point_1*0.999, pb1_high*0.999, point_1*0.998, pb1_high*0.998, "green1_pb1"),
                (pb1_high*0.998, pb1_high,      point_1*0.999, pb1_high*0.997, "green2_pb1"),
                (pb1_high*0.997, pb1_high*0.998, point_2*1.001, point_2*1.002, "break"),
                (point_2*1.002, point_2*1.005,  point_2*0.999, point_2*1.003, "green1_pb2"),
                (point_2*1.003, point_2*1.006,  point_2*1.001, point_2*1.004, "green2_pb2"),
                (point_2*1.004, pb2_high,        entry*0.999,   entry,         "entry"),
            ]

            h_lines = [
                (point_1,   T["yellow"], f"POINT 1 = {point_1:.2f}",   "dashed"),
                (pb1_high,  "#888888",   f"pullback1_high = {pb1_high:.2f}", "dotted"),
                (point_2,   T["orange"], f"POINT 2 = {point_2:.2f}",   "dashed"),
                (sl,        "#ff6b6b",   f"SL = {sl:.2f}",             "dotted"),
                (entry,     T["red"],    f"ENTRY = {entry:.2f}",       "solid"),
                (tp,        T["green"],  f"TP = {tp:.2f}",             "dotted"),
            ]

            self._draw_candle_chart(candles, w, h, h_lines=h_lines, entry_idx=7, entry_dir="SELL")

            self.info_text.config(state=tk.NORMAL)
            self.info_text.delete(1.0, tk.END)
            lines = [
                ("LAST DETECTED PATTERN — SELL (real data)\n", "header"),
                ("\n", "value"),
                (f"POINT 1 = {point_1:.5f}  ", "label"),
                (f"(lowest low of initial red candles)\n", "value"),
                (f"pullback1_high = {pb1_high:.5f}  ", "label"),
                (f"(reset reference for second pullback)\n", "value"),
                (f"POINT 2 = {point_2:.5f}  ", "label"),
                (f"(lowest low of second pullback)\n", "value"),
                (f"ENTRY = {entry:.5f}  SL = {sl:.5f}  TP = {tp:.5f}\n", "ok"),
                (f"Risk = {risk:.5f}  Reward = {risk*2:.5f}  Ratio = 1:2\n", "value"),
            ]
            for text, tag in lines:
                self.info_text.insert(tk.END, text, tag)
            self.info_text.config(state=tk.DISABLED)

        else:  # BUY
            pb1_low  = s.get("pullback1_low")
            pb2_low  = s.get("pullback2_low")

            candles = [
                (pb1_low*0.999, point_1*1.001, pb1_low*0.998, point_1*0.999, "green1_pb1"),
                (point_1*0.999, point_1*1.001, pb1_low*0.999, point_1*1.001, "green2_pb1"),
                (point_1*1.001, point_1*1.002, pb1_low*1.001, pb1_low*1.002, "break"),
                (pb1_low*1.002, point_2*0.999, pb1_low*1.001, point_2*0.998, "red1_pb2"),
                (point_2*0.998, point_2*0.999, pb2_low*1.001, point_2*0.997, "red2_pb2"),
                (point_2*0.997, entry*1.001,   point_2*0.998, entry,          "entry"),
            ]

            h_lines = [
                (point_1,  T["yellow"], f"POINT 1 = {point_1:.2f}",  "dashed"),
                (pb1_low,  "#888888",   f"pullback1_low = {pb1_low:.2f}", "dotted"),
                (point_2,  T["orange"], f"POINT 2 = {point_2:.2f}",  "dashed"),
                (sl,       "#ff6b6b",   f"SL = {sl:.2f}",            "dotted"),
                (entry,    T["green"],  f"ENTRY = {entry:.2f}",      "solid"),
                (tp,       T["green"],  f"TP = {tp:.2f}",            "dotted"),
            ]

            self._draw_candle_chart(candles, w, h, h_lines=h_lines, entry_idx=5, entry_dir="BUY")

            self.info_text.config(state=tk.NORMAL)
            self.info_text.delete(1.0, tk.END)
            lines = [
                ("LAST DETECTED PATTERN — BUY (real data)\n", "header"),
                ("\n", "value"),
                (f"POINT 1 = {point_1:.5f}  ", "label"),
                (f"(highest high of initial green candles)\n", "value"),
                (f"POINT 2 = {point_2:.5f}  ", "label"),
                (f"(highest high of second pullback)\n", "value"),
                (f"ENTRY = {entry:.5f}  SL = {sl:.5f}  TP = {tp:.5f}\n", "ok"),
                (f"Risk = {risk:.5f}  Reward = {risk*2:.5f}  Ratio = 1:2\n", "value"),
            ]
            for text, tag in lines:
                self.info_text.insert(tk.END, text, tag)
            self.info_text.config(state=tk.DISABLED)

    # ── COD Pattern ───────────────────────────────────────────────────────────

    def _draw_cod_pattern(self, w, h):
        """Draw Change of Direction SELL pattern — 4 phases."""
        T = self._T
        self.canvas.delete("all")

        # ── Candle data: 4-phase pattern ─────────────────────────────────
        #
        #  idx  role              open     high     low      close
        #   0   RED #1 (PHASE1)  2335.00  2335.50  2330.00  2330.50  ← first red, reset=2335.50
        #   1   RED #2 (PHASE1)  2330.50  2331.00  2326.00  2326.50  ← point_1 = 2326.00
        #   2   GREEN #1 (PH2)   2326.50  2333.00  2326.00  2332.50  ← pullback1, exceeded (2332.50>2335.00? no)
        #   3   GREEN #2 (PH2)   2332.50  2336.00  2332.00  2335.50  ← pullback1_high=2336, exceeded ✓
        #   4   RED (PH3)        2335.50  2336.00  2323.00  2323.50  ← close < point_1(2326) → PHASE4
        #   5   GREEN #1 (PH4)   2323.50  2328.00  2323.00  2327.50  ← pullback2_high=2328, point_2=2323
        #   6   GREEN #2 (PH4)   2327.50  2329.00  2325.00  2328.50  ← pullback2_high=2329, point_2=2323
        #   7   RED (PH5)        2328.50  2329.00  2320.00  2321.00  ← close=2321 <= point_2=2323 → SELL

        candles = [
            # open,    high,    low,     close,   role
            (2335.00, 2335.50, 2330.00, 2330.50, "red1"),
            (2330.50, 2331.00, 2326.00, 2326.50, "red2"),
            (2326.50, 2333.00, 2326.00, 2332.50, "green1_pb1"),
            (2332.50, 2336.00, 2332.00, 2335.50, "green2_pb1"),
            (2335.50, 2336.00, 2323.00, 2323.50, "break"),
            (2323.50, 2328.00, 2323.00, 2327.50, "green1_pb2"),
            (2327.50, 2329.00, 2325.00, 2328.50, "green2_pb2"),
            (2328.50, 2329.00, 2320.00, 2321.00, "entry"),
        ]

        point_1          = 2326.00   # low of red candles
        first_red_open   = 2335.00   # open of first red
        pullback1_high   = 2336.00   # high of first pullback
        point_2          = 2323.00   # low of second pullback
        pullback2_high   = 2329.00   # high of second pullback → SL
        entry_px         = 2321.00   # close of entry candle
        sl_price         = pullback2_high
        tp_price         = entry_px - (sl_price - entry_px) * 2.0

        self._draw_candle_chart(
            candles, w, h,
            h_lines=[
                (first_red_open, "#aaaaaa",  "open_first_red = 2335.00", "dotted"),
                (point_1,        T["yellow"], "POINT 1 = 2326.00",        "dashed"),
                (pullback1_high, "#888888",   "pullback1_high = 2336.00", "dotted"),
                (point_2,        T["orange"], "POINT 2 = 2323.00",        "dashed"),
                (sl_price,       "#ff6b6b",   f"SL = {sl_price:.2f}",     "dotted"),
                (entry_px,       T["red"],    f"ENTRY = {entry_px:.2f}",  "solid"),
                (tp_price,       T["green"],  f"TP = {tp_price:.2f}",     "dotted"),
            ],
            entry_idx=7,
            entry_dir="SELL",
            phase_labels=[
                (0, "PHASE 1\n2 reds"),
                (2, "PHASE 2\npullback 1"),
                (4, "PHASE 3\nbreak p1"),
                (5, "PHASE 4\npullback 2"),
                (7, "ENTRY\nSELL"),
            ],
        )

        self.info_text.config(state=tk.NORMAL)
        self.info_text.delete(1.0, tk.END)

        lines = [
            ("CHANGE OF DIRECTION — SELL PATTERN (4 phases)\n", "header"),
            ("\n", "value"),
            ("① PHASE 1 — Consecutive reds  ", "label"),
            ("Candles 1-2: 2 consecutive RED  →  ", "value"),
            ("point_1 = 2326.00 (lowest low)\n", "ok"),
            ("\n", "value"),
            ("② PHASE 2 — First pullback  ", "label"),
            ("Candles 3-4: 2+ greens, close(2335.50) > open_first_red(2335.00) ✓  →  ", "value"),
            ("pullback1_high = 2336.00\n", "ok"),
            ("\n", "value"),
            ("③ PHASE 3 — Break of point_1  ", "label"),
            ("Candle 5: close(2323.50) < point_1(2326.00) ✓  →  ", "value"),
            ("confirmed bearish continuation\n", "ok"),
            ("\n", "value"),
            ("④ PHASE 4 — Second pullback  ", "label"),
            ("Candles 6-7: 2+ greens  →  ", "value"),
            ("point_2 = 2323.00  |  SL = pullback2_high = 2329.00\n", "ok"),
            ("\n", "value"),
            ("⑤ ENTRY  ", "label"),
            ("Candle 8: close(2321.00) ≤ point_2(2323.00) ✓  →  ", "value"),
            ("SELL @ 2321.00   SL=2329.00   TP=2305.00   risk=8   reward=16 (1:2)\n", "ok"),
        ]
        for text, tag in lines:
            self.info_text.insert(tk.END, text, tag)
        self.info_text.config(state=tk.DISABLED)

    # ── EMA Pattern ───────────────────────────────────────────────────────────

    def _draw_ema_pattern(self, w, h):
        """Draw EMA Pullback Pro BUY pattern."""
        T = self._T
        self.canvas.delete("all")

        # Uptrend: EMA_fast > EMA_slow, vela toca EMA y rebota arriba
        candles = [
            (2320.00, 2322.00, 2319.00, 2321.50, "context"),
            (2321.50, 2323.00, 2320.50, 2322.80, "context"),
            (2322.80, 2324.50, 2322.00, 2324.00, "context"),
            (2324.00, 2325.50, 2323.20, 2325.00, "context"),
            (2325.00, 2326.00, 2323.50, 2323.80, "touch"),   # toca EMA
            (2323.80, 2327.00, 2323.60, 2326.50, "entry"),   # bounce + entry
        ]

        ema_fast = 2324.00   # entre open y close de la vela touch
        ema_slow = 2321.00   # por debajo → uptrend confirmado

        # Construir puntos de EMA para dibujar la línea
        ema_fast_vals = [2321.50, 2322.20, 2322.90, 2323.50, 2324.00, 2324.80]
        ema_slow_vals = [2319.50, 2320.00, 2320.50, 2321.00, 2321.00, 2321.50]

        self._draw_candle_chart(
            candles, w, h,
            h_lines=[
                (ema_fast, T["blue"],   "EMA Fast (21) = 2324.00", "dashed"),
                (ema_slow, T["orange"], "EMA Slow (50) = 2321.00", "dashed"),
            ],
            entry_idx=5,
            entry_dir="BUY",
            ema_fast_vals=ema_fast_vals,
            ema_slow_vals=ema_slow_vals,
        )

        self.info_text.config(state=tk.NORMAL)
        self.info_text.delete(1.0, tk.END)

        lines = [
            ("EMA PULLBACK PRO — BUY PATTERN\n", "header"),
            ("\n", "value"),
            ("① TREND CONFIRMATION  ", "label"),
            ("EMA_fast(2324.00) > EMA_slow(2321.00) ✓  →  ", "value"),
            ("Uptrend confirmed\n", "ok"),
            ("\n", "value"),
            ("② EMA TOUCH  ", "label"),
            ("Candle 5: open(2325.00) > EMA(2324.00) > close(2323.80) ✓  →  ", "value"),
            ("EMA between open and close\n", "ok"),
            ("\n", "value"),
            ("③ BOUNCE CONFIRMATION  ", "label"),
            ("Candle 6: close(2326.50) > EMA_fast(2324.00) ✓  →  ", "value"),
            ("BUY @ 2326.50\n", "ok"),
            ("   Trailing SL = 2326.50 × (1 − 0.3%) = 2319.67   |   Moves up with price\n", "value"),
        ]
        for text, tag in lines:
            self.info_text.insert(tk.END, text, tag)
        self.info_text.config(state=tk.DISABLED)

    # ── Core Drawing Engine ───────────────────────────────────────────────────

    def _draw_candle_chart(
        self, candles, w, h,
        h_lines=None,
        entry_idx=None,
        entry_dir="BUY",
        ema_fast_vals=None,
        ema_slow_vals=None,
        phase_labels=None,
    ):
        """
        Draw candlesticks + horizontal reference lines + EMA curves.

        candles: list of (open, high, low, close, role)
        h_lines: list of (price, color, label, style)
        """
        T = self._T
        h_lines = h_lines or []

        # ── Price range ───────────────────────────────────────────────────
        all_prices = [p for c in candles for p in (c[0], c[1], c[2], c[3])]
        if h_lines:
            all_prices += [hl[0] for hl in h_lines]

        price_min = min(all_prices)
        price_max = max(all_prices)
        price_pad = (price_max - price_min) * 0.15
        price_min -= price_pad
        price_max += price_pad
        price_range = price_max - price_min

        # ── Layout margins ────────────────────────────────────────────────
        ml = 70    # left  (price labels)
        mr = 160   # right (line labels)
        mt = 20    # top
        mb = 30    # bottom (candle numbers)

        pw = w - ml - mr   # plot width
        ph = h - mt - mb   # plot height

        n = len(candles)
        slot_w = pw / (n + 1)
        body_w = max(slot_w * 0.55, 6)

        def to_y(price):
            return mt + ph * (1.0 - (price - price_min) / price_range)

        def to_x(i):
            return ml + (i + 1) * slot_w

        # ── Background grid ───────────────────────────────────────────────
        for k in range(6):
            price = price_min + price_range * k / 5
            y = to_y(price)
            self.canvas.create_line(ml, y, ml + pw, y,
                                    fill="#1e2a3a", width=1)
            self.canvas.create_text(ml - 6, y,
                                    text=f"{price:.2f}",
                                    anchor=tk.E,
                                    fill=T["text_dim"],
                                    font=("Consolas", 8))

        # ── Horizontal reference lines ────────────────────────────────────
        for price, color, label, style in h_lines:
            y = to_y(price)
            dash = (6, 4) if style == "dashed" else (2, 3) if style == "dotted" else None
            kw = {"fill": color, "width": 1}
            if dash:
                kw["dash"] = dash
            self.canvas.create_line(ml, y, ml + pw, y, **kw)
            self.canvas.create_text(
                ml + pw + 6, y,
                text=label, anchor=tk.W,
                fill=color, font=("Consolas", 8),
            )

        # ── EMA lines ─────────────────────────────────────────────────────
        if ema_fast_vals and len(ema_fast_vals) == n:
            pts = [(to_x(i), to_y(v)) for i, v in enumerate(ema_fast_vals)]
            for i in range(len(pts) - 1):
                self.canvas.create_line(
                    pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1],
                    fill=T["blue"], width=2, dash=(5, 3),
                )

        if ema_slow_vals and len(ema_slow_vals) == n:
            pts = [(to_x(i), to_y(v)) for i, v in enumerate(ema_slow_vals)]
            for i in range(len(pts) - 1):
                self.canvas.create_line(
                    pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1],
                    fill=T["orange"], width=2, dash=(5, 3),
                )

        # ── Candles ───────────────────────────────────────────────────────
        role_colors = {
            "context":   ("#4a9eff", "#2a5a8f"),   # azul tenue
            "red1":      ("#ff4757", "#cc2233"),
            "red2":      ("#ff4757", "#cc2233"),
            "green_pcd": ("#00d4aa", "#009977"),
            "touch":     ("#ffa502", "#cc7700"),
            "breakout":  ("#ff6b35", "#cc4400"),
            "entry":     ("#ff4757", "#cc2233"),
        }

        for i, (open_p, high, low, close, role) in enumerate(candles):
            x = to_x(i)
            y_open  = to_y(open_p)
            y_close = to_y(close)
            y_high  = to_y(high)
            y_low   = to_y(low)

            is_bull = close >= open_p
            fill_c, outline_c = role_colors.get(role, ("#eaeaea", "#aaaaaa"))

            # Highlight entry candle
            if i == entry_idx:
                # Glow effect
                self.canvas.create_rectangle(
                    x - body_w / 2 - 3, min(y_open, y_close) - 3,
                    x + body_w / 2 + 3, max(y_open, y_close) + 3,
                    fill="", outline=T["yellow"], width=2,
                )

            # Wick
            self.canvas.create_line(x, y_high, x, y_low,
                                    fill=outline_c, width=1)

            # Body
            y_top = min(y_open, y_close)
            y_bot = max(y_open, y_close)
            if y_bot - y_top < 2:
                y_bot = y_top + 2   # mínimo visible

            self.canvas.create_rectangle(
                x - body_w / 2, y_top,
                x + body_w / 2, y_bot,
                fill=fill_c, outline=outline_c, width=1,
            )

            # Candle number label
            self.canvas.create_text(
                x, mt + ph + 14,
                text=str(i + 1),
                fill=T["text_dim"],
                font=("Consolas", 8),
            )

        # ── Entry arrow ───────────────────────────────────────────────────
        if entry_idx is not None:
            x = to_x(entry_idx)
            open_p, high, low, close, _ = candles[entry_idx]

            if entry_dir == "SELL":
                # Arrow pointing down above the candle
                y_tip = to_y(high) - 8
                arrow_color = T["red"]
                label = "▼ SELL"
                anchor = tk.S
            else:
                # Arrow pointing up below the candle
                y_tip = to_y(low) + 8
                arrow_color = T["green"]
                label = "▲ BUY"
                anchor = tk.N

            self.canvas.create_text(
                x, y_tip,
                text=label,
                fill=arrow_color,
                font=("Segoe UI", 10, "bold"),
                anchor=anchor,
            )

        # ── Phase labels (top of each phase) ─────────────────────────────
        if phase_labels:
            for idx, label in phase_labels:
                x = to_x(idx)
                self.canvas.create_text(
                    x, mt + 4,
                    text=label,
                    fill=T["yellow"],
                    font=("Consolas", 7),
                    anchor=tk.N,
                    justify=tk.CENTER,
                )

        # ── Legend (top-left) ─────────────────────────────────────────────
        legend_items = [
            ("■", T["red"],    "Red candle (bearish)"),
            ("■", T["green"],  "Green candle (bullish)"),
            ("■", T["yellow"], "Entry candle"),
        ]
        if ema_fast_vals:
            legend_items += [
                ("—", T["blue"],   "EMA Fast (21)"),
                ("—", T["orange"], "EMA Slow (50)"),
            ]

        lx, ly = ml + 6, mt + 6
        for sym, color, text in legend_items:
            self.canvas.create_text(lx, ly, text=sym, fill=color,
                                    font=("Consolas", 9), anchor=tk.W)
            self.canvas.create_text(lx + 14, ly, text=text,
                                    fill=T["text_dim"],
                                    font=("Consolas", 8), anchor=tk.W)
            ly += 14
