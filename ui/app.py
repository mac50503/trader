"""
ui/app.py
----------
Main application window — the root Tkinter window.

Responsibilities:
- Create and manage the main window
- Initialize all components (broker, strategy, bot engine, DB)
- Wire up the UI panels
- Handle application lifecycle (start, close)

Architecture note:
    The UI runs in the main thread.
    The bot engine runs in a background thread.
    Communication: bot calls on_event() → UI uses after() to update widgets safely.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
from typing import Optional

from brokers.future_broker import create_broker
from strategies.strategy_registry import StrategyRegistry
from risk_management.risk_manager import RiskManager
from market_data.market_stream import BotEngine
from database.database import Database
from database.trade_repository import TradeRepository
from ui.dashboard import DashboardPanel
from ui.logs_window import LogsPanel
from ui.settings_window import SettingsPanel
from ui.chart_panel import ChartPanel
from utils.logger import get_logger
import config

logger = get_logger(__name__)

# ── Color Theme ───────────────────────────────────────────────────────────────
THEME = {
    "bg":           "#1a1a2e",
    "bg_panel":     "#16213e",
    "bg_card":      "#0f3460",
    "accent":       "#e94560",
    "accent2":      "#533483",
    "text":         "#eaeaea",
    "text_dim":     "#8892a4",
    "green":        "#00d4aa",
    "red":          "#ff4757",
    "yellow":       "#ffa502",
    "border":       "#2d3561",
    "font_main":    ("Segoe UI", 10),
    "font_title":   ("Segoe UI", 12, "bold"),
    "font_mono":    ("Consolas", 9),
}


class TradingBotApp:
    """Main application class — owns the root window and all components."""

    def __init__(self):
        self.root = tk.Tk()
        self._setup_window()
        self._apply_theme()

        # ── Initialize infrastructure ──────────────────────────────────────
        self.db = Database()
        self.db.initialize()
        self.trade_repo = TradeRepository(self.db)

        self.broker = create_broker(initial_balance=10_000.0)
        self.broker.connect()

        self.strategy = StrategyRegistry.get_strategy(config.ACTIVE_STRATEGY)
        self.risk_manager = RiskManager(self.trade_repo)

        self.bot_engine: Optional[BotEngine] = None

        # ── Build UI ───────────────────────────────────────────────────────
        self._build_layout()

        # ── Start periodic UI refresh ──────────────────────────────────────
        self._schedule_ui_refresh()

        logger.info("TradingBotApp initialized")

    # ── Window Setup ──────────────────────────────────────────────────────────

    def _setup_window(self) -> None:
        self.root.title("AlgoTrader Pro — Trend Following Bot")
        self.root.geometry("1280x800")
        self.root.minsize(1024, 700)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _apply_theme(self) -> None:
        self.root.configure(bg=THEME["bg"])
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(".", background=THEME["bg"], foreground=THEME["text"],
                        font=THEME["font_main"])
        style.configure("TFrame", background=THEME["bg"])
        style.configure("TLabel", background=THEME["bg"], foreground=THEME["text"])
        style.configure("TNotebook", background=THEME["bg_panel"],
                        tabmargins=[2, 5, 2, 0])
        style.configure("TNotebook.Tab", background=THEME["bg_card"],
                        foreground=THEME["text"], padding=[12, 4])
        style.map("TNotebook.Tab",
                  background=[("selected", THEME["accent2"])],
                  foreground=[("selected", THEME["text"])])

        # Fix Combobox readonly state — prevents text going blank on focus loss
        style.configure("TCombobox",
                        fieldbackground=THEME["bg_card"],
                        background=THEME["bg_card"],
                        foreground=THEME["text"],
                        selectbackground=THEME["accent2"],
                        selectforeground=THEME["text"],
                        arrowcolor=THEME["text"])
        style.map("TCombobox",
                  fieldbackground=[
                      ("readonly", THEME["bg_card"]),
                      ("disabled", THEME["bg"]),
                  ],
                  foreground=[
                      ("readonly", THEME["text"]),
                      ("disabled", THEME["text_dim"]),
                  ],
                  selectbackground=[("readonly", THEME["accent2"])],
                  selectforeground=[("readonly", THEME["text"])])

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_layout(self) -> None:
        """Build the main window layout."""

        # ── Top bar ────────────────────────────────────────────────────────
        self._build_topbar()

        # ── Main content area ──────────────────────────────────────────────
        main_frame = tk.Frame(self.root, bg=THEME["bg"])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        # Left panel: fixed width, scrollable internally
        left_frame = tk.Frame(main_frame, bg=THEME["bg"], width=310)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        left_frame.pack_propagate(False)

        # Use a canvas+scrollbar so the left panel scrolls if content overflows
        left_canvas = tk.Canvas(left_frame, bg=THEME["bg"],
                                highlightthickness=0, width=295)
        left_scroll = ttk.Scrollbar(left_frame, orient=tk.VERTICAL,
                                    command=left_canvas.yview)
        left_inner = tk.Frame(left_canvas, bg=THEME["bg"])

        left_inner.bind(
            "<Configure>",
            lambda e: left_canvas.configure(
                scrollregion=left_canvas.bbox("all")
            )
        )
        left_canvas.create_window((0, 0), window=left_inner, anchor=tk.NW)
        left_canvas.configure(yscrollcommand=left_scroll.set)

        left_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        left_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind mousewheel to scroll
        def _on_mousewheel(event):
            left_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        left_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        self._build_control_panel(left_inner)
        self._build_stats_panel(left_inner)

        # Right panel: tabbed content
        right_frame = tk.Frame(main_frame, bg=THEME["bg"])
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._build_tabs(right_frame)

    def _build_topbar(self) -> None:
        """Top bar with title and connection status."""
        bar = tk.Frame(self.root, bg=THEME["bg_card"], height=50)
        bar.pack(fill=tk.X, padx=0, pady=0)
        bar.pack_propagate(False)

        tk.Label(
            bar, text="⚡ AlgoTrader Pro",
            bg=THEME["bg_card"], fg=THEME["accent"],
            font=("Segoe UI", 14, "bold"),
        ).pack(side=tk.LEFT, padx=16, pady=10)

        tk.Label(
            bar, text="Trend Following | Gold · Nasdaq · SP500",
            bg=THEME["bg_card"], fg=THEME["text_dim"],
            font=THEME["font_main"],
        ).pack(side=tk.LEFT, padx=8)

        # Status indicator
        self._status_label = tk.Label(
            bar, text="● STOPPED",
            bg=THEME["bg_card"], fg=THEME["red"],
            font=("Segoe UI", 10, "bold"),
        )
        self._status_label.pack(side=tk.RIGHT, padx=16)

        # Broker mode badge
        mode_text = f"[{config.BROKER_NAME.upper()} / {config.BROKER_MODE.upper()}]"
        tk.Label(
            bar, text=mode_text,
            bg=THEME["bg_card"], fg=THEME["yellow"],
            font=THEME["font_mono"],
        ).pack(side=tk.RIGHT, padx=8)

    def _build_control_panel(self, parent: tk.Frame) -> None:
        """Bot control buttons."""
        frame = tk.LabelFrame(
            parent, text=" Bot Controls ",
            bg=THEME["bg_panel"], fg=THEME["text"],
            font=THEME["font_title"], bd=1, relief=tk.FLAT,
        )
        frame.pack(fill=tk.X, pady=(0, 8))

        # Symbol selector
        sym_frame = tk.Frame(frame, bg=THEME["bg_panel"])
        sym_frame.pack(fill=tk.X, padx=8, pady=4)
        tk.Label(sym_frame, text="Symbol:", bg=THEME["bg_panel"],
                 fg=THEME["text_dim"]).pack(side=tk.LEFT)
        self._symbol_var = tk.StringVar(value=config.DEFAULT_SYMBOL)
        sym_combo = ttk.Combobox(
            sym_frame, textvariable=self._symbol_var,
            values=config.SUPPORTED_SYMBOLS, width=10, state="readonly",
        )
        sym_combo.pack(side=tk.LEFT, padx=8)
        sym_combo.bind("<<ComboboxSelected>>", lambda e: sym_combo.selection_clear())

        # Timeframe selector
        tf_frame = tk.Frame(frame, bg=THEME["bg_panel"])
        tf_frame.pack(fill=tk.X, padx=8, pady=4)
        tk.Label(tf_frame, text="Timeframe:", bg=THEME["bg_panel"],
                 fg=THEME["text_dim"]).pack(side=tk.LEFT)
        self._tf_var = tk.StringVar(value=config.DEFAULT_TIMEFRAME)
        tf_combo = ttk.Combobox(
            tf_frame, textvariable=self._tf_var,
            values=config.SUPPORTED_TIMEFRAMES, width=8, state="readonly",
        )
        tf_combo.pack(side=tk.LEFT, padx=8)
        tf_combo.bind("<<ComboboxSelected>>", lambda e: tf_combo.selection_clear())

        # Control buttons
        btn_frame = tk.Frame(frame, bg=THEME["bg_panel"])
        btn_frame.pack(fill=tk.X, padx=8, pady=8)

        self._btn_start = self._make_button(
            btn_frame, "▶ START", THEME["green"], self._on_start
        )
        self._btn_start.pack(fill=tk.X, pady=2)

        self._btn_pause = self._make_button(
            btn_frame, "⏸ PAUSE", THEME["yellow"], self._on_pause
        )
        self._btn_pause.pack(fill=tk.X, pady=2)
        self._btn_pause.config(state=tk.DISABLED)

        self._btn_stop = self._make_button(
            btn_frame, "⏹ STOP", THEME["red"], self._on_stop
        )
        self._btn_stop.pack(fill=tk.X, pady=2)
        self._btn_stop.config(state=tk.DISABLED)

        self._btn_restart = self._make_button(
            btn_frame, "↺ RESTART", THEME["accent2"], self._on_restart
        )
        self._btn_restart.pack(fill=tk.X, pady=2)
        self._btn_restart.config(state=tk.DISABLED)

        # Manual trading
        sep = tk.Frame(frame, bg=THEME["border"], height=1)
        sep.pack(fill=tk.X, padx=8, pady=4)

        tk.Label(frame, text="Manual Trading",
                 bg=THEME["bg_panel"], fg=THEME["text_dim"],
                 font=("Segoe UI", 9)).pack(padx=8, anchor=tk.W)

        lot_frame = tk.Frame(frame, bg=THEME["bg_panel"])
        lot_frame.pack(fill=tk.X, padx=8, pady=4)
        tk.Label(lot_frame, text="Lot:", bg=THEME["bg_panel"],
                 fg=THEME["text_dim"]).pack(side=tk.LEFT)
        self._manual_lot_var = tk.StringVar(value="0.01")
        tk.Entry(lot_frame, textvariable=self._manual_lot_var,
                 width=8, bg=THEME["bg_card"], fg=THEME["text"],
                 insertbackground=THEME["text"]).pack(side=tk.LEFT, padx=8)

        manual_frame = tk.Frame(frame, bg=THEME["bg_panel"])
        manual_frame.pack(fill=tk.X, padx=8, pady=(0, 8))

        self._make_button(
            manual_frame, "BUY", THEME["green"], self._on_manual_buy
        ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        self._make_button(
            manual_frame, "SELL", THEME["red"], self._on_manual_sell
        ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        self._make_button(
            manual_frame, "CLOSE", THEME["yellow"], self._on_manual_close
        ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

    def _build_stats_panel(self, parent: tk.Frame) -> None:
        """Live stats + indicators display."""
        T = THEME

        # ── Account stats ──────────────────────────────────────────────────
        acct_frame = tk.LabelFrame(
            parent, text=" Account ",
            bg=T["bg_panel"], fg=T["text"],
            font=T["font_title"], bd=1, relief=tk.FLAT,
        )
        acct_frame.pack(fill=tk.X, pady=(0, 6))

        self._stat_vars = {}
        acct_stats = [
            ("Price",      "price",      T["text"]),
            ("Balance",    "balance",    T["text"]),
            ("Equity",     "equity",     T["text"]),
            ("Unrealized", "unrealized", T["yellow"]),
            ("Open Trade", "open_trade", T["text_dim"]),
            ("Bot State",  "bot_state",  T["text"]),
        ]
        for label, key, color in acct_stats:
            row = tk.Frame(acct_frame, bg=T["bg_panel"])
            row.pack(fill=tk.X, padx=8, pady=2)
            tk.Label(row, text=f"{label}:", bg=T["bg_panel"],
                     fg=T["text_dim"], width=11, anchor=tk.W).pack(side=tk.LEFT)
            var = tk.StringVar(value="—")
            self._stat_vars[key] = var
            tk.Label(row, textvariable=var, bg=T["bg_panel"],
                     fg=color, font=T["font_mono"]).pack(side=tk.LEFT)

        # ── Indicators panel ───────────────────────────────────────────────
        ind_frame = tk.LabelFrame(
            parent, text=" Indicators (live) ",
            bg=T["bg_panel"], fg=T["green"],
            font=T["font_title"], bd=1, relief=tk.FLAT,
        )
        ind_frame.pack(fill=tk.X, pady=(0, 6))

        indicator_stats = [
            ("EMA Fast",   "ema_fast",      T["green"]),
            ("EMA Slow",   "ema_slow",      T["accent2"]),
            ("ATR",        "atr",           T["yellow"]),
            ("RSI",        "rsi",           T["text"]),
            ("Trail Stop", "trailing_stop", T["red"]),
        ]
        for label, key, color in indicator_stats:
            row = tk.Frame(ind_frame, bg=T["bg_panel"])
            row.pack(fill=tk.X, padx=8, pady=3)
            tk.Label(row, text=f"{label}:", bg=T["bg_panel"],
                     fg=T["text_dim"], width=11, anchor=tk.W).pack(side=tk.LEFT)
            var = tk.StringVar(value="—")
            self._stat_vars[key] = var
            lbl = tk.Label(row, textvariable=var, bg=T["bg_panel"],
                           fg=color, font=("Consolas", 10, "bold"))
            lbl.pack(side=tk.LEFT)

    def _build_tabs(self, parent: tk.Frame) -> None:
        """Tabbed panel: Dashboard, Chart, Logs, Settings."""
        notebook = ttk.Notebook(parent)
        notebook.pack(fill=tk.BOTH, expand=True)

        # Dashboard tab
        dash_frame = tk.Frame(notebook, bg=THEME["bg"])
        notebook.add(dash_frame, text="  📊 Dashboard  ")
        self.dashboard = DashboardPanel(dash_frame, self.trade_repo, THEME)

        # Chart tab
        chart_frame = tk.Frame(notebook, bg=THEME["bg"])
        notebook.add(chart_frame, text="  📈 Chart  ")
        self.chart_panel = ChartPanel(chart_frame, THEME)
        self.chart_panel.pack(fill=tk.BOTH, expand=True)

        # Logs tab
        logs_frame = tk.Frame(notebook, bg=THEME["bg"])
        notebook.add(logs_frame, text="  📋 Logs  ")
        self.logs_panel = LogsPanel(logs_frame, self.trade_repo, THEME)

        # Settings tab
        settings_frame = tk.Frame(notebook, bg=THEME["bg"])
        notebook.add(settings_frame, text="  ⚙ Settings  ")
        self.settings_panel = SettingsPanel(
            settings_frame, self.strategy, self.risk_manager, THEME,
            get_bot_engine=lambda: self.bot_engine,
        )

        # Redraw chart when tab is selected
        def on_tab_change(e):
            selected = notebook.tab(notebook.select(), "text").strip()
            if "Chart" in selected:
                self.chart_panel.force_redraw()
        notebook.bind("<<NotebookTabChanged>>", on_tab_change)

    # ── Bot Controls ──────────────────────────────────────────────────────────

    def _on_start(self) -> None:
        symbol = self._symbol_var.get()
        timeframe = self._tf_var.get()

        self.bot_engine = BotEngine(
            broker=self.broker,
            strategy=self.strategy,
            risk_manager=self.risk_manager,
            trade_repo=self.trade_repo,
            symbol=symbol,
            timeframe=timeframe,
            on_event=self._on_bot_event,
        )

        if self.bot_engine.start():
            self._set_button_states(running=True)
            self._update_status("RUNNING", THEME["green"])

    def _on_pause(self) -> None:
        if self.bot_engine:
            if self.bot_engine.state == "PAUSED":
                self.bot_engine.resume()
                self._btn_pause.config(text="⏸ PAUSE")
                self._update_status("RUNNING", THEME["green"])
            else:
                self.bot_engine.pause()
                self._btn_pause.config(text="▶ RESUME")
                self._update_status("PAUSED", THEME["yellow"])

    def _on_stop(self) -> None:
        if self.bot_engine:
            self.bot_engine.stop()
        self._set_button_states(running=False)
        self._update_status("STOPPED", THEME["red"])

    def _on_restart(self) -> None:
        if self.bot_engine:
            self.bot_engine.restart()

    def _on_manual_buy(self) -> None:
        if self.bot_engine:
            try:
                lot = float(self._manual_lot_var.get())
                self.bot_engine.manual_buy(lot)
            except ValueError:
                messagebox.showerror("Error", "Invalid lot size")

    def _on_manual_sell(self) -> None:
        if self.bot_engine:
            try:
                lot = float(self._manual_lot_var.get())
                self.bot_engine.manual_sell(lot)
            except ValueError:
                messagebox.showerror("Error", "Invalid lot size")

    def _on_manual_close(self) -> None:
        if self.bot_engine:
            self.bot_engine.manual_close()

    # ── Bot Event Handler ─────────────────────────────────────────────────────

    def _on_bot_event(self, event: str, data: dict) -> None:
        """
        Receives events from the bot engine (background thread).
        Uses root.after() to safely update UI from main thread.
        """
        self.root.after(0, self._handle_bot_event, event, data)

    def _handle_bot_event(self, event: str, data: dict) -> None:
        """Process bot events in the main thread."""
        if event == "state_update":
            self._update_stats(data)
            # Update chart
            if self.bot_engine and self.bot_engine.candle_builder.df is not None:
                try:
                    df = self.bot_engine.candle_builder.df.copy()
                    from utils.indicators import compute_all
                    params = self.bot_engine.strategy.params
                    df = compute_all(
                        df,
                        ema_fast=params["ema_fast"],
                        ema_slow=params["ema_slow"],
                        atr_period=params["atr_period"],
                        rsi_period=params["rsi_period"],
                    )
                    self.chart_panel.update(
                        df=df,
                        current_price=data.get("price", 0),
                        indicators=data.get("indicators", {}),
                        symbol=self.bot_engine.symbol,
                        timeframe=self.bot_engine.timeframe,
                    )
                except Exception as e:
                    logger.error(f"Chart update error: {e}")

        elif event == "trade_opened":
            msg = (f"OPENED {data['direction']} {data['lot_size']} "
                   f"{data['symbol']} @ {data['price']:.5f}")
            self.logs_panel.add_log("TRADE", msg, data.get("symbol"))

        elif event == "trade_closed":
            pnl = data.get("pnl", 0)
            color = "green" if pnl >= 0 else "red"
            msg = (f"CLOSED {data['symbol']} @ {data['exit_price']:.5f} "
                   f"PnL={pnl:+.2f} | {data.get('reason', '')}")
            self.logs_panel.add_log("TRADE", msg, data.get("symbol"))
            self.dashboard.refresh()

        elif event == "signal":
            self.logs_panel.add_log("SIGNAL", data.get("signal", ""), data.get("symbol"))

        elif event == "error":
            self.logs_panel.add_log("ERROR", data.get("message", ""), None)
            self._update_status("ERROR", THEME["red"])

        elif event == "risk_block":
            self.logs_panel.add_log("RISK", data.get("reason", ""), None)

    # ── UI Helpers ────────────────────────────────────────────────────────────

    def _update_stats(self, data: dict) -> None:
        """Update the stats panel with latest bot data."""
        price      = data.get("price", 0)
        balance    = data.get("balance", 0)
        equity     = data.get("equity", 0)
        unrealized = data.get("unrealized_pnl", 0)
        open_trade = data.get("open_trade")
        indicators = data.get("indicators", {})
        trail_stop = data.get("trailing_stop")

        self._stat_vars["price"].set(f"{price:.5f}")
        self._stat_vars["balance"].set(f"${balance:,.2f}")
        self._stat_vars["equity"].set(f"${equity:,.2f}")

        sign = "+" if unrealized >= 0 else ""
        self._stat_vars["unrealized"].set(f"{sign}{unrealized:.2f}")
        self._stat_vars["open_trade"].set(f"#{open_trade}" if open_trade else "None")
        self._stat_vars["bot_state"].set(data.get("state", "—"))

        # Indicators
        def fmt(val, decimals=5):
            return f"{val:.{decimals}f}" if val is not None else "—"

        self._stat_vars["ema_fast"].set(fmt(indicators.get("ema_fast")))
        self._stat_vars["ema_slow"].set(fmt(indicators.get("ema_slow")))
        self._stat_vars["atr"].set(fmt(indicators.get("atr")))

        rsi = indicators.get("rsi")
        if rsi is not None:
            # Color RSI based on value
            rsi_str = f"{rsi:.1f}"
            if rsi >= 70:
                rsi_str += " ⚠ OB"
            elif rsi <= 30:
                rsi_str += " ⚠ OS"
            self._stat_vars["rsi"].set(rsi_str)
        else:
            self._stat_vars["rsi"].set("—")

        self._stat_vars["trailing_stop"].set(
            fmt(trail_stop) if trail_stop else "—"
        )

    def _update_status(self, text: str, color: str) -> None:
        self._status_label.config(text=f"● {text}", fg=color)

    def _set_button_states(self, running: bool) -> None:
        if running:
            self._btn_start.config(state=tk.DISABLED)
            self._btn_pause.config(state=tk.NORMAL)
            self._btn_stop.config(state=tk.NORMAL)
            self._btn_restart.config(state=tk.NORMAL)
        else:
            self._btn_start.config(state=tk.NORMAL)
            self._btn_pause.config(state=tk.DISABLED)
            self._btn_stop.config(state=tk.DISABLED)
            self._btn_restart.config(state=tk.DISABLED)

    def _make_button(self, parent, text: str, color: str, command) -> tk.Button:
        return tk.Button(
            parent, text=text, command=command,
            bg=color, fg="white",
            activebackground=THEME["bg_card"], activeforeground=THEME["text"],
            relief=tk.FLAT, cursor="hand2",
            font=("Segoe UI", 9, "bold"), pady=6,
        )

    def _schedule_ui_refresh(self) -> None:
        """Refresh dashboard every 10 seconds."""
        self.dashboard.refresh()
        self.root.after(10_000, self._schedule_ui_refresh)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def _on_close(self) -> None:
        """Clean shutdown when window is closed."""
        if self.bot_engine and self.bot_engine.is_running:
            if messagebox.askyesno("Confirm", "Bot is running. Stop and exit?"):
                self.bot_engine.stop()
            else:
                return

        self.db.close()
        self.root.destroy()
        logger.info("Application closed")

    def run(self) -> None:
        """Start the Tkinter main loop."""
        self.root.mainloop()
