"""Logs page — every signal/order/system event, IST, secrets redacted."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from kalvex.ui.widgets import hint_label, make_table, page_header, set_placeholder_rows


class LogsPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 12)
        root.setSpacing(10)

        root.addWidget(page_header(
            "Logs",
            "Every signal, order, modify, cancel, fill and reject — "
            "timestamped IST. Tokens/secrets are redacted before writing."))

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.level_filter = QComboBox()
        self.level_filter.addItems(["All levels", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.level_filter.setMinimumWidth(130)
        bar.addWidget(self.level_filter)
        self.source_filter = QComboBox()
        self.source_filter.addItems(
            ["All sources", "Bot", "Risk", "Orders", "Broker", "Feed", "UI", "Auth"])
        self.source_filter.setMinimumWidth(130)
        bar.addWidget(self.source_filter)
        self.search = QLineEdit()
        self.search.setPlaceholderText("search…")
        self.search.setMinimumWidth(200)
        bar.addWidget(self.search)
        self.refresh_btn = QPushButton("↻ REFRESH")
        self.refresh_btn.setObjectName("ghost")
        bar.addWidget(self.refresh_btn)
        bar.addStretch(1)
        root.addLayout(bar)

        self.table = make_table(
            ["Time (IST)", "Level", "Source", "Event", "Detail"],
            stretch_cols=(3, 4))
        root.addWidget(self.table, stretch=1)
        root.addWidget(hint_label(
            "Retention: SQLite logs table. Sandbox/test events are tagged."))

    def set_logs(self, rows: list[list[str]]) -> None:
        level = self.level_filter.currentText()
        source = self.source_filter.currentText()
        needle = self.search.text().strip().lower()
        filtered = []
        for row in rows:
            if level != "All levels" and row[1] != level:
                continue
            if source != "All sources" and row[2] != source:
                continue
            if needle and needle not in " ".join(row).lower():
                continue
            filtered.append(row)
        set_placeholder_rows(self.table, filtered[-400:])
