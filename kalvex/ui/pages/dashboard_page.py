"""Dashboard: instrument cards + live Decision Stream + session/guard rails."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QPlainTextEdit,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from kalvex.ui.theme import mono_font
from kalvex.ui.widgets import (
    hint_label,
    legend,
    num_label,
    page_header,
    panel_card,
    section_title,
    stat_card,
)


class DashboardPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 12)
        root.setSpacing(10)

        root.addWidget(page_header(
            "Dashboard",
            "Live picture of the automated loop — every value is real engine "
            "state (live Upstox quotes once connected — no synthetic data). All times IST."))

        # ---- instrument row --------------------------------------------
        cards = QHBoxLayout()
        cards.setSpacing(8)
        self.pnl_card = stat_card("P&L TODAY (NET)", "₹ —", " cardCyan", 19)
        self.pos_card = stat_card("OPEN POSITIONS", "—", "", 19)
        self.sig_card = stat_card("SIGNALS TODAY", "—", " cardViolet", 19)
        self.win_card = stat_card("WIN RATE", "—", "", 19)
        self.risk_card = stat_card("RISK BUDGET USED", "—", " cardCoral", 19)
        for c in (self.pnl_card, self.pos_card, self.sig_card, self.win_card,
                  self.risk_card):
            cards.addWidget(c)
        root.addLayout(cards)

        # ---- body: decision stream | side ------------------------------
        body = QHBoxLayout()
        body.setSpacing(10)

        # Decision Stream — the bot's visible thought process
        stream_col = QVBoxLayout()
        stream_col.setSpacing(6)
        head = QHBoxLayout()
        head.addWidget(section_title("DECISION STREAM — THE BOT'S THOUGHT PROCESS"))
        head.addStretch(1)
        head.addWidget(legend("analyse › decide › size › execute › manage › review",
                              faint=True))
        stream_col.addLayout(head)

        self.stream = QPlainTextEdit()
        self.stream.setReadOnly(True)
        self.stream.setFont(mono_font(10))
        self.stream.setStyleSheet(
            "background-color: #10151C; border: 1px solid #222B36;")
        self.stream.setPlaceholderText(
            "the bot's reasoning will stream here as it analyses, decides, "
            "sizes and executes…")
        stream_col.addWidget(self.stream, stretch=1)
        stream_col.addWidget(hint_label(
            "Every entry is persisted in the decision_log table (auditable, "
            "no black-box steps)."))
        left = QWidget()
        left.setLayout(stream_col)
        body.addWidget(left, stretch=3)

        # side: session + guard rails + daily budget
        side = QVBoxLayout()
        side.setSpacing(8)

        sess = QVBoxLayout()
        sess.setSpacing(4)
        self.clock = num_label("—", 22)
        sess.addWidget(legend("market clock · ist"))
        sess.addWidget(self.clock)
        sess.addWidget(legend("time to square-off"))
        self.tts = num_label("—", 14)
        sess.addWidget(self.tts)
        side.addWidget(panel_card("SESSION", "", self._wrap(sess)))

        budget = QVBoxLayout()
        budget.setSpacing(4)
        budget.addWidget(legend("daily loss budget"))
        self.budget_bar = QProgressBar()
        self.budget_bar.setRange(0, 100)
        self.budget_bar.setValue(0)
        self.budget_bar.setFormat("%p% used")
        budget.addWidget(self.budget_bar)
        self.budget_note = hint_label("max loss ₹— · flatten + stop when hit")
        budget.addWidget(self.budget_note)
        side.addWidget(panel_card("RISK CIRCUIT", " cardCoral", self._wrap(budget)))

        guard = QVBoxLayout()
        guard.setSpacing(2)
        for line in (
            "· Hard ceilings cannot be raised from settings",
            "· Trailing SL arms only after min profit",
            "· Options: time exit enforced (theta-aware)",
            "· Kill switch = cancel + flatten + stop",
            "· Unattended only inside session hours",
        ):
            lbl = hint_label(line)
            guard.addWidget(lbl)
        side.addWidget(panel_card("GUARD RAILS", " cardViolet", self._wrap(guard)))

        side.addStretch(1)
        right = QWidget()
        right.setLayout(side)
        right.setFixedWidth(330)
        body.addWidget(right)
        root.addLayout(body, stretch=1)

        root.addWidget(hint_label(
            "Specification/tooling only — not trading advice. Paper is the default mode."))

    @staticmethod
    def _wrap(inner: QVBoxLayout) -> QWidget:
        w = QWidget()
        w.setLayout(inner)
        return w

    # ------------------------------------------------------------------ #
    def append_thought(self, ev: dict) -> None:
        stage = ev.get("stage", "?")
        color = {
            "ANALYSE": "#8B7CFF", "DECIDE": "#FFB020", "SIZE": "#35D0C8",
            "EXECUTE": "#E8EEF6", "MANAGE": "#FF8A3D", "REVIEW": "#8B7CFF",
            "RISK": "#FF5D5D", "SYSTEM": "#7A8798",
        }.get(stage, "#E8EEF6")
        self.stream.appendHtml(
            f'<span style="color:#4A5665">{ev.get("ts","")}</span> '
            f'<span style="color:{color}; font-weight:700">[{stage}]</span> '
            f'<span style="color:#B8C4D2">{ev.get("strategy","·")}</span> '
            f'<span style="color:#E8EEF6">{ev.get("text","")}</span>')
        sb = self.stream.verticalScrollBar()
        sb.setValue(sb.maximum())

    def set_metrics(self, realised: float, unrealised: float, open_pos: int,
                    signals: int, win_rate: float | None,
                    risk_used_pct: float, max_loss: float) -> None:
        total = realised + unrealised
        pnl_lbl = self.pnl_card.value_label
        pnl_lbl.setText(f"₹ {total:,.0f}")
        pnl_lbl.setStyleSheet(
            f"color: {'#35D0C8' if total >= 0 else '#FF5D5D'};")
        self.pos_card.value_label.setText(str(open_pos))
        self.sig_card.value_label.setText(str(signals))
        self.win_card.value_label.setText(
            "—" if win_rate is None else f"{win_rate:.0%}")
        self.risk_card.value_label.setText(f"{risk_used_pct:.0f}%")
        self.budget_bar.setValue(min(100, int(risk_used_pct)))
        self.budget_note.setText(
            f"max loss ₹{max_loss:,.0f} · flatten + stop when hit")
