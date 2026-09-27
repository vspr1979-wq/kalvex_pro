"""Strategy Manager page — table of the small v1 strategy set (layout only)."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from kalvex.core.constants import STRATEGY_NAMES
from kalvex.ui.widgets import hint_label, make_table, page_header, section_title


class StrategiesPage(QWidget):
    """Strategy table: name, on/off, mode, positions, today PnL, start/stop/edit."""

    HEADERS = ["Strategy", "On/Off", "Mode", "Open Positions", "Today P&L", "Actions"]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(12)

        root.addWidget(
            page_header(
                "Strategy Manager",
                "Enable and configure a SMALL set of strategies. Rows below are the planned v1 set — "
                "no logic runs in this layout build.",
            )
        )

        # --- toolbar ---
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        add_btn = QPushButton("Add strategy (later)")
        add_btn.setObjectName("secondary")
        add_btn.setEnabled(False)
        toolbar.addWidget(add_btn)

        filter_mode = QComboBox()
        filter_mode.addItems(["All modes", "Paper", "Semi-auto", "Auto"])
        filter_mode.setCurrentIndex(0)
        filter_mode.setMinimumWidth(140)
        toolbar.addWidget(filter_mode)

        toolbar.addStretch(1)
        toolbar.addWidget(hint_label("Auto entries stay disabled until Paper mode has been used."))
        root.addLayout(toolbar)

        # --- strategy table ---
        self.table: QTableWidget = make_table(list(self.HEADERS), stretch_cols=(0,))
        self._fill_sample_rows()
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, header.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, header.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, header.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, header.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, header.ResizeMode.Fixed)
        self.table.setColumnWidth(5, 250)
        root.addWidget(self.table, stretch=1)

        root.addWidget(section_title("LATER / OVERLAY-ONLY (NOT LIVE AUTO-ENTRY IN V1)"))
        root.addWidget(
            hint_label(
                "Nice-to-have: Bollinger squeeze, MACD momentum. "
                "SMC (FVG/OB/BOS/CHoCH) via smartmoneyconcepts is a chart overlay + optional alert only — "
                "never the sole live strategy."
            )
        )

    def _fill_sample_rows(self) -> None:
        """Static placeholder rows for the planned v1 strategy set."""
        self.table.setRowCount(len(STRATEGY_NAMES))
        for r, name in enumerate(STRATEGY_NAMES):
            self.table.setItem(r, 0, self._item(name))

            on_off = QCheckBox()
            on_off.setChecked(False)
            on_off.setStyleSheet("margin-left: 12px;")
            self.table.setCellWidget(r, 1, on_off)

            mode = QComboBox()
            mode.addItems(["Paper", "Semi-auto", "Auto (locked)"])
            mode.setCurrentIndex(0)
            mode.setMinimumWidth(130)
            mode.setMaximumWidth(150)
            self.table.setCellWidget(r, 2, mode)

            self.table.setItem(r, 3, self._item("—"))
            self.table.setItem(r, 4, self._item("—"))

            actions = QWidget()
            actions_lay = QHBoxLayout(actions)
            actions_lay.setContentsMargins(4, 2, 4, 2)
            actions_lay.setSpacing(6)
            for label, enabled in (("Start", True), ("Stop", False), ("Edit", True)):
                btn = QPushButton(label)
                btn.setObjectName("secondary")
                btn.setEnabled(enabled)
                btn.setFixedWidth(72)
                actions_lay.addWidget(btn)
            actions_lay.addStretch(1)
            self.table.setCellWidget(r, 5, actions)

    @staticmethod
    def _item(text: str):
        from PySide6.QtWidgets import QTableWidgetItem

        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return item
