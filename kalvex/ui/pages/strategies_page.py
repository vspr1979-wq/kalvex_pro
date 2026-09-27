"""Strategy Manager — enable/edit the SMALL v1 set with live stats."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from kalvex.core.strategies import TUNE_BANDS
from kalvex.ui.widgets import (
    hint_label,
    legend,
    make_table,
    page_header,
    section_title,
)


class StrategiesPage(QWidget):
    strategy_toggled = Signal(str, bool)
    param_changed = Signal(str, str, object)   # key, param, value

    HEADERS = ["Strategy", "On/Off", "Mode", "Parameters (within hard bands)",
               "Trades", "Win %", "Today P&L", "Status"]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 12)
        root.setSpacing(10)

        root.addWidget(page_header(
            "Strategy Manager",
            "Four v1 strategies only. Parameters are editable within hard "
            "tune bands; the self-improvement loop can only move them inside "
            "those same bands."))

        self.table = make_table(list(self.HEADERS), stretch_cols=(0, 3))
        root.addWidget(self.table, stretch=1)

        root.addWidget(section_title("LATER / OVERLAY-ONLY — NOT LIVE AUTO-ENTRY"))
        root.addWidget(hint_label(
            "Nice-to-have: Bollinger squeeze, MACD momentum. SMC "
            "(FVG/OB/BOS/CHoCH via smartmoneyconcepts) = chart overlay + "
            "optional alert only — never the sole live strategy."))

    # ------------------------------------------------------------------ #
    def set_strategies(self, rows: list[dict]) -> None:
        """rows: key, name, enabled, mode, params(dict), trades, win, pnl, status"""
        from PySide6.QtWidgets import QTableWidgetItem
        self.table.setRowCount(len(rows))
        self._keys = [r["key"] for r in rows]
        for r, row in enumerate(rows):
            self.table.setItem(r, 0, QTableWidgetItem(row["name"]))

            cb = QCheckBox()
            cb.setChecked(bool(row["enabled"]))
            cb.setStyleSheet("margin-left: 10px;")
            cb.toggled.connect(
                lambda on, k=row["key"]: self.strategy_toggled.emit(k, on))
            self.table.setCellWidget(r, 1, cb)

            mode = QComboBox()
            mode.addItems(["Paper", "Semi-auto", "Auto (locked)"])
            mode.setCurrentIndex({"Paper": 0, "Semi-auto": 1}.get(row.get("mode", "Paper"), 0))
            mode.setMaximumWidth(130)
            self.table.setCellWidget(r, 2, mode)

            self.table.setCellWidget(r, 3, self._param_editor(row["key"], row["params"]))
            self.table.setItem(r, 4, QTableWidgetItem(str(row.get("trades", 0))))
            wr = row.get("win")
            self.table.setItem(r, 5, QTableWidgetItem(
                "—" if wr is None else f"{wr:.0%}"))
            pnl = row.get("pnl", 0.0)
            item = QTableWidgetItem(f"₹ {pnl:,.0f}")
            item.setForeground(
                __import__("PySide6.QtGui", fromlist=["QColor"]).QColor(
                    "#35D0C8" if pnl >= 0 else "#FF5D5D"))
            self.table.setItem(r, 6, item)
            self.table.setItem(r, 7, QTableWidgetItem(row.get("status", "idle")))

    def _param_editor(self, key: str, params: dict) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(6)
        bands = TUNE_BANDS.get(key, {})
        for name, value in list(params.items())[:3]:
            edit = QLineEdit(str(value))
            edit.setMaximumWidth(72)
            if name in bands:
                lo, hi = bands[name]
                edit.setToolTip(f"hard band: {lo} … {hi}")
            else:
                edit.setToolTip("fixed parameter")
            edit.editingFinished.connect(
                lambda e=edit, k=key, n=name: self._emit_param(k, n, e.text()))
            lay.addWidget(legend(name))
            lay.addWidget(edit)
        lay.addStretch(1)
        return w

    def _emit_param(self, key: str, name: str, text: str) -> None:
        bands = TUNE_BANDS.get(key, {})
        try:
            val: float | int = float(text)
            if name in bands:
                lo, hi = bands[name]
                val = max(lo, min(hi, val))
            if float(val).is_integer():
                val = int(val)
        except ValueError:
            return
        self.param_changed.emit(key, name, val)
