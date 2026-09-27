"""Charts page — timeframe controls, chart canvas placeholder, overlays panel."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from kalvex.ui.widgets import hint_label, page_header, placeholder_panel, section_title


class ChartsPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(12)

        root.addWidget(
            page_header(
                "Charts",
                "Candles, timeframe switching, indicator overlays and buy/sell markers. "
                "Chart canvas embeds lightweight-charts-python in a later phase (fallback: pyqtgraph).",
            )
        )

        # --- toolbar ---
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        toolbar.addWidget(QLabel("Symbol:"))
        symbol = QComboBox()
        symbol.setPlaceholderText("Search symbol…")
        symbol.addItems(["NIFTY 50", "BANK NIFTY", "FIN NIFTY", "NIFTY (F&O) placeholder…"])
        symbol.setCurrentIndex(-1)
        symbol.setMinimumWidth(200)
        toolbar.addWidget(symbol)

        toolbar.addSpacing(10)
        toolbar.addWidget(QLabel("Timeframe:"))
        self.tf_group = QButtonGroup(self)
        self.tf_group.setExclusive(True)
        for i, tf in enumerate(("1m", "5m", "15m")):
            btn = QPushButton(tf)
            btn.setObjectName("segButton segButtonLeft" if i == 0 else "segButton")
            btn.setCheckable(True)
            self.tf_group.addButton(btn)
            toolbar.addWidget(btn)
        self.tf_group.buttons()[1].setChecked(True)  # default 5m

        toolbar.addStretch(1)

        live_btn = QPushButton("Connect feed (placeholder)")
        live_btn.setObjectName("secondary")
        live_btn.setEnabled(False)
        live_btn.setToolTip("No market-data connection in this layout build.")
        toolbar.addWidget(live_btn)
        root.addLayout(toolbar)

        # --- chart + side panel ---
        body = QHBoxLayout()
        body.setSpacing(12)

        chart_col = QVBoxLayout()
        chart_col.setSpacing(8)

        self.chart_placeholder = QFrame()
        self.chart_placeholder.setObjectName("placeholder")
        chart_lay = QVBoxLayout(self.chart_placeholder)
        chart_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chart_msg = QLabel(
            "Chart canvas — empty\n\n"
            "Target: lightweight-charts-python (fallback: pyqtgraph)\n"
            "Candles • 1m / 5m / 15m • overlays • buy/sell markers"
        )
        chart_msg.setObjectName("placeholderText")
        chart_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chart_lay.addWidget(chart_msg)
        chart_col.addWidget(self.chart_placeholder, stretch=1)

        # marker legend
        legend = QHBoxLayout()
        buy_lbl = QLabel("▲ Buy marker")
        buy_lbl.setObjectName("pnlPositive")
        sell_lbl = QLabel("▼ Sell marker")
        sell_lbl.setObjectName("pnlNegative")
        legend.addWidget(buy_lbl)
        legend.addWidget(sell_lbl)
        legend.addStretch(1)
        legend.addWidget(hint_label("Markers rendered from logged signals/orders (IST)."))
        chart_col.addLayout(legend)

        body.addLayout(chart_col, stretch=4)

        # --- right: overlays + watchlist ---
        side = QVBoxLayout()
        side.setSpacing(10)
        side.addWidget(section_title("OVERLAYS / INDICATORS"))

        self.overlays: list[QCheckBox] = []
        for name, checked in (
            ("EMA (fast/slow)", True),
            ("VWAP", True),
            ("Supertrend", False),
            ("RSI (sub-chart)", False),
            ("Bollinger Bands (squeeze — nice-to-have)", False),
            ("MACD (nice-to-have)", False),
            ("SMC FVG/OB/BOS/CHoCH (research only)", False),
        ):
            cb = QCheckBox(name)
            cb.setChecked(checked)
            if "SMC" in name:
                cb.setToolTip("Overlay/research only — never the sole live strategy in v1.")
            self.overlays.append(cb)
            side.addWidget(cb)

        side.addSpacing(8)
        side.addWidget(section_title("WATCHLIST"))
        watch = placeholder_panel("Watchlist (empty)", min_height=180)
        side.addWidget(watch)
        side.addWidget(
            hint_label(
                "Options (v1, opt-in): index options buying only, ATM / defined OTM width, "
                "current expiry first. IV & Greeks only if the feed provides them."
            )
        )
        side.addStretch(1)

        side_w = QWidget()
        side_w.setLayout(side)
        side_w.setFixedWidth(320)
        body.addWidget(side_w)

        root.addLayout(body, stretch=1)
