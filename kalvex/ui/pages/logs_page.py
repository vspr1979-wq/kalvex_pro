"""Logs page — signal / order / system event trail in IST."""

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from kalvex.ui.widgets import hint_label, make_table, page_header


class LogsPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(12)

        root.addWidget(
            page_header(
                "Logs",
                "Every signal, order, modify, cancel, fill and reject — timestamped in IST. "
                "Secrets and tokens are never written to logs.",
            )
        )

        # --- filter bar ---
        bar = QHBoxLayout()
        bar.setSpacing(8)

        self.level_filter = QComboBox()
        self.level_filter.addItems(["All levels", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.level_filter.setMinimumWidth(140)
        bar.addWidget(self.level_filter)

        self.source_filter = QComboBox()
        self.source_filter.addItems(["All sources", "Bot", "Risk", "Orders", "Broker", "Feed", "UI", "Auth"])
        self.source_filter.setMinimumWidth(140)
        bar.addWidget(self.source_filter)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search event text…")
        self.search.setMinimumWidth(240)
        bar.addWidget(self.search)

        export_btn = QPushButton("Export (placeholder)")
        export_btn.setObjectName("secondary")
        export_btn.setEnabled(False)
        bar.addWidget(export_btn)

        bar.addStretch(1)
        root.addLayout(bar)

        # --- log table ---
        self.logs_table = make_table(
            ["Time (IST)", "Level", "Source", "Event", "Details"],
            stretch_cols=(3, 4),
        )
        root.addWidget(self.logs_table, stretch=1)

        root.addWidget(
            hint_label(
                "Retention lives in SQLite (logs table). Sandbox/test events are tagged so they can be filtered out."
            )
        )
