"""Top bar: connection, funds, live PnL, bot state, bot-mode selector, kill switch.

Layout only — every value is a placeholder. Paper is the default mode and
Auto is rendered disabled until the Paper-first gate is satisfied.
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from kalvex.core.constants import AUTO_MODE_LOCKED, BotMode


class TopBar(QFrame):
    """Persistent top bar shown on every page."""

    # UI-only signals for the skeleton (nothing is wired to a broker yet).
    mode_changed = Signal(str)
    kill_switch_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("topBar")
        self.setFixedHeight(66)

        root = QHBoxLayout(self)
        root.setContentsMargins(16, 8, 16, 8)
        root.setSpacing(14)

        # --- app identity ---
        title = QLabel("KALVEX PRO")
        title.setObjectName("appTitle")
        root.addWidget(title)

        paper_badge = QLabel("PAPER TRADING DEFAULT")
        paper_badge.setObjectName("pill pillAmber")
        root.addWidget(paper_badge)

        root.addSpacing(8)

        # --- connection status ---
        self.conn_pill = QLabel("● Disconnected")
        self.conn_pill.setObjectName("pill")
        root.addWidget(self.conn_pill)

        # --- KPIs ---
        self.funds_card = self._compact_metric("FUNDS", "₹ —")
        self.pnl_card = self._compact_metric("LIVE P&L", "₹ —")
        root.addWidget(self.funds_card)
        root.addWidget(self.pnl_card)

        root.addStretch(1)

        # --- bot state ---
        self.bot_state_pill = QLabel("BOT: IDLE")
        self.bot_state_pill.setObjectName("pill")
        root.addWidget(self.bot_state_pill)

        # --- bot mode segmented control ---
        root.addWidget(self._mode_label("Mode:"))
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)

        self.btn_paper = self._seg_button("Paper", "Paper", left=True)
        self.btn_semi = self._seg_button("Semi-auto", BotMode.SEMI_AUTO.value)
        self.btn_auto = self._seg_button("Auto", BotMode.AUTO.value, right=True)

        seg = QWidget()
        seg_lay = QHBoxLayout(seg)
        seg_lay.setContentsMargins(0, 0, 0, 0)
        seg_lay.setSpacing(0)
        for b in (self.btn_paper, self.btn_semi, self.btn_auto):
            seg_lay.addWidget(b)
        root.addWidget(seg)

        # Paper is the default mode.
        self.btn_paper.setChecked(True)
        if AUTO_MODE_LOCKED:
            self.btn_auto.setEnabled(False)
            self.btn_auto.setToolTip(
                "Locked: Auto mode unlocks only after Paper mode has been used "
                "(live auto-trading is a later opt-in phase with hard risk limits)."
            )
        self.mode_group.buttonClicked.connect(self._on_mode_clicked)

        # --- kill switch ---
        self.kill_btn = QPushButton("KILL SWITCH")
        self.kill_btn.setObjectName("killSwitch")
        self.kill_btn.setToolTip(
            "Cancel all open orders, flatten positions, stop the bot immediately."
        )
        self.kill_btn.clicked.connect(self._confirm_kill_switch)
        root.addWidget(self.kill_btn)

        root.addStretch(0)

    # ------------------------------------------------------------------ #
    def _compact_metric(self, title: str, value: str) -> QWidget:
        """Inline metric used inside the top bar (narrower than page cards)."""
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        t = QLabel(title)
        t.setObjectName("metricTitle")
        v = QLabel(value)
        v.setObjectName("metricValue")
        lay.addWidget(t)
        lay.addWidget(v)
        w.setFixedWidth(120)
        w.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        return w

    @staticmethod
    def _mode_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("metricTitle")
        return lbl

    def _seg_button(self, text: str, mode: str, left: bool = False, right: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setProperty("mode", mode)
        if left:
            btn.setObjectName("segButton segButtonLeft")
        elif right:
            btn.setObjectName("segButton segButtonRight")
        else:
            btn.setObjectName("segButton")
        self.mode_group.addButton(btn)
        return btn

    def _on_mode_clicked(self, btn: QPushButton) -> None:
        self.mode_changed.emit(btn.property("mode"))

    def _confirm_kill_switch(self) -> None:
        """Confirmation dialog (UI only — nothing is cancelled/flatenned yet)."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Kill Switch")
        box.setText("Stop everything immediately?")
        box.setInformativeText(
            "This will cancel all open orders, flatten open positions and stop the bot.\n"
            "(UI preview — no orders exist and no broker is connected.)"
        )
        ok = box.addButton("EXECUTE KILL SWITCH", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(box.buttons()[-1])  # default = Cancel, safer UX
        box.exec()
        if box.clickedButton() is ok:
            self.bot_state_pill.setText("BOT: STOPPED (KILL)")
            self.bot_state_pill.setObjectName("pill pillRed")
            self.bot_state_pill.style().unpolish(self.bot_state_pill)
            self.bot_state_pill.style().polish(self.bot_state_pill)
            self.kill_switch_requested.emit()
