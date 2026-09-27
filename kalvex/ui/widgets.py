"""Shared widgets for the Ember Terminal UI."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from kalvex.ui.theme import mono_font, label_font


def legend(text: str, faint: bool = False) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setObjectName("legendFaint" if faint else "legend")
    lbl.setFont(label_font(9))
    return lbl


def num_label(text: str = "—", size: int = 15, bold: bool = True,
              color: str | None = None) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("num")
    lbl.setFont(mono_font(size, bold))
    if color:
        lbl.setStyleSheet(f"color: {color};")
    return lbl


def page_header(title: str, subtitle: str = "") -> QWidget:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 6)
    lay.setSpacing(2)
    t = QLabel(title)
    t.setObjectName("title")
    lay.addWidget(t)
    if subtitle:
        s = QLabel(subtitle)
        s.setObjectName("subtitle")
        s.setWordWrap(True)
        lay.addWidget(s)
    return w


def empty_state(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("empty")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setWordWrap(True)
    return lbl


def hint_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("hint")
    lbl.setWordWrap(True)
    return lbl


def section_title(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setObjectName("section")
    lbl.setFont(label_font(10))
    return lbl


def stat_card(leg: str, value: str = "—", accent: str = "",
              value_size: int = 17) -> QFrame:
    """Cockpit instrument: micro-legend on top, big mono value below."""
    card = QFrame()
    card.setObjectName("card" + accent)
    lay = QVBoxLayout(card)
    lay.setContentsMargins(12, 8, 12, 10)
    lay.setSpacing(2)
    lay.addWidget(legend(leg))
    v = num_label(value, size=value_size)
    lay.addWidget(v)
    card.value_label = v  # type: ignore[attr-defined]
    card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return card


def chip(text: str, accent: str = "") -> QFrame:
    """Small status chip with a coloured left edge."""
    f = QFrame()
    f.setObjectName("chip" + accent)
    lay = QHBoxLayout(f)
    lay.setContentsMargins(8, 4, 8, 4)
    lay.setSpacing(6)
    lbl = QLabel(text)
    lbl.setObjectName("legend")
    lbl.setFont(label_font(9))
    lay.addWidget(lbl)
    return f


def panel_card(title: str, accent: str = "", body: QWidget | None = None) -> QFrame:
    card = QFrame()
    card.setObjectName("card" + accent)
    lay = QVBoxLayout(card)
    lay.setContentsMargins(12, 10, 12, 12)
    lay.setSpacing(6)
    if title:
        lay.addWidget(section_title(title))
    if body is not None:
        lay.addWidget(body)
    return card


def form_row(label: str, widget: QWidget, hint: str = "") -> QWidget:
    row = QWidget()
    lay = QHBoxLayout(row)
    lay.setContentsMargins(0, 3, 0, 3)
    lay.setSpacing(12)
    lbl = QLabel(label)
    lbl.setMinimumWidth(210)
    lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    lay.addWidget(lbl)

    from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QLineEdit,
                                   QSpinBox, QTimeEdit)
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
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 8, 0, 8)
    lay.setSpacing(2)
    lay.addWidget(section_title(title))
    for r in rows:
        lay.addWidget(r)
    if note:
        lay.addWidget(hint_label(note))
    return w


def make_table(headers: list[str], stretch_cols: tuple[int, ...] = ()):
    from PySide6.QtWidgets import (QAbstractItemView, QHeaderView,
                                   QTableWidget, QTableWidgetItem)
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
    _ = QTableWidgetItem
    return table


def set_placeholder_rows(table, rows: list[list[str]]) -> None:
    from PySide6.QtWidgets import QTableWidgetItem
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            table.setItem(r, c, QTableWidgetItem(text))
