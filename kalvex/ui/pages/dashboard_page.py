"""Dashboard page — KPI cards, session panel, recent activity placeholders."""

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from kalvex.ui.widgets import (
    empty_state,
    hint_label,
    metric_card,
    page_header,
    placeholder_panel,
    section_block,
)


class DashboardPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(14)

        root.addWidget(
            page_header(
                "Dashboard",
                "Market overview and bot status — values are placeholders in this layout build. "
                "All times shown in IST.",
            )
        )

        # --- KPI card row ---
        cards = QHBoxLayout()
        cards.setSpacing(12)
        for title, value in (
            ("TODAY'S P&L (PAPER)", "₹ —"),
            ("OPEN POSITIONS", "—"),
            ("ORDERS TODAY", "—"),
            ("RISK USED (DAILY LOSS LIMIT)", "—"),
            ("STRATEGIES RUNNING", "—"),
        ):
            cards.addWidget(metric_card(title, value))
        cards.addStretch(1)
        root.addLayout(cards)

        # --- two-column body ---
        body = QHBoxLayout()
        body.setSpacing(12)

        # Left: recent signals / bot activity
        left_col = QVBoxLayout()
        left_col.setSpacing(12)
        left_col.addWidget(section_block("RECENT SIGNALS", []))
        left_col.addWidget(empty_state("No signals yet — signals will appear here as the bot evaluates strategies."))
        left_col.addWidget(placeholder_panel("Bot activity timeline (tick → indicator → signal → order → fill)", min_height=220))
        left_col.addStretch(1)

        # Right: session + guard rails
        right_col = QVBoxLayout()
        right_col.setSpacing(12)
        right_col.addWidget(
            section_block(
                "SESSION",
                [],
                note="Market hours 09:15–15:30 IST • Square-off 15:15 IST (user-configurable). "
                "Unattended operation only during market hours and only after Paper mode has been used.",
            )
        )
        right_col.addWidget(metric_card("MARKET CLOCK (IST)", "—"))
        right_col.addWidget(metric_card("TIME TO SQUARE-OFF", "—"))
        right_col.addWidget(
            section_block(
                "GUARD RAILS",
                [],
                note="Daily max loss → flatten + stop bot. Kill switch always available in the top bar "
                "and tray. Trailing SL only after a minimum profit (per settings).",
            )
        )
        right_col.addStretch(1)

        left = QWidget()
        left.setLayout(left_col)
        right = QWidget()
        right.setLayout(right_col)
        body.addWidget(left, stretch=3)
        body.addWidget(right, stretch=2)
        root.addLayout(body, stretch=1)

        root.addWidget(hint_label("Spec note: this is a specification/UI artifact, not live trading advice."))
