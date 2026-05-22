"""
ui/logs_window.py
------------------
Logs panel — real-time event log with filtering.
Shows signals, trades, errors, trailing stop updates.
"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime
from typing import Optional

from database.trade_repository import TradeRepository
from utils.logger import get_logger

logger = get_logger(__name__)

# Log level colors
LEVEL_COLORS = {
    "TRADE":  "#00d4aa",
    "SIGNAL": "#a29bfe",
    "RISK":   "#ffa502",
    "ERROR":  "#ff4757",
    "INFO":   "#eaeaea",
    "SYSTEM": "#74b9ff",
}


class LogsPanel:
    """
    Scrollable log viewer with level filtering.
    Logs are added in real-time via add_log() and also loaded from DB.
    """

    def __init__(self, parent: tk.Frame, trade_repo: TradeRepository, theme: dict):
        self.parent = parent
        self.trade_repo = trade_repo
        self.theme = theme
        self._filter_var = tk.StringVar(value="ALL")
        self._build()
        self._load_from_db()

    def _build(self) -> None:
        T = self.theme

        # ── Toolbar ────────────────────────────────────────────────────────
        toolbar = tk.Frame(self.parent, bg=T["bg"])
        toolbar.pack(fill=tk.X, padx=8, pady=8)

        tk.Label(toolbar, text="Filter:", bg=T["bg"],
                 fg=T["text_dim"]).pack(side=tk.LEFT)

        levels = ["ALL", "TRADE", "SIGNAL", "RISK", "ERROR", "SYSTEM"]
        for level in levels:
            color = LEVEL_COLORS.get(level, T["text"])
            rb = tk.Radiobutton(
                toolbar, text=level,
                variable=self._filter_var, value=level,
                bg=T["bg"], fg=color, selectcolor=T["bg_card"],
                activebackground=T["bg"], activeforeground=color,
                command=self._apply_filter,
            )
            rb.pack(side=tk.LEFT, padx=4)

        tk.Button(
            toolbar, text="Clear",
            bg=T["bg_card"], fg=T["text_dim"],
            relief=tk.FLAT, cursor="hand2",
            command=self._clear_logs,
        ).pack(side=tk.RIGHT, padx=4)

        tk.Button(
            toolbar, text="↻ Reload",
            bg=T["bg_card"], fg=T["text_dim"],
            relief=tk.FLAT, cursor="hand2",
            command=self._load_from_db,
        ).pack(side=tk.RIGHT, padx=4)

        # ── Log text area ──────────────────────────────────────────────────
        text_frame = tk.Frame(self.parent, bg=T["bg"])
        text_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        self._text = tk.Text(
            text_frame,
            bg=T["bg_panel"], fg=T["text"],
            font=T["font_mono"],
            state=tk.DISABLED,
            wrap=tk.WORD,
            relief=tk.FLAT,
            padx=8, pady=8,
        )

        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL,
                                  command=self._text.yview)
        self._text.configure(yscrollcommand=scrollbar.set)

        self._text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Configure text tags for colors
        for level, color in LEVEL_COLORS.items():
            self._text.tag_configure(level, foreground=color)
        self._text.tag_configure("timestamp", foreground=T["text_dim"])
        self._text.tag_configure("dim", foreground=T["text_dim"])

        # Store all log entries for filtering
        self._all_logs: list = []

    def add_log(self, level: str, message: str, symbol: Optional[str] = None) -> None:
        """
        Add a new log entry (called from UI thread via root.after).
        Also persists to DB.
        """
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        entry = {
            "timestamp": timestamp,
            "level": level.upper(),
            "symbol": symbol or "",
            "message": message,
        }
        self._all_logs.append(entry)

        # Persist to DB
        try:
            self.trade_repo.log_event(level, level, message, symbol)
        except Exception:
            pass

        # Display if matches current filter
        if self._matches_filter(entry):
            self._append_to_text(entry)

    def _append_to_text(self, entry: dict) -> None:
        """Append a single log entry to the text widget."""
        self._text.config(state=tk.NORMAL)

        level = entry["level"]
        symbol = f"[{entry['symbol']}] " if entry["symbol"] else ""

        self._text.insert(tk.END, f"{entry['timestamp']} ", "timestamp")
        self._text.insert(tk.END, f"[{level:6s}] ", level)
        self._text.insert(tk.END, f"{symbol}", "dim")
        self._text.insert(tk.END, f"{entry['message']}\n")

        self._text.config(state=tk.DISABLED)
        self._text.see(tk.END)   # Auto-scroll to bottom

    def _apply_filter(self) -> None:
        """Re-render log with current filter."""
        self._text.config(state=tk.NORMAL)
        self._text.delete("1.0", tk.END)
        self._text.config(state=tk.DISABLED)

        for entry in self._all_logs:
            if self._matches_filter(entry):
                self._append_to_text(entry)

    def _matches_filter(self, entry: dict) -> bool:
        selected = self._filter_var.get()
        return selected == "ALL" or entry["level"] == selected

    def _clear_logs(self) -> None:
        self._all_logs.clear()
        self._text.config(state=tk.NORMAL)
        self._text.delete("1.0", tk.END)
        self._text.config(state=tk.DISABLED)

    def _load_from_db(self) -> None:
        """Load recent events from database."""
        try:
            events = self.trade_repo.get_recent_events(limit=200)
            self._all_logs.clear()
            for event in reversed(events):
                self._all_logs.append({
                    "timestamp": event.get("timestamp", "")[:19],
                    "level": event.get("level", "INFO"),
                    "symbol": event.get("symbol") or "",
                    "message": event.get("message", ""),
                })
            self._apply_filter()
        except Exception as e:
            logger.error(f"Failed to load logs from DB: {e}")
