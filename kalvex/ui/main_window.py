"""Main window — wires the Ember Terminal UI to the live engine.

Thread model (v1):
  * UI thread  : Qt widgets, timers for display refresh
  * Bot thread : BotWorker(QThread) runs the decision pipeline
  * Feed       : SimFeedProvider ticks from a UI timer (real Upstox websocket
                 feed will run its own worker thread — see market_data.py)
All cross-thread traffic is Qt signals; engine state is guarded by the bot's
lock. Restart recovery: engine state is rebuilt from SQLite on startup.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QCloseEvent, QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMenu,
    QMessageBox,
    QStackedWidget,
    QStyle,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from kalvex.core.bot import BotWorker
from kalvex.core.constants import (
    APP_NAME, APP_VERSION, PAGE_TITLES, WINDOW_DEFAULT_HEIGHT,
    WINDOW_DEFAULT_WIDTH, WINDOW_MIN_HEIGHT, WINDOW_MIN_WIDTH, BotMode, PageId,
)
from kalvex.core.db import Database
from kalvex.core.execution import PaperEngine
from kalvex.core.instruments import DEFAULT_BOOK
from kalvex.core.market_data import SimFeedProvider
from kalvex.core.risk import RiskConfig
from kalvex.ui.nav_sidebar import NavSidebar
from kalvex.ui.pages.activity_page import ActivityPage
from kalvex.ui.pages.brain_page import BrainPage
from kalvex.ui.pages.charts_page import ChartsPage
from kalvex.ui.pages.dashboard_page import DashboardPage
from kalvex.ui.pages.logs_page import LogsPage
from kalvex.ui.pages.settings_page import SettingsPage
from kalvex.ui.pages.strategies_page import StrategiesPage
from kalvex.ui.top_bar import TopBar

IST = ZoneInfo("Asia/Kolkata")


class MainWindow(QMainWindow):
    def __init__(self, db_path: str = "data/kalvex.db", sim: bool = True) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} — Ember Terminal · Paper · {APP_VERSION}")
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.resize(WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT)

        # ---------------- engine ----------------
        self.db = Database(db_path)
        for k, v in {
            "capital": "500000", "risk_per_trade_pct": "1.0",
            "max_open_positions": "3", "max_lots": "2", "max_orders_per_min": "20",
            "daily_max_loss": "5000", "square_off_time": "15:15",
            "session_open": "09:15", "session_close": "15:30",
            "auto_tune": "1", "options_enabled": "0",
        }.items():
            if self.db.get_setting(k) == "":
                self.db.set_setting(k, v)

        self.sim = sim
        self.feed = SimFeedProvider(
            {name: spec.base_price for name, spec in DEFAULT_BOOK.items()},
            seed=42, speed=float(self.db.get_setting("sim_speed", "5")))
        self.broker = PaperEngine(
            self.db, fee_per_order=float(self.db.get_setting("fee_per_order", "20")))
        risk_cfg = RiskConfig(
            capital=float(self.db.get_setting("capital", "500000")),
            risk_per_trade_pct=float(self.db.get_setting("risk_per_trade_pct", "1.0")),
            max_open_positions=int(self.db.get_setting("max_open_positions", "3")),
            max_lots=int(self.db.get_setting("max_lots", "2")),
            max_orders_per_min=int(self.db.get_setting("max_orders_per_min", "20")),
            daily_max_loss=float(self.db.get_setting("daily_max_loss", "5000")),
            daily_profit_stop=float(self.db.get_setting("daily_profit_stop", "10000")),
            profit_stop_enabled=self.db.get_setting("profit_stop_enabled", "0") == "1",
            trailing_start_profit=float(self.db.get_setting("trailing_start_profit", "500")),
            lot_size=75,
        )
        self.bot = BotWorker(self.db, self.feed, self.broker, risk_cfg,
                             mode=BotMode.PAPER,
                             instruments=DEFAULT_BOOK, cycle_seconds=1.0)

        # ---------------- UI shell ----------------
        central = QWidget()
        central.setObjectName("root")
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.top_bar = TopBar()
        outer.addWidget(self.top_bar)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        self.nav = NavSidebar()
        row.addWidget(self.nav)

        self.stack = QStackedWidget()
        self.page_dashboard = DashboardPage()
        self.page_charts = ChartsPage()
        self.page_brain = BrainPage()
        self.page_strategies = StrategiesPage()
        self.page_activity = ActivityPage()
        self.page_logs = LogsPage()
        self.page_settings = SettingsPage()
        self.pages: dict[str, QWidget] = {
            PageId.DASHBOARD.value: self.page_dashboard,
            PageId.CHARTS.value: self.page_charts,
            PageId.BRAIN.value: self.page_brain,
            PageId.STRATEGIES.value: self.page_strategies,
            PageId.ACTIVITY.value: self.page_activity,
            PageId.LOGS.value: self.page_logs,
            PageId.SETTINGS.value: self.page_settings,
        }
        for key in (PageId.DASHBOARD.value, PageId.CHARTS.value,
                    PageId.BRAIN.value, PageId.STRATEGIES.value,
                    PageId.ACTIVITY.value, PageId.LOGS.value,
                    PageId.SETTINGS.value):
            self.stack.addWidget(self.pages[key])
        row.addWidget(self.stack, stretch=1)
        outer.addLayout(row, stretch=1)
        self.setCentralWidget(central)

        self.page_charts.set_symbols(list(DEFAULT_BOOK.keys()))

        # ---------------- wiring ----------------
        self.nav.page_selected.connect(self._show_page)
        self.top_bar.kill_switch_requested.connect(self._kill_switch)
        self.top_bar.start_stop_clicked.connect(self._toggle_bot)
        self.bot.thought.connect(self._on_thought)
        self.bot.pnl_update.connect(self._on_pnl)
        self.bot.state_changed.connect(self.top_bar.set_state)
        self.bot.state_changed.connect(lambda s: self.db.log("INFO", "UI", "STATE", s))
        self.bot.toast.connect(self._on_toast)
        self.bot.semi_confirm.connect(self._on_semi_confirm)
        self.bot.positions_changed.connect(self._refresh_data_pages)
        self.page_strategies.strategy_toggled.connect(self._on_strategy_toggled)
        self.page_strategies.param_changed.connect(self._on_param_changed)

        # ---------------- timers ----------------
        self._feed_timer = QTimer(self)
        self._feed_timer.timeout.connect(self._advance_feed)
        self._feed_timer.start(300)

        self._ui_timer = QTimer(self)
        self._ui_timer.timeout.connect(self._refresh_ui)
        self._ui_timer.start(1500)
        self._refresh_ui()

        # ---------------- tray ----------------
        self._build_tray()

    # ------------------------------------------------------------------ #
    # feed + UI refresh
    # ------------------------------------------------------------------ #
    def _advance_feed(self) -> None:
        self.feed.tick()
        if self.bot.state.value == "RUNNING" and hasattr(self.broker, "on_tick"):
            ltps = {n: self.feed.ltp(n) for n in DEFAULT_BOOK}
            trades = self.broker.on_tick(ltps)
            if trades:
                from kalvex.core.models import Side as _Side
                bars = self.feed.bars(self.page_charts.symbol.currentText())
                idx = max(0, len(bars) - 1)
                for t in trades:
                    if t.instrument == self.page_charts.symbol.currentText():
                        self.page_charts.chart.add_marker(
                            idx, t.price,
                            "BUY" if t.side == _Side.BUY else "SELL")

    def _refresh_ui(self) -> None:
        from kalvex.core import indicators as ind
        bars = self.feed.bars("NIFTY 50")
        if len(bars) > 5:
            closes = [b.close for b in bars]
            self.page_charts.chart.set_data(
                bars, ema=ind.ema(closes, 9), vwap=ind.vwap_session(
                    [b.high for b in bars], [b.low for b in bars], closes,
                    [b.volume for b in bars],
                    [b.ts.strftime("%Y-%m-%d") for b in bars]))
        now = datetime.now(IST)
        self.page_dashboard.clock.setText(now.strftime("%a %d %b · %H:%M:%S"))
        sq = self.db.get_setting("square_off_time", "15:15")
        sq_dt = now.replace(hour=int(sq[:2]), minute=int(sq[3:]), second=0)
        delta = max(0, int((sq_dt - now).total_seconds() // 60))
        self.page_dashboard.tts.setText(f"{delta // 60}h {delta % 60:02d}m")

        open_pos = self.broker.get_positions()
        realised = self.bot.risk.day_realised_pnl
        unrealised = sum(p.unrealised(self.feed.ltp(p.instrument))
                         for p in open_pos)
        n_signals = len(self.db.query("SELECT id FROM signals"))
        wins = self.db.query("SELECT pnl FROM trades WHERE pnl > 0")
        closed = self.db.query("SELECT pnl FROM trades WHERE pnl != 0")
        wr = (len(wins) / len(closed)) if closed else None
        max_loss = self.bot.risk.config.daily_max_loss
        risk_used = (abs(min(0, realised + unrealised)) / max_loss * 100) if max_loss else 0
        self.page_dashboard.set_metrics(realised, unrealised, len(open_pos),
                                        n_signals, wr, risk_used, max_loss)
        self.top_bar.set_pnl(realised, unrealised)
        self._refresh_data_pages()

    def _refresh_data_pages(self) -> None:
        pos_rows = []
        for p in self.broker.get_positions():
            ltp = self.feed.ltp(p.instrument)
            pos_rows.append([
                p.instrument, f"{p.qty:+d}", f"{p.avg_price:,.2f}",
                f"{ltp:,.2f}", f"{p.unrealised(ltp):,.0f}",
                f"{p.sl:,.2f}" if p.sl else "—",
                f"{p.target:,.2f}" if p.target else "—",
                p.strategy_key, p.source.value, p.opened_at])
        self.page_activity.set_positions(pos_rows)

        orders = self.db.query("SELECT * FROM orders ORDER BY ts DESC LIMIT 200")
        self.page_activity.set_orders([
            [o["ts"], o["tag"], o["instrument"], o["side"], o["order_type"],
             str(o["qty"]), f"{(o['price'] or 0):,.2f}", o["status"],
             o["source"], o["strategy_key"]] for o in orders])
        trades = self.db.query("SELECT * FROM trades ORDER BY ts DESC LIMIT 200")
        self.page_activity.set_trades([
            [t["ts"], t["instrument"], t["side"], str(t["qty"]),
             f"{t['price']:,.2f}", f"{t['fee']:,.0f}", f"{t['pnl']:,.0f}",
             t["strategy_key"], t["source"]] for t in trades])
        logs = self.db.query(
            "SELECT ts, level, source, event, detail FROM logs "
            "ORDER BY id DESC LIMIT 400")
        self.page_logs.set_logs([[r[0], r[1], r[2], r[3], r[4]] for r in logs])

        rows = self.db.query("SELECT * FROM strategies")
        import json as _json
        strat_rows = [
            {"key": r["key"], "name": r["name"], "enabled": bool(r["enabled"]),
             "mode": r["mode"],
             "params": _json.loads(r["params"] or "{}"),
             "trades": 0, "win": None, "pnl": 0.0, "status": "armed"}
            for r in rows]
        self.page_strategies.set_strategies(strat_rows)

        brain_rows = []
        for r in rows:
            last = self.db.query(
                "SELECT thought FROM decision_log WHERE strategy_key=? "
                "ORDER BY id DESC LIMIT 1", (r["key"],))
            brain_rows.append({
                "name": r["name"], "enabled": bool(r["enabled"]),
                "params": ", ".join(f"{k}={v}" for k, v in
                                    _json.loads(r["params"] or "{}").items()),
                "last": last[0]["thought"] if last else "—"})
        self.page_brain.set_strategies(brain_rows)
        self.page_brain.set_reviews(self.db.recent_reviews(30))

    # ------------------------------------------------------------------ #
    # bot control
    # ------------------------------------------------------------------ #
    def _toggle_bot(self) -> None:
        if self.bot.state.value == "RUNNING":
            self.bot.stop()
            self.bot.wait(3000)
            self.db.log("INFO", "UI", "BOT_STOP", "user stop")
        else:
            if self.bot.isRunning():
                return
            self.bot = BotWorker(self.db, self.feed, self.broker,
                                 self.bot.risk.config, mode=BotMode.PAPER,
                                 instruments=DEFAULT_BOOK, cycle_seconds=1.0)
            self.bot.thought.connect(self._on_thought)
            self.bot.pnl_update.connect(self._on_pnl)
            self.bot.state_changed.connect(self.top_bar.set_state)
            self.bot.toast.connect(self._on_toast)
            self.bot.semi_confirm.connect(self._on_semi_confirm)
            self.bot.positions_changed.connect(self._refresh_data_pages)
            self.bot.start()
            self.db.log("INFO", "UI", "BOT_START", "paper mode")

    def _kill_switch(self) -> None:
        self.bot.kill_switch()
        self.db.log("WARNING", "UI", "KILL_SWITCH", "executed from UI")

    def _on_thought(self, ev: dict) -> None:
        self.page_dashboard.append_thought(ev)
        self.page_brain.on_thought(ev)

    def _on_pnl(self, realised: float, unrealised: float) -> None:
        self.top_bar.set_pnl(realised, unrealised)

    def _on_toast(self, text: str) -> None:
        self.tray.showMessage(APP_NAME, text,
                              QSystemTrayIcon.MessageIcon.Information, 4000)

    def _on_semi_confirm(self, payload) -> None:
        sig, decision = payload
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setText(f"Semi-auto signal: {sig.side.value} {sig.instrument} "
                    f"@ {sig.entry:,.2f}")
        box.setInformativeText(
            f"SL {sig.sl:,.2f} · target {sig.target:,.2f} · qty {decision.qty}\n\n"
            f"{sig.thought}")
        yes = box.addButton("CONFIRM (paper)", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Reject", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        self.bot.confirm_semi(payload, box.clickedButton() is yes)

    def _on_strategy_toggled(self, key: str, enabled: bool) -> None:
        self.bot.set_strategy_enabled(key, enabled)

    def _on_param_changed(self, key: str, param: str, value) -> None:
        self.bot.set_strategy_param(key, param, value)
        self.db.log("INFO", "UI", "PARAM_CHANGE", f"{key}.{param}={value}")

    def _show_page(self, page_id: str) -> None:
        self.stack.setCurrentWidget(self.pages[page_id])
        self.setWindowTitle(
            f"{APP_NAME} — {PAGE_TITLES[PageId(page_id)]} · Paper · {APP_VERSION}")

    # ------------------------------------------------------------------ #
    # tray + close
    # ------------------------------------------------------------------ #
    def _build_tray(self) -> None:
        icon: QIcon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip(f"{APP_NAME} — Paper Trading")
        menu = QMenu()
        act_show = QAction("Show / Hide", self)
        act_show.triggered.connect(self._toggle_visible)
        menu.addAction(act_show)
        menu.addSeparator()
        act_start = QAction("Start / Stop bot", self)
        act_start.triggered.connect(self._toggle_bot)
        menu.addAction(act_start)
        act_flat = QAction("Flatten all (keep bot)", self)
        act_flat.triggered.connect(lambda: self.bot.request_flatten_all("TRAY"))
        menu.addAction(act_flat)
        menu.addSeparator()
        act_kill = QAction("KILL SWITCH", self)
        act_kill.triggered.connect(self._kill_switch)
        menu.addAction(act_kill)
        menu.addSeparator()
        act_quit = QAction("Quit", self)
        act_quit.triggered.connect(self.close)
        menu.addAction(act_quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda r: self._toggle_visible() if r == QSystemTrayIcon.ActivationReason.Trigger else None)
        self.tray.show()

    def _toggle_visible(self) -> None:
        if self.isVisible():
            self.hide()
        else:
            self.showNormal()
            self.raise_()
            self.activateWindow()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(f"Quit {APP_NAME}?")
        box.setText("Keep the bot running in the tray?")
        to_tray = box.addButton("Minimize to tray", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Stop bot & quit", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is to_tray:
            self.hide()
            event.ignore()
        else:
            self.bot.stop()
            self.bot.wait(2000)
            self.tray.hide()
            event.accept()
