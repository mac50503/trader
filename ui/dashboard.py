"""
ui/dashboard.py
----------------
Dashboard panel — shows trade history and performance summary.
Displayed in the main tab of the application.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional
from datetime import datetime

from database.trade_repository import TradeRepository
from utils.logger import get_logger

logger = get_logger(__name__)


class DashboardPanel:
    """
    Trade history table + performance summary cards.
    Refreshes on demand (called by app.py every 10s and after each trade).
    """

    def __init__(self, parent: tk.Frame, trade_repo: TradeRepository, theme: dict):
        self.parent = parent
        self.trade_repo = trade_repo
        self.theme = theme
        self._build()

    def _build(self) -> None:
        T = self.theme

        # ── Summary cards ──────────────────────────────────────────────────
        cards_frame = tk.Frame(self.parent, bg=T["bg"])
        cards_frame.pack(fill=tk.X, padx=8, pady=8)

        self._card_vars = {}
        cards = [
            ("Total Trades", "total_trades", T["text"]),
            ("Win Rate",     "win_rate",     T["green"]),
            ("Total PnL",    "total_pnl",    T["yellow"]),
            ("Best Trade",   "best_trade",   T["green"]),
            ("Worst Trade",  "worst_trade",  T["red"]),
            ("Avg Duration", "avg_duration", T["text_dim"]),
        ]

        for i, (label, key, color) in enumerate(cards):
            card = tk.Frame(cards_frame, bg=T["bg_card"], padx=12, pady=8)
            card.grid(row=0, column=i, padx=4, sticky="ew")
            cards_frame.columnconfigure(i, weight=1)

            tk.Label(card, text=label, bg=T["bg_card"],
                     fg=T["text_dim"], font=("Segoe UI", 8)).pack()
            var = tk.StringVar(value="—")
            self._card_vars[key] = var
            tk.Label(card, textvariable=var, bg=T["bg_card"],
                     fg=color, font=("Segoe UI", 13, "bold")).pack()

        # ── Toolbar ────────────────────────────────────────────────────────
        toolbar = tk.Frame(self.parent, bg=T["bg"])
        toolbar.pack(fill=tk.X, padx=8, pady=(4, 0))

        tk.Label(toolbar, text="Trade History",
                 bg=T["bg"], fg=T["text"],
                 font=T["font_title"]).pack(side=tk.LEFT)

        tk.Button(
            toolbar, text="↻ Refresh",
            bg=T["bg_card"], fg=T["text_dim"],
            relief=tk.FLAT, cursor="hand2", padx=8,
            command=self.refresh,
        ).pack(side=tk.RIGHT, padx=4)

        tk.Button(
            toolbar, text="🗑 Clear All",
            bg=T["red"], fg="white",
            relief=tk.FLAT, cursor="hand2", padx=8,
            command=self._confirm_clear,
        ).pack(side=tk.RIGHT, padx=4)

        # ── Trade history table ────────────────────────────────────────────
        table_frame = tk.Frame(self.parent, bg=T["bg"])
        table_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(4, 8))

        columns = ("id", "symbol", "dir", "entry", "exit", "lot", "pnl", "status", "time")
        self._tree = ttk.Treeview(
            table_frame, columns=columns, show="headings",
            height=15, selectmode="browse",
        )

        headers = {
            "id":     ("#",          50),
            "symbol": ("Symbol",     80),
            "dir":    ("Dir",        50),
            "entry":  ("Entry",      90),
            "exit":   ("Exit",       90),
            "lot":    ("Lot",        60),
            "pnl":    ("PnL",        80),
            "status": ("Status",     70),
            "time":   ("Entry Time", 140),
        }

        for col, (heading, width) in headers.items():
            self._tree.heading(col, text=heading)
            self._tree.column(col, width=width, anchor=tk.CENTER)

        style = ttk.Style()
        style.configure("Treeview",
                        background=T["bg_panel"],
                        foreground=T["text"],
                        fieldbackground=T["bg_panel"],
                        rowheight=24,
                        font=T["font_mono"])
        style.configure("Treeview.Heading",
                        background=T["bg_card"],
                        foreground=T["text"],
                        font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", T["accent2"])])

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL,
                                  command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)

        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._tree.tag_configure("profit", foreground=T["green"])
        self._tree.tag_configure("loss",   foreground=T["red"])
        self._tree.tag_configure("open",   foreground=T["yellow"])

        self.refresh()

    # ── Public ────────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        """Reload trade data from DB and update all widgets."""
        try:
            trades = self.trade_repo.get_all_trades(limit=100)
            self._update_table(trades)
            self._update_summary(trades)
        except Exception as e:
            logger.error(f"Dashboard refresh error: {e}")

    # ── Private ───────────────────────────────────────────────────────────────

    def _confirm_clear(self) -> None:
        """Ask for confirmation before clearing all trade history."""
        answer = messagebox.askyesno(
            "Clear Trade History",
            "This will permanently delete all trades and events from the database.\n\n"
            "Are you sure?",
            icon="warning",
        )
        if answer:
            self._clear_all()

    def _clear_all(self) -> None:
        """Delete all trades and events from the database."""
        try:
            conn = self.trade_repo.db.get_connection()
            conn.execute("DELETE FROM trades")
            conn.execute("DELETE FROM bot_events")
            conn.commit()
            logger.info("Trade history cleared by user")
            self.refresh()
        except Exception as e:
            logger.error(f"Failed to clear history: {e}")
            messagebox.showerror("Error", f"Could not clear history:\n{e}")

    def _update_table(self, trades) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)

        for trade in trades:
            pnl_str  = f"{trade.pnl:+.2f}" if trade.pnl != 0 else "—"
            exit_str = f"{trade.exit_price:.5f}" if trade.exit_price else "—"
            time_str = trade.entry_time.strftime("%Y-%m-%d %H:%M") if trade.entry_time else "—"

            tag = "open"
            if trade.status == "CLOSED":
                tag = "profit" if trade.pnl >= 0 else "loss"

            self._tree.insert("", tk.END, values=(
                trade.id,
                trade.symbol,
                trade.direction,
                f"{trade.entry_price:.5f}",
                exit_str,
                trade.lot_size,
                pnl_str,
                trade.status,
                time_str,
            ), tags=(tag,))

    def _update_summary(self, trades) -> None:
        closed = [t for t in trades if t.status == "CLOSED"]

        if not closed:
            for key in self._card_vars:
                self._card_vars[key].set("—")
            return

        total     = len(closed)
        winners   = [t for t in closed if t.pnl > 0]
        win_rate  = (len(winners) / total * 100) if total > 0 else 0
        total_pnl = sum(t.pnl for t in closed)
        best      = max(t.pnl for t in closed)
        worst     = min(t.pnl for t in closed)

        durations   = [t.duration_seconds for t in closed if t.duration_seconds]
        avg_dur     = sum(durations) / len(durations) if durations else 0
        avg_dur_str = f"{avg_dur/3600:.1f}h" if avg_dur > 0 else "—"

        self._card_vars["total_trades"].set(str(total))
        self._card_vars["win_rate"].set(f"{win_rate:.1f}%")
        self._card_vars["total_pnl"].set(f"{total_pnl:+.2f}")
        self._card_vars["best_trade"].set(f"+{best:.2f}")
        self._card_vars["worst_trade"].set(f"{worst:.2f}")
        self._card_vars["avg_duration"].set(avg_dur_str)
