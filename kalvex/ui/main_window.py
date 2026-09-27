"""Main window: top bar + left nav + page stack + status bar + system tray.

UI layout skeleton — no bot threads, no websocket, no broker calls.
Those come later behind PaperEngine / LiveBrokerAdapter with a shared interface.
"""

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

from kalvex.core.constants import (
    APP_NAME,
    APP_VERSION,
    PAGE_TITLES,
    WINDOW_DEFAULT_HEIGHT,
    WINDOW_DEFAULT_WIDTH,
    WINDOW_MIN_HEIGHT,
    WINDOW_MIN_WIDTH,
    PageId,
)
from kalvex.ui.nav_sidebar import NavSidebar
from kalvex.ui.pages.activity_page import ActivityPage
from kalvex.ui.pages.charts_page import ChartsPage
from kalvex.ui.pages.dashboard_page import DashboardPage
from kalvex.ui.pages.logs_page import LogsPage
from kalvex.ui.pages.settings_page import SettingsPage
from kalvex.ui.pages.strategies_page import StrategiesPage
from kalvex.ui.top_bar import TopBar

IST = ZoneInfo("Asia/Kolkata")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} — Paper Trading (UI Layout Preview)")
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.resize(WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT)

        # ---------- central layout ----------
        central = QWidget()
        central.setObjectName("root")
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.top_bar = TopBar()
        outer.addWidget(self.top_bar)

        body = QWidget()
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(0)

        row_lay2 = QHBoxLayout()
        row_lay2.setContentsMargins(0, 0, 0, 0)
        row_lay2.setSpacing(0)

        self.nav = NavSidebar()
        row_lay2.addWidget(self.nav)

        self.stack = QStackedWidget()
        self.pages: dict[str, QWidget] = {
            PageId.DASHBOARD.value: DashboardPage(),
            PageId.CHARTS.value: ChartsPage(),
            PageId.STRATEGIES.value: StrategiesPage(),
            PageId.ACTIVITY.value: ActivityPage(),
            PageId.LOGS.value: LogsPage(),
            PageId.SETTINGS.value: SettingsPage(),
        }
        self._page_order = [
            PageId.DASHBOARD.value,
            PageId.CHARTS.value,
            PageId.STRATEGIES.value,
            PageId.ACTIVITY.value,
            PageId.LOGS.value,
            PageId.SETTINGS.value,
        ]
        for key in self._page_order:
            self.stack.addWidget(self.pages[key])
        row_lay2.addWidget(self.stack, stretch=1)

        row = QWidget()
        row.setLayout(row_lay2)
        body_lay.addWidget(row)
        outer.addWidget(body, stretch=1)

        self.setCentralWidget(central)

        # ---------- wiring ----------
        self.nav.page_selected.connect(self._show_page)
        self.top_bar.mode_changed.connect(self._on_mode_changed)
        self.top_bar.kill_switch_requested.connect(self._on_kill_switch)

        # ---------- status bar ----------
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._tick_clock)
        self._clock_timer.start(1000)
        self._tick_clock()

        # ---------- system tray ----------
        self._build_tray()

    # ------------------------------------------------------------------ #
    # Pages
    # ------------------------------------------------------------------ #
    def _show_page(self, page_id: str) -> None:
        self.stack.setCurrentWidget(self.pages[page_id])
        self.setWindowTitle(f"{APP_NAME} — {PAGE_TITLES[PageId(page_id)]} (Paper)")

    def _on_mode_changed(self, mode: str) -> None:
        self.nav.set_mode_note(mode)

    def _on_kill_switch(self) -> None:
        # UI skeleton: nothing to cancel yet; the dialog in TopBar already ran.
        pass

    # ------------------------------------------------------------------ #
    # Status bar clock (IST)
    # ------------------------------------------------------------------ #
    def _tick_clock(self) -> None:
        now = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")
        self.statusBar().showMessage(
            f"PAPER MODE • Disconnected • Sandbox toggle: ON • Layout build v{APP_VERSION} • {now}"
        )

    # ------------------------------------------------------------------ #
    # Tray
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
        act_start_paper = QAction("Start Paper bot (placeholder)", self)
        act_start_paper.setEnabled(False)
        menu.addAction(act_start_paper)

        act_stop = QAction("Stop bot (placeholder)", self)
        act_stop.setEnabled(False)
        menu.addAction(act_stop)

        menu.addSeparator()
        act_kill = QAction("KILL SWITCH", self)
        act_kill.triggered.connect(self.top_bar._confirm_kill_switch)
        menu.addAction(act_kill)

        menu.addSeparator()
        act_quit = QAction("Quit", self)
        act_quit.triggered.connect(self.close)
        menu.addAction(act_quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle_visible()

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
        box.setText("Minimize to tray instead of quitting?")
        box.setInformativeText(
            "The tray keeps the bot reachable during market hours (after Paper mode has been validated). "
            "Choose Quit to fully exit this layout preview."
        )
        to_tray = box.addButton("Minimize to tray", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Quit", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is to_tray:
            self.hide()
            self.tray.showMessage(
                APP_NAME,
                "Still running in the tray. Use the tray menu for kill switch.",
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )
            event.ignore()
        else:
            self.tray.hide()
            event.accept()
