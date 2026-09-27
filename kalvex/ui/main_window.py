"""Main window — Ember Terminal wired to the PRODUCTION engine.

Data & execution:
  * market data comes from Upstox (verified quote endpoint) once the broker
    is connected — there is NO synthetic data in the GUI; disconnected means
    'no data' rather than fake prices.
  * instruments (NIFTY / SENSEX / BANKNIFTY / FINNIFTY / MIDCAPNIFTY) are
    resolved from the Upstox instrument master (lot sizes, keys, strikes).
  * Paper / Semi-auto / Auto is a real execution switch:
      Paper  -> simulated fills from LIVE quotes (default)
      Semi   -> signal + confirm dialog, then the chosen execution target
      Auto   -> unattended; live orders only with broker connected AND the
                explicit live opt-in (and after Paper has been used)
  * live orders go through the official SDK (verified fields, X-Algo-Name,
    static-IP requirement, 10/sec throttle); raw MARKET is refused.

Threads: UI thread + BotWorker(QThread); cross-thread traffic is Qt
signals; engine state is lock-guarded in the bot.
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
from kalvex.core.instruments import InstrumentMaster, InstrumentSpec
from kalvex.core.market_data import UpstoxLiveFeed
from kalvex.core.risk import RiskConfig
from kalvex.core.security import TokenStore
from kalvex.core.session import BrokerSession, ConnectionState
from kalvex.core.upstox_api import UpstoxApi
from kalvex.ui.connect_dialog import ConnectDialog
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
    def __init__(self, db_path: str = "data/kalvex.db") -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} — Ember Terminal · Paper · {APP_VERSION}")
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.resize(WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT)

        # ---------------- persistence ----------------
        self.db = Database(db_path)
        for k, v in {
            "capital": "500000", "risk_per_trade_pct": "1.0",
            "max_open_positions": "3", "max_lots": "2", "max_orders_per_min": "20",
            "daily_max_loss": "5000", "square_off_time": "15:15",
            "session_open": "09:15", "session_close": "15:30",
            "auto_tune": "1", "options_enabled": "0",
            "options_underlying": "NIFTY", "options_otm_width": "0",
            "options_expiry": "current", "live_enabled": "0",
        }.items():
            if self.db.get_setting(k) == "":
                self.db.set_setting(k, v)

        # ---------------- instruments (Upstox master) ----------------
        self.master = InstrumentMaster("data")

        # ---------------- broker session ----------------
        self.token_store = TokenStore("data")
        self.session = BrokerSession(self.token_store)
        self.api = UpstoxApi(lambda: self.token_store.load()[0])

        # ---------------- feed + engines ----------------
        self.feed = UpstoxLiveFeed(self.api, {})
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
            lot_size=1,   # per-instrument lot sizes come from Upstox rows
        )
        self.bot = BotWorker(self.db, self.feed, self.broker, risk_cfg,
                             mode=BotMode.PAPER, instruments={},
                             cycle_seconds=1.0)
        self.bot.set_api(self.api)

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

        # ---------------- wiring ----------------
        self.nav.page_selected.connect(self._show_page)
        self.top_bar.kill_switch_requested.connect(self._kill_switch)
        self.top_bar.start_stop_clicked.connect(self._toggle_bot)
        self.top_bar.connect_clicked.connect(self._on_connect_clicked)
        self.top_bar.mode_changed.connect(self._on_mode_changed)
        self.page_settings.connect_requested.connect(self._on_connect_clicked)
        self.page_settings.disconnect_requested.connect(self._on_disconnect)
        self.page_settings.api_key.editingFinished.connect(self._save_session_config)
        self.page_settings.api_secret.editingFinished.connect(self._save_session_config)
        self.page_settings.redirect.editingFinished.connect(self._save_session_config)
        self.page_settings.algo_name.editingFinished.connect(self._save_session_config)
        self.page_settings.fetch_master_clicked.connect(self._fetch_master)
        self.bot.thought.connect(self._on_thought)
        self.bot.pnl_update.connect(self._on_pnl)
        self.bot.state_changed.connect(self.top_bar.set_state)
        self.bot.toast.connect(self._on_toast)
        self.bot.semi_confirm.connect(self._on_semi_confirm)
        self.bot.positions_changed.connect(self._refresh_data_pages)
        self.page_strategies.strategy_toggled.connect(self._on_strategy_toggled)
        self.page_strategies.param_changed.connect(self._on_param_changed)

        # ---------------- timers ----------------
        self._feed_timer = QTimer(self)
        self._feed_timer.timeout.connect(self._poll_feed)
        self._feed_timer.start(1000)        # live quotes: 1 poll/sec

        self._ui_timer = QTimer(self)
        self._ui_timer.timeout.connect(self._refresh_ui)
        self._ui_timer.start(1500)
        self._refresh_ui()
        self._load_session_config()   # restore broker config + cached master

        # ---------------- tray ----------------
        self._build_tray()

    # ------------------------------------------------------------------ #
    # instruments
    # ------------------------------------------------------------------ #
    def _apply_master(self) -> None:
        """Build the working book + live feed from the Upstox master."""
        specs = self.master.watchlist()
        book: dict[str, InstrumentSpec] = {s.display: s for s in specs}
        self.bot.set_book(book)
        keys = {s.display: s.key for s in specs if s.resolved and s.key}
        self.feed.set_instruments(keys)
        self.page_charts.set_symbols(list(book.keys()))
        resolved = sum(1 for s in specs if s.resolved)
        self.page_settings.set_master_status(
            f"{self.master.count} rows · fetched {self.master.fetched_at or 'never'}"
            f" · {resolved}/{len(specs)} watchlist indices resolved")
        for s in specs:
            if not s.resolved:
                self.db.log("WARNING", "Feed", "INSTRUMENT_UNKNOWN",
                            f"{s.display}: {s.note}")

    def _fetch_master(self) -> None:
        try:
            n = self.master.fetch()
        except Exception as e:
            self.db.log("ERROR", "Feed", "MASTER_FETCH_FAILED", repr(e)[:200])
            self._on_toast(f"Instrument master fetch failed: {e}")
            return
        self._apply_master()
        self.db.log("INFO", "Feed", "MASTER_FETCHED", f"{n} instruments")
        self._on_toast(f"Instrument master loaded from Upstox ({n} rows).")

    # ------------------------------------------------------------------ #
    # broker session: connect / disconnect
    # ------------------------------------------------------------------ #
    def _load_session_config(self) -> None:
        cfg = {
            "client_id": self.db.get_setting("api_key", ""),
            "client_secret": self.db.get_setting("api_secret", ""),
            "redirect_uri": self.db.get_setting("redirect_uri", ""),
            "algo_name": self.db.get_setting("algo_name", ""),
            "static_ip": self.db.get_setting("static_ip", ""),
        }
        self.session.configure(cfg["client_id"], cfg["client_secret"],
                               cfg["redirect_uri"], cfg["algo_name"],
                               sandbox=True)
        self.page_settings.set_broker_fields(cfg)
        self._refresh_broker_ui()
        self._apply_master()      # load cached master if present

    def _save_session_config(self) -> None:
        cfg = self.page_settings.broker_config()
        for key in ("client_id", "client_secret", "redirect_uri", "algo_name",
                    "static_ip"):
            self.db.set_setting(key, cfg[key])
        self.session.configure(cfg["client_id"], cfg["client_secret"],
                               cfg["redirect_uri"], cfg["algo_name"],
                               sandbox=True)

    def _refresh_broker_ui(self) -> None:
        st = self.session.status()
        connected = st.state == ConnectionState.CONNECTED
        if connected and not self.feed.last_error:
            self.top_bar.set_feed("LIVE · Upstox")
        elif connected:
            self.top_bar.set_feed("LIVE · degraded")
        else:
            self.top_bar.set_feed("NO DATA · disconnected")
        self.page_charts.feed_chip.setText(
            "feed: LIVE Upstox" if connected and not self.feed.last_error
            else "feed: NO DATA")
        self.top_bar.set_broker(st.describe(), st.state.value)
        self.page_settings.set_broker_status(
            st.describe() + (f"  ·  algo={st.algo_name}" if st.algo_name else ""),
            st.state == ConnectionState.CONNECTED)

    def _on_connect_clicked(self) -> None:
        st = self.session.status()
        if st.state == ConnectionState.CONNECTED:
            self._on_disconnect()
            return
        self._save_session_config()
        dlg = ConnectDialog(self.session, self)
        dlg.connected.connect(self._on_broker_connected)
        dlg.exec()

    def _on_broker_connected(self, info: dict) -> None:
        self.db.set_setting("api_key", info["client_id"])
        self.db.set_setting("api_secret", info["client_secret"])
        self.db.set_setting("redirect_uri", info["redirect_uri"])
        self.db.set_setting("algo_name", info["algo_name"])
        self.db.log("INFO", "Auth", "BROKER_CONNECTED",
                    f"token valid until {info['expires_at']} (03:30 IST rule)")
        self._refresh_broker_ui()
        adapter = self.session.adapter()
        self.bot.set_live_broker(adapter)
        try:
            funds = adapter.get_funds()
            avail = float(funds.get("available_margin", 0.0) or 0.0)
            self.top_bar.funds_val.setText(f"₹ {avail:,.0f}")
        except Exception as e:
            self.db.log("WARNING", "Broker", "FUNDS_FETCH_FAILED", repr(e)[:200])
            self.top_bar.funds_val.setText("₹ —")
        self._fetch_master()      # production instruments come from Upstox
        self._on_toast("Upstox CONNECTED — live quotes streaming. Trading "
                       "remains in Paper mode until you switch mode.")

    def _on_disconnect(self) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Disconnect broker")
        box.setText("Disconnect and wipe the stored access token?")
        box.setInformativeText(
            "Live data and live order routing stop until the next daily "
            "OAuth login. Paper trading keeps working with the last quotes.")
        ok = box.addButton("Disconnect", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is not ok:
            return
        self.session.disconnect()
        self.bot.set_live_broker(None)
        self.top_bar.funds_val.setText("₹ —")
        self.db.log("INFO", "Auth", "BROKER_DISCONNECTED", "token wiped")
        self._refresh_broker_ui()
        self._on_toast("Broker disconnected — token wiped.")

    # ------------------------------------------------------------------ #
    # mode switching (Paper / Semi-auto / Auto)
    # ------------------------------------------------------------------ #
    def _on_mode_changed(self, mode: str) -> None:
        bot_mode = {"Paper": BotMode.PAPER, "Semi-auto": BotMode.SEMI_AUTO,
                    "Auto": BotMode.AUTO}.get(mode, BotMode.PAPER)

        if bot_mode == BotMode.AUTO:
            blockers = []
            if self.db.get_state("paper_used", "0") != "1":
                blockers.append("Paper mode has not been used yet")
            if self.session.status().state != ConnectionState.CONNECTED:
                blockers.append("broker is not connected")
            if blockers:
                QMessageBox.warning(
                    self, "Auto mode locked",
                    "Cannot switch to Auto:\n· " + "\n· ".join(blockers))
                self.top_bar.btn_paper.setChecked(True)
                return
            live = QMessageBox.question(
                self, "Enable LIVE order routing?",
                "Auto mode with a connected broker sends REAL orders to "
                "Upstox (hard risk ceilings still apply: 2%/trade, 10 orders/"
                "sec, daily loss flatten, kill switch).\n\n"
                "Choose Yes for LIVE orders, No to run Auto on paper fills.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            live_enabled = live == QMessageBox.StandardButton.Yes
        else:
            live_enabled = False

        self.bot.set_mode(bot_mode, live_enabled=live_enabled)
        self.nav.set_mode_note(bot_mode.value)
        target = self.bot.execution_target.value
        self.db.log("INFO", "UI", "MODE_SWITCH",
                    f"{bot_mode.value} -> execution {target}")
        self._on_toast(f"Mode: {bot_mode.value} — execution: {target}")

    # ------------------------------------------------------------------ #
    # feed polling (live quotes only)
    # ------------------------------------------------------------------ #
    def _poll_feed(self) -> None:
        if self.session.status().state != ConnectionState.CONNECTED:
            return
        ticks = self.feed.poll()
        if ticks and self.bot.state.value == "RUNNING" and \
                hasattr(self.broker, "on_tick"):
            ltps = {n: self.feed.ltp(n) for n in self.bot.book}
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
        self._refresh_broker_ui()
        from kalvex.core import indicators as ind
        sym = self.page_charts.symbol.currentText()
        bars = self.feed.bars(sym) if sym else []
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
            if not self.bot.book:
                QMessageBox.warning(
                    self, "No instruments",
                    "The Upstox instrument master is not loaded — connect "
                    "the broker (or press 'Fetch from Upstox') first. "
                    "The app never trades on placeholder instruments.")
                return
            prev = self.bot
            live = prev.live_broker or (
                self.session.adapter()
                if self.session.status().state == ConnectionState.CONNECTED
                else None)
            self.bot = BotWorker(self.db, self.feed, self.broker,
                                 prev.risk.config, mode=prev.mode,
                                 instruments=prev.book, cycle_seconds=1.0)
            self.bot.set_api(self.api)
            self.bot.set_live_broker(live)
            self.bot.thought.connect(self._on_thought)
            self.bot.pnl_update.connect(self._on_pnl)
            self.bot.state_changed.connect(self.top_bar.set_state)
            self.bot.toast.connect(self._on_toast)
            self.bot.semi_confirm.connect(self._on_semi_confirm)
            self.bot.positions_changed.connect(self._refresh_data_pages)
            self.bot.start()
            self.db.log("INFO", "UI", "BOT_START", f"mode={self.bot.mode.value}")

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
            f"SL {sig.sl:,.2f} · target {sig.target:,.2f} · qty {decision.qty}\n"
            f"Execution target: {self.bot.execution_target.value}\n\n"
            f"{sig.thought}")
        yes = box.addButton("CONFIRM", QMessageBox.ButtonRole.AcceptRole)
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
