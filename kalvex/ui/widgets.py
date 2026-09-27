"""Shared lightweight widgets/helpers used across pages (layout only)."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


def page_header(title: str, subtitle: str = "") -> QWidget:
    """Standard page title + muted subtitle block."""
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 4)
    lay.setSpacing(2)
    t = QLabel(title)
    t.setObjectName("pageTitle")
    lay.addWidget(t)
    if subtitle:
        s = QLabel(subtitle)
        s.setObjectName("pageSubtitle")
        s.setWordWrap(True)
        lay.addWidget(s)
    return w


def empty_state(text: str) -> QLabel:
    """Centered muted placeholder for empty tables/panels."""
    lbl = QLabel(text)
    lbl.setObjectName("emptyState")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setWordWrap(True)
    return lbl


def hint_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("hint")
    lbl.setWordWrap(True)
    return lbl


def section_title(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("sectionTitle")
    return lbl


def metric_card(title: str, value: str = "—", value_color: str | None = None) -> QFrame:
    """Small KPI card: muted title on top, big value below."""
    card = QFrame()
    card.setObjectName("card")
    lay = QVBoxLayout(card)
    lay.setContentsMargins(14, 12, 14, 12)
    lay.setSpacing(4)

    t = QLabel(title)
    t.setObjectName("metricTitle")
    lay.addWidget(t)

    v = QLabel(value)
    v.setObjectName("metricValue")
    if value_color:
        v.setStyleSheet(f"color: {value_color};")
    lay.addWidget(v)

    card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return card


def placeholder_panel(text: str, min_height: int = 200) -> QFrame:
    """Dashed-border panel used for not-yet-built regions (e.g. chart canvas)."""
    frame = QFrame()
    frame.setObjectName("placeholder")
    frame.setMinimumHeight(min_height)
    lay = QVBoxLayout(frame)
    lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

    lbl = QLabel(text)
    lbl.setObjectName("placeholderText")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setWordWrap(True)
    lay.addWidget(lbl)
    return frame


def form_row(label: str, widget: QWidget, hint: str = "") -> QWidget:
    """Label | widget | optional hint row used on Settings tabs."""
    row = QWidget()
    lay = QHBoxLayout(row)
    lay.setContentsMargins(0, 4, 0, 4)
    lay.setSpacing(12)

    lbl = QLabel(label)
    lbl.setMinimumWidth(210)
    lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    lay.addWidget(lbl)

    # Only clamp editable inputs; checkboxes/labels may use their natural width.
    from PySide6.QtWidgets import QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox, QTimeEdit

    if isinstance(widget, (QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTimeEdit)):
        widget.setMinimumWidth(180)
        widget.setMaximumWidth(320)
    lay.addWidget(widget)

    if hint:
        h = hint_label(hint)
        lay.addWidget(h, stretch=1)
    else:
        lay.addStretch(1)
    return row


def section_block(title: str, rows: list[QWidget], note: str = "") -> QWidget:
    """A titled vertical block of form rows with an optional footnote."""
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 10, 0, 10)
    lay.setSpacing(2)
    lay.addWidget(section_title(title))
    for r in rows:
        lay.addWidget(r)
    if note:
        lay.addWidget(hint_label(note))
    return w


def make_table(headers: list[str], stretch_cols: tuple[int, ...] = ()) -> QTableWidget:
    """Empty dark table with the given column headers."""
    cols = len(headers)
    table = QTableWidget(0, cols)
    table.setHorizontalHeaderLabels(headers)
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.verticalHeader().setVisible(False)
    header = table.horizontalHeader()
    header.setStretchLastSection(False)
    for i in range(cols):
        header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
    for i in stretch_cols:
        header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
    return table


def set_placeholder_rows(table: QTableWidget, rows: list[list[str]]) -> None:
    """Fill a table with clearly-static sample/placeholder rows."""
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            table.setItem(r, c, QTableWidgetItem(text))
