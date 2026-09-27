"""Command strip (top bar): brand, session chip, funds, live P&L, bot state,
mode selector (Paper default; Auto locked until Paper used), KILL SWITCH."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from kalvex.core.constants import AUTO_MODE_LOCKED, BotMode
from kalvex.ui.theme import label_font
from kalvex.ui.widgets import legend, num_label


class TopBar(QFrame):
    mode_changed = Signal(str)
    kill_switch_requested = Signal()
    start_stop_clicked = Signal()
    connect_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("topBar")
        self.setFixedHeight(72)

        root = QHBoxLayout(self)
        root.setContentsMargins(16, 8, 16, 8)
        root.setSpacing(12)

        # --- brand -------------------------------------------------------
        brand_box = QVBoxLayout()
        brand_box.setSpacing(0)
        brand = QLabel("KΛLVEX PRO")
        brand.setObjectName("brand")
        brand_box.addWidget(brand)
        sub = QLabel("EMBER TERMINAL · UPSTOX · SPEC BUILD")
        sub.setObjectName("brandSub")
        sub.setFont(label_font(8))
        brand_box.addWidget(sub)
        root.addLayout(brand_box)

        self.feed_chip, self.feed_val = self._chip(
            "FEED", "NO DATA · disconnected", "chipViolet")
        root.addWidget(self.feed_chip)
        self.funds_chip, self.funds_val = self._chip("FUNDS", "₹ —", "")
        root.addWidget(self.funds_chip)
        self.pnl_chip, self.pnl_val = self._chip("P&L TODAY", "₹ —", "chipCyan")
        root.addWidget(self.pnl_chip)

        root.addStretch(1)

        # --- broker connection ------------------------------------------
        self.broker_chip, self.broker_val = self._chip("BROKER", "DISCONNECTED", "chipRed")
        root.addWidget(self.broker_chip)
        self.connect_btn = QPushButton("CONNECT")
        self.connect_btn.setObjectName("ember")
        self.connect_btn.setToolTip(
            "Upstox OAuth login (daily — token expires 03:30 IST, no refresh "
            "token). Disconnect wipes the stored token.")
        self.connect_btn.clicked.connect(self.connect_clicked.emit)
        root.addWidget(self.connect_btn)

        # --- bot state ---------------------------------------------------
        self.state_chip, self.state_val = self._chip("BOT", "IDLE", "")
        root.addWidget(self.state_chip)

        # --- mode selector -----------------------------------------------
        m_lbl = legend("mode")
        root.addWidget(m_lbl)
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.btn_paper = self._seg("Paper", BotMode.PAPER.value, left=True)
        self.btn_semi = self._seg("Semi-auto", BotMode.SEMI_AUTO.value)
        self.btn_auto = self._seg("Auto", BotMode.AUTO.value, right=True)
        seg_box = QHBoxLayout()
        seg_box.setSpacing(0)
        for b in (self.btn_paper, self.btn_semi, self.btn_auto):
            seg_box.addWidget(b)
        root.addLayout(seg_box)
        self.btn_paper.setChecked(True)
        if AUTO_MODE_LOCKED:
            self.btn_auto.setEnabled(False)
            self.btn_auto.setToolTip(
                "Locked: Auto unlocks only after Paper mode has been used "
                "(and the live opt-in phase). Paper is the default.")
        self.mode_group.buttonClicked.connect(
            lambda b: self.mode_changed.emit(b.property("mode")))

        # --- start/stop + kill -------------------------------------------
        self.start_btn = QPushButton("▶ START BOT")
        self.start_btn.setObjectName("ember")
        self.start_btn.clicked.connect(self.start_stop_clicked.emit)
        root.addWidget(self.start_btn)

        self.kill_btn = QPushButton("■ KILL SWITCH")
        self.kill_btn.setObjectName("kill")
        self.kill_btn.setToolTip(
            "Cancel all open orders, flatten all positions, stop immediately.")
        self.kill_btn.clicked.connect(self._confirm_kill)
        root.addWidget(self.kill_btn)

    # ------------------------------------------------------------------ #
    def _chip_frame(self, leg: str, value: str, accent: str) -> QFrame:
        return self._chip(leg, value, accent)[0]

    def _chip(self, leg: str, value: str, accent: str):
        f = QFrame()
        f.setObjectName("chip" + accent)
        lay = QVBoxLayout(f)
        lay.setContentsMargins(10, 4, 10, 4)
        lay.setSpacing(0)
        lay.addWidget(legend(leg))
        v = num_label(value, size=13)
        lay.addWidget(v)
        return f, v

    def _seg(self, text: str, mode: str, left: bool = False,
             right: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setProperty("mode", mode)
        btn.setObjectName(
            "seg segButtonLeft" if left else ("seg segButtonRight" if right else "seg"))
        self.mode_group.addButton(btn)
        return btn

    # ------------------------------------------------------------------ #
    def set_pnl(self, realised: float, unrealised: float) -> None:
        total = realised + unrealised
        self.pnl_val.setText(f"₹ {total:,.0f}")
        self.pnl_val.setStyleSheet(
            f"color: {'#35D0C8' if total >= 0 else '#FF5D5D'};")

    def set_state(self, state: str) -> None:
        self.state_val.setText(state)
        if state == "RUNNING":
            self.state_val.setStyleSheet("color: #35D0C8;")
            self.start_btn.setText("■ STOP BOT")
        elif state in ("KILLED", "FLATTENING"):
            self.state_val.setStyleSheet("color: #FF5D5D;")
            self.start_btn.setText("▶ START BOT")
        else:
            self.state_val.setStyleSheet("color: #E8EEF6;")
            self.start_btn.setText("▶ START BOT")

    def set_feed(self, text: str) -> None:
        self.feed_val.setText(text)
        live = text.startswith("LIVE")
        self.feed_val.setStyleSheet(
            f"color: {'#35D0C8' if live else '#8B93A1'};")
        self.feed_val.setToolTip(
            "Live Upstox quotes (1 poll/sec)" if live else
            "No market data — connect the broker. The app never shows "
            "synthetic prices.")

    def set_broker(self, describe: str, state: str) -> None:
        """state: ConnectionState value — drives chip colour + button label."""
        short = describe
        if len(short) > 30:
            short = short.split(" · token")[0] + " · until 03:30 IST"
        self.broker_val.setText(short)
        self.broker_val.setToolTip(describe)
        if state == "CONNECTED":
            self.broker_val.setStyleSheet("color: #35D0C8;")
            self.connect_btn.setText("DISCONNECT")
            self.connect_btn.setObjectName("ghost")
        elif state in ("EXPIRED", "ERROR"):
            self.broker_val.setStyleSheet("color: #FF5D5D;")
            self.connect_btn.setText("RE-LOGIN")
            self.connect_btn.setObjectName("ember")
        elif state == "CONNECTING":
            self.broker_val.setStyleSheet("color: #FFB020;")
            self.connect_btn.setText("CONNECTING…")
            self.connect_btn.setObjectName("ember")
        else:
            self.broker_val.setStyleSheet("color: #E8EEF6;")
            self.connect_btn.setText("CONNECT")
            self.connect_btn.setObjectName("ember")
        self.connect_btn.style().unpolish(self.connect_btn)
        self.connect_btn.style().polish(self.connect_btn)

    def _confirm_kill(self) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("KILL SWITCH")
        box.setText("Stop everything immediately?")
        box.setInformativeText(
            "Cancels all open orders, flattens all positions and stops the bot.\n"
            "This is the emergency control — it works in every mode.")
        ok = box.addButton("EXECUTE KILL SWITCH", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(box.buttons()[-1])
        box.exec()
        if box.clickedButton() is ok:
            self.kill_switch_requested.emit()
