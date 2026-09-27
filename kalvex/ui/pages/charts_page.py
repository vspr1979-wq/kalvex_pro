"""Charts page — custom candle canvas, timeframe + overlay toggles, markers."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from kalvex.ui.chart import CandleChart
from kalvex.ui.widgets import hint_label, legend, page_header, section_title


class ChartsPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 12)
        root.setSpacing(8)

        root.addWidget(page_header(
            "Charts",
            "Candles rendered live from the feed with the bot's overlays and "
            "entry/exit markers."))

        # toolbar
        bar = QHBoxLayout()
        bar.setSpacing(8)
        bar.addWidget(legend("instrument"))
        self.symbol = QComboBox()
        self.symbol.setMinimumWidth(180)
        bar.addWidget(self.symbol)

        bar.addSpacing(8)
        bar.addWidget(legend("timeframe"))
        self.tf_group = QButtonGroup(self)
        self.tf_group.setExclusive(True)
        for i, tf in enumerate(("1m", "5m", "15m")):
            b = QPushButton(tf)
            b.setObjectName("seg segButtonLeft" if i == 0 else "seg")
            b.setCheckable(True)
            self.tf_group.addButton(b)
            bar.addWidget(b)
        self.tf_group.buttons()[1].setChecked(True)

        bar.addStretch(1)
        self.feed_chip = legend("feed: NO DATA", faint=True)
        bar.addWidget(self.feed_chip)
        root.addLayout(bar)

        body = QHBoxLayout()
        body.setSpacing(10)

        self.chart = CandleChart()
        body.addWidget(self.chart, stretch=1)

        # overlays panel
        side = QVBoxLayout()
        side.setSpacing(6)
        side.addWidget(section_title("OVERLAYS"))
        self.cb_ema = QCheckBox("EMA (fast/slow)")
        self.cb_ema.setChecked(True)
        self.cb_vwap = QCheckBox("VWAP (session)")
        self.cb_vwap.setChecked(True)
        self.cb_ema.toggled.connect(lambda on: setattr(self.chart, "show_ema", on))
        self.cb_vwap.toggled.connect(lambda on: setattr(self.chart, "show_vwap", on))
        side.addWidget(self.cb_ema)
        side.addWidget(self.cb_vwap)
        side.addWidget(hint_label(
            "Later: Bollinger squeeze, MACD, SMC FVG/OB/BOS/CHoCH as "
            "research overlays + optional alert only — never sole live entry."))
        side.addStretch(1)
        right = QWidget()
        right.setLayout(side)
        right.setFixedWidth(280)
        body.addWidget(right)
        root.addLayout(body, stretch=1)

        root.addWidget(hint_label(
            "▲▼ markers show the bot's executed entries/exits (IST journal). "
            "Production embed target: lightweight-charts-python (fallback pyqtgraph)."))

    def set_symbols(self, names: list[str]) -> None:
        self.symbol.clear()
        self.symbol.addItems(names)
