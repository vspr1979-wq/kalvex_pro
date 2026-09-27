"""Positions / Orders / Trades — live tables backed by SQLite."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from kalvex.ui.widgets import hint_label, make_table


class ActivityPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 12)
        root.setSpacing(10)

        head = QHBoxLayout()
        title = QLabel("POSITIONS / ORDERS")
        title.setObjectName("title")
        head.addWidget(title)
        head.addStretch(1)
        refresh = QPushButton("↻ REFRESH")
        refresh.setObjectName("ghost")
        refresh.clicked.connect(self._noop_refresh)
        head.addWidget(refresh)
        root.addLayout(head)

        self.tabs = QTabWidget()
        self.positions_table = make_table(
            ["Instrument", "Qty", "Avg", "LTP", "P&L", "SL", "Target",
             "Strategy", "Source", "Opened"],
            stretch_cols=(0,))
        self.orders_table = make_table(
            ["Time (IST)", "Tag", "Instrument", "Side", "Type", "Qty", "Price",
             "Status", "Source", "Strategy"],
            stretch_cols=(1, 2))
        self.trades_table = make_table(
            ["Time (IST)", "Instrument", "Side", "Qty", "Price", "Fee",
             "P&L", "Strategy", "Source"],
            stretch_cols=(1,))
        self.tabs.addTab(self._wrap(self.positions_table), "Positions")
        self.tabs.addTab(self._wrap(self.orders_table), "Orders (full trail)")
        self.tabs.addTab(self._wrap(self.trades_table), "Trades / Fills")
        root.addWidget(self.tabs, stretch=1)

        root.addWidget(hint_label(
            "Paper fills are simulated from LTP with slippage + fee model; "
            "live fills will come from the broker. Every order carries a "
            "client tag used for restart dedupe. v1 order policy: LIMIT / "
            "SL-L only — raw MARKET not sent (UNKNOWN per current algo rules)."))

    @staticmethod
    def _wrap(w: QWidget) -> QWidget:
        box = QVBoxLayout()
        box.setContentsMargins(6, 6, 6, 6)
        box.addWidget(w)
        holder = QWidget()
        holder.setLayout(box)
        return holder

    def _noop_refresh(self) -> None:
        pass  # wired by MainWindow

    # ------------------------------------------------------------------ #
    def set_positions(self, rows: list[list[str]]) -> None:
        from kalvex.ui.widgets import set_placeholder_rows
        set_placeholder_rows(self.positions_table, rows)

    def set_orders(self, rows: list[list[str]]) -> None:
        from kalvex.ui.widgets import set_placeholder_rows
        set_placeholder_rows(self.orders_table, rows)

    def set_trades(self, rows: list[list[str]]) -> None:
        from kalvex.ui.widgets import set_placeholder_rows
        set_placeholder_rows(self.trades_table, rows)
