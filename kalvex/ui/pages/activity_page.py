"""Positions / Orders / Trades page — three empty tables with filter bars."""

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from kalvex.ui.widgets import hint_label, make_table, page_header


class ActivityPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(12)

        root.addWidget(
            page_header(
                "Positions / Orders",
                "Working positions, the full order trail and fills. Every signal, order, modify, "
                "cancel, fill and reject is logged in IST.",
            )
        )

        self.tabs = QTabWidget()
        self.tabs.addTab(self._positions_tab(), "Positions")
        self.tabs.addTab(self._orders_tab(), "Orders")
        self.tabs.addTab(self._trades_tab(), "Trades")
        root.addWidget(self.tabs, stretch=1)

        root.addWidget(hint_label("Paper fills are simulated from LTP/quote; live fills come from the broker — both land in the same tables."))

    # ------------------------------------------------------------------ #
    def _filter_bar(self, extra_widget: QWidget | None = None) -> QWidget:
        bar = QWidget()
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(0, 0, 0, 8)
        lay.setSpacing(8)

        segment = QComboBox()
        segment.addItems(["All segments", "Equity", "F&O (futures)", "Index options (opt-in)"])
        segment.setMinimumWidth(180)
        segment.setMaximumWidth(220)
        lay.addWidget(segment)

        if extra_widget is not None:
            lay.addWidget(extra_widget)

        refresh = QPushButton("Refresh (placeholder)")
        refresh.setObjectName("secondary")
        refresh.setEnabled(False)
        lay.addWidget(refresh)

        flatten = QPushButton("Square-off all")
        flatten.setObjectName("secondary")
        flatten.setEnabled(False)
        flatten.setToolTip("Placeholder — flattens paper/live positions in a later phase.")
        lay.addWidget(flatten)

        lay.addStretch(1)
        return bar

    def _positions_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.addWidget(self._filter_bar())
        self.positions_table = make_table(
            ["Symbol", "Product", "Qty", "Avg Price", "LTP", "P&L", "SL", "Target", "Strategy", "Actions"],
            stretch_cols=(0, 8),
        )
        lay.addWidget(self.positions_table)
        return w

    def _orders_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        status_label = QLabel("Status:")
        status = QComboBox()
        status.addItems(["All", "Pending", "Filled", "Cancelled", "Rejected"])
        status.setMinimumWidth(130)
        status_row = QWidget()
        status_lay = QHBoxLayout(status_row)
        status_lay.setContentsMargins(0, 0, 0, 0)
        status_lay.setSpacing(8)
        status_lay.addWidget(status_label)
        status_lay.addWidget(status)
        lay.addWidget(self._filter_bar(status_row))
        self.orders_table = make_table(
            ["Time (IST)", "Symbol", "Side", "Type", "Qty", "Price", "Status", "Strategy", "Broker Order ID"],
            stretch_cols=(1, 7),
        )
        lay.addWidget(self.orders_table)
        lay.addWidget(
            hint_label(
                "v1 order types: prefer Limit / SL-L (and GTT if available). Raw MARKET orders only if "
                "current Upstox algo/API rules allow them — otherwise UNKNOWN/locked."
            )
        )
        return w

    def _trades_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.addWidget(self._filter_bar())
        self.trades_table = make_table(
            ["Time (IST)", "Symbol", "Side", "Qty", "Fill Price", "P&L", "Source", "Order ID"],
            stretch_cols=(1,),
        )
        lay.addWidget(self.trades_table)
        lay.addWidget(hint_label("Source column distinguishes simulated Paper fills from live broker fills."))
        return w
