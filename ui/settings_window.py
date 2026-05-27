"""
ui/settings_window.py
----------------------
Settings panel — configure strategy parameters and risk rules from the UI.
Changes take effect immediately without restarting the bot.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

from strategies.strategy_registry import StrategyRegistry
from risk_management.risk_manager import RiskManager
from utils.logger import get_logger
from typing import Optional
import config

logger = get_logger(__name__)


class SettingsPanel:
    """
    Settings form for strategy and risk parameters.
    Applies changes to live strategy and risk manager instances.
    """

    def __init__(
        self,
        parent: tk.Frame,
        strategy,
        risk_manager: RiskManager,
        theme: dict,
        get_bot_engine=None,
        on_strategy_change=None,   # callable(strategy_name) — hot-swaps strategy
    ):
        self.parent = parent
        self.strategy = strategy
        self.risk_manager = risk_manager
        self.theme = theme
        self.get_bot_engine = get_bot_engine or (lambda: None)
        self.on_strategy_change = on_strategy_change or (lambda name: None)
        self._vars: dict = {}
        self._build()

    def _build(self) -> None:
        T = self.theme

        # Scrollable container
        canvas = tk.Canvas(self.parent, bg=T["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.parent, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=T["bg"])

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scroll_frame, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # ── Strategy Selection ─────────────────────────────────────────────
        strategy_frame = tk.LabelFrame(
            scroll_frame, text=" Active Strategy ",
            bg=T["bg"], fg=T["text"],
            font=T["font_title"], bd=1, relief=tk.FLAT,
        )
        strategy_frame.pack(fill=tk.X, padx=8, pady=8)

        row = tk.Frame(strategy_frame, bg=T["bg"])
        row.pack(fill=tk.X, padx=8, pady=8)

        tk.Label(
            row, text="Strategy:", bg=T["bg"],
            fg=T["text_dim"], width=22, anchor=tk.W,
        ).pack(side=tk.LEFT)

        available_strategies = StrategyRegistry.list_strategies()
        self._vars["active_strategy"] = tk.StringVar(value=config.ACTIVE_STRATEGY)
        strategy_combo = ttk.Combobox(
            row, textvariable=self._vars["active_strategy"],
            values=available_strategies,
            state="readonly", width=30,
        )
        strategy_combo.pack(side=tk.LEFT, padx=8)

        hint_frame = tk.Frame(strategy_frame, bg=T["bg"])
        hint_frame.pack(fill=tk.X, padx=8, pady=(0, 8))
        tk.Label(
            hint_frame,
            text="  • Strategy changes apply immediately (bot restarts automatically if running).",
            bg=T["bg"], fg=T["text_dim"], font=("Segoe UI", 8), anchor=tk.W,
        ).pack(side=tk.LEFT)

        # ── Strategy Settings ──────────────────────────────────────────────
        self._build_section(
            scroll_frame, "Strategy Parameters",
            [
                ("EMA Fast Period",          "ema_fast",             int,   config.EMA_FAST),
                ("EMA Slow Period",          "ema_slow",             int,   config.EMA_SLOW),
                ("ATR Period",               "atr_period",           int,   config.ATR_PERIOD),
                ("Touch Tolerance (× ATR)",  "touch_tolerance_atr",  float, 0.5),
                ("Exit % Below EMA",         "exit_pct_below_ema",   float, 0.3),
                ("RSI Period",               "rsi_period",           int,   config.RSI_PERIOD),
            ]
        )

        # Hints under strategy section
        hint_frame = tk.Frame(scroll_frame, bg=T["bg"])
        hint_frame.pack(fill=tk.X, padx=16, pady=(0, 4))
        hints = [
            "Touch Tolerance: how close low must get to EMA (0.5 = half ATR)",
            "Exit % Below EMA: e.g. 0.3 = exit if close < EMA × 0.997",
        ]
        for hint in hints:
            tk.Label(hint_frame, text=f"  • {hint}", bg=T["bg"],
                     fg=T["text_dim"], font=("Segoe UI", 8),
                     anchor=tk.W).pack(fill=tk.X)

        # RSI filter toggle
        rsi_frame = tk.Frame(scroll_frame, bg=T["bg"])
        rsi_frame.pack(fill=tk.X, padx=16, pady=4)
        self._vars["use_rsi_filter"] = tk.BooleanVar(value=False)
        tk.Checkbutton(
            rsi_frame, text="Enable RSI Filter",
            variable=self._vars["use_rsi_filter"],
            bg=T["bg"], fg=T["text"],
            selectcolor=T["bg_card"],
            activebackground=T["bg"],
        ).pack(side=tk.LEFT)

        # Allow short toggle
        short_frame = tk.Frame(scroll_frame, bg=T["bg"])
        short_frame.pack(fill=tk.X, padx=16, pady=4)
        self._vars["allow_short"] = tk.BooleanVar(value=False)
        tk.Checkbutton(
            short_frame, text="Allow Short Selling (SELL signals)",
            variable=self._vars["allow_short"],
            bg=T["bg"], fg=T["text"],
            selectcolor=T["bg_card"],
            activebackground=T["bg"],
        ).pack(side=tk.LEFT)

        # ── Risk Settings ──────────────────────────────────────────────────
        self._build_section(
            scroll_frame, "Risk Management",
            [
                ("Risk Per Trade (%)",     "risk_percent",          float, config.DEFAULT_RISK_PERCENT),
                ("Max Daily Loss (%)",     "max_daily_loss_pct",    float, config.MAX_DAILY_LOSS_PERCENT),
                ("Max Open Positions",     "max_open_positions",    int,   config.MAX_OPEN_POSITIONS),
            ]
        )

        # ── Bot Behavior ───────────────────────────────────────────────────
        self._build_section(
            scroll_frame, "Bot Behavior",
            [
                ("Tick Interval (seconds)", "tick_interval", int, config.TICK_INTERVAL_SECONDS),
            ]
        )
        # Helper label
        hint_frame = tk.Frame(scroll_frame, bg=T["bg"])
        hint_frame.pack(fill=tk.X, padx=16, pady=(0, 4))
        tk.Label(
            hint_frame,
            text="↑ How often the bot polls for new data. Lower = faster simulation.",
            bg=T["bg"], fg=T["text_dim"], font=("Segoe UI", 8), anchor=tk.W,
        ).pack(side=tk.LEFT)

        # ── Broker Settings ────────────────────────────────────────────────
        self._build_section(
            scroll_frame, "Broker Configuration",
            [
                ("API Key",    "api_key",    str, config.BROKER_API_KEY or ""),
                ("Secret Key", "secret_key", str, config.BROKER_SECRET_KEY or ""),
                ("Base URL",   "base_url",   str, config.BROKER_BASE_URL or ""),
            ],
            secret_fields={"api_key", "secret_key"},
        )

        # ── Apply button ───────────────────────────────────────────────────
        btn_frame = tk.Frame(scroll_frame, bg=T["bg"])
        btn_frame.pack(fill=tk.X, padx=16, pady=16)

        tk.Button(
            btn_frame, text="✓ Apply Settings",
            bg=T["green"], fg="white",
            relief=tk.FLAT, cursor="hand2",
            font=("Segoe UI", 10, "bold"), pady=8,
            command=self._apply_settings,
        ).pack(fill=tk.X)

        tk.Button(
            btn_frame, text="🎨 Draw Pattern",
            bg=T["bg_card"], fg=T["text"],
            relief=tk.FLAT, cursor="hand2",
            font=("Segoe UI", 10), pady=6,
            command=self._draw_pattern,
        ).pack(fill=tk.X, pady=(4, 0))

        tk.Button(
            btn_frame, text="🔍 Scan Patterns",
            bg=T["bg_card"], fg=T["text"],
            relief=tk.FLAT, cursor="hand2",
            font=("Segoe UI", 10), pady=6,
            command=self._scan_patterns,
        ).pack(fill=tk.X, pady=(4, 0))

        tk.Button(
            btn_frame, text="↺ Reset to Defaults",
            bg=T["bg_card"], fg=T["text_dim"],
            relief=tk.FLAT, cursor="hand2",
            pady=6,
            command=self._reset_defaults,
        ).pack(fill=tk.X, pady=(4, 0))

    def _build_section(
        self,
        parent: tk.Frame,
        title: str,
        fields: list,
        secret_fields: set = None,
    ) -> None:
        """Build a labeled section with input fields."""
        T = self.theme
        secret_fields = secret_fields or set()

        section = tk.LabelFrame(
            parent, text=f" {title} ",
            bg=T["bg"], fg=T["text"],
            font=T["font_title"], bd=1, relief=tk.FLAT,
        )
        section.pack(fill=tk.X, padx=8, pady=8)

        for label, key, cast, default in fields:
            row = tk.Frame(section, bg=T["bg"])
            row.pack(fill=tk.X, padx=8, pady=3)

            tk.Label(
                row, text=f"{label}:", bg=T["bg"],
                fg=T["text_dim"], width=22, anchor=tk.W,
            ).pack(side=tk.LEFT)

            var = tk.StringVar(value=str(default))
            self._vars[key] = var

            show = "*" if key in secret_fields else ""
            entry = tk.Entry(
                row, textvariable=var,
                bg=T["bg_card"], fg=T["text"],
                insertbackground=T["text"],
                relief=tk.FLAT, width=20,
                show=show,
            )
            entry.pack(side=tk.LEFT, padx=8)

            # Store cast type for validation
            entry._cast = cast

    def _apply_settings(self) -> None:
        """Read form values and update strategy + risk manager."""
        try:
            # Hot-swap strategy — updates self.strategy in app and bot_engine if running
            if "active_strategy" in self._vars:
                selected_strategy = self._vars["active_strategy"].get()
                config.ACTIVE_STRATEGY = selected_strategy
                self.on_strategy_change(selected_strategy)
                logger.info(f"Active strategy set to: {selected_strategy}")

            # Update strategy params
            strategy_keys = [
                "ema_fast", "ema_slow", "atr_period",
                "touch_tolerance_atr", "exit_pct_below_ema",
                "rsi_period", "use_rsi_filter", "allow_short",
            ]
            for key in strategy_keys:
                if key in self._vars:
                    var = self._vars[key]
                    if isinstance(var, tk.BooleanVar):
                        self.strategy.params[key] = var.get()
                    else:
                        # Determine type from current param value
                        current = self.strategy.params.get(key)
                        if isinstance(current, int):
                            self.strategy.params[key] = int(var.get())
                        elif isinstance(current, float):
                            self.strategy.params[key] = float(var.get())
                        else:
                            self.strategy.params[key] = var.get()

            # Update risk manager
            risk_updates = {}
            if "risk_percent" in self._vars:
                risk_updates["risk_percent"] = float(self._vars["risk_percent"].get())
            if "max_daily_loss_pct" in self._vars:
                risk_updates["max_daily_loss_pct"] = float(self._vars["max_daily_loss_pct"].get())
            if "max_open_positions" in self._vars:
                risk_updates["max_open_positions"] = int(self._vars["max_open_positions"].get())

            self.risk_manager.update_params(**risk_updates)

            # Update bot engine tick interval (takes effect on next sleep cycle)
            if "tick_interval" in self._vars:
                new_interval = int(self._vars["tick_interval"].get())
                new_interval = max(1, min(new_interval, 60))   # clamp 1–60s
                bot = self.get_bot_engine()
                if bot is not None:
                    bot.tick_interval = new_interval
                    logger.info(f"Tick interval updated to {new_interval}s (bot running)")
                else:
                    # Bot not started yet — update config so it picks it up on start
                    config.TICK_INTERVAL_SECONDS = new_interval
                    logger.info(f"Tick interval set to {new_interval}s (applied on next start)")

            messagebox.showinfo("Settings", "Settings applied successfully.")
            logger.info("Settings updated from UI")

        except ValueError as e:
            messagebox.showerror("Invalid Input", f"Please check your values:\n{e}")

    def _reset_defaults(self) -> None:
        """Reset all fields to config defaults."""
        defaults = {
            "ema_fast":             config.EMA_FAST,
            "ema_slow":             config.EMA_SLOW,
            "atr_period":           config.ATR_PERIOD,
            "touch_tolerance_atr":  0.5,
            "exit_pct_below_ema":   0.3,
            "rsi_period":           config.RSI_PERIOD,
            "risk_percent":         config.DEFAULT_RISK_PERCENT,
            "max_daily_loss_pct":   config.MAX_DAILY_LOSS_PERCENT,
            "max_open_positions":   config.MAX_OPEN_POSITIONS,
            "tick_interval":        config.TICK_INTERVAL_SECONDS,
        }
        for key, value in defaults.items():
            if key in self._vars and isinstance(self._vars[key], tk.StringVar):
                self._vars[key].set(str(value))
        if "use_rsi_filter" in self._vars:
            self._vars["use_rsi_filter"].set(False)
        if "allow_short" in self._vars:
            self._vars["allow_short"].set(False)

    def _draw_pattern(self) -> None:
        """Open pattern visualizer window."""
        from ui.pattern_visualizer import PatternVisualizer

        strategy_name = self._vars.get("active_strategy", tk.StringVar()).get()
        if not strategy_name:
            strategy_name = config.ACTIVE_STRATEGY

        # Get the CURRENT live strategy — from bot engine if running,
        # otherwise fall back to self.strategy (may be stale after hot-swap)
        bot = self.get_bot_engine()
        live_strategy = (bot.strategy if bot is not None else None) or self.strategy
        snapshot = getattr(live_strategy, "last_pattern_snapshot", {})

        # Debug: log what we found
        import logging
        logging.getLogger(__name__).info(
            f"Draw Pattern: strategy={type(live_strategy).__name__} "
            f"snapshot_keys={list(snapshot.keys())} "
            f"bot_running={bot is not None}"
        )

        PatternVisualizer(
            self.parent.winfo_toplevel(),
            strategy_name=strategy_name,
            snapshot=snapshot,
        )

    def _scan_patterns(self) -> None:
        """Open pattern scanner — runs strategy over historical candles."""
        from ui.pattern_scanner import PatternScanner

        strategy_name = self._vars.get("active_strategy", tk.StringVar()).get()
        if not strategy_name:
            strategy_name = config.ACTIVE_STRATEGY

        # Get candle data from bot engine if running
        df = None
        bot = self.get_bot_engine()
        if bot is not None and bot.candle_builder.df is not None:
            df = bot.candle_builder.df.copy()

        PatternScanner(self.parent.winfo_toplevel(), strategy_name=strategy_name, df=df)
