"""Custom candlestick chart widget (QPainter) — zero external chart deps.

Production note: lightweight-charts-python remains the intended embed for
richer charting (fallback pyqtgraph); this widget keeps the v1 build
self-contained and gives the bot's overlays/markers a home.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from kalvex.core.models import Bar
from kalvex.ui.theme import mono_font

UP = QColor("#35D0C8")
DOWN = QColor("#FF5D5D")
GRID = QColor("#1B222C")
AXIS = QColor("#7A8798")
EMBER = QColor("#FFB020")
VIOLET = QColor("#8B7CFF")


class CandleChart(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(320)
        self._bars: list[Bar] = []
        self._ema: list[float] = []
        self._vwap: list[float] = []
        self._markers: list[tuple[int, float, str]] = []   # (bar_idx, price, side)
        self.show_ema = True
        self.show_vwap = True
        self.setBackgroundRole(self.backgroundRole())
        self.setAutoFillBackground(False)

    def set_data(self, bars: list[Bar], ema: list[float] | None = None,
                 vwap: list[float] | None = None) -> None:
        self._bars = bars[-220:]
        off = len(bars) - len(self._bars)
        self._ema = (ema or [])[off:]
        self._vwap = (vwap or [])[off:]
        self._markers = [(i - off, p, s) for i, p, s in self._markers if i - off >= 0]
        self.update()

    def add_marker(self, bar_idx: int, price: float, side: str) -> None:
        self._markers.append((bar_idx, price, side))
        self.update()

    def clear_markers(self) -> None:
        self._markers = []
        self.update()

    # ------------------------------------------------------------------ #
    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor("#0C1016"))

        pad_r, pad_b, pad_t = 64, 22, 12
        plot_w, plot_h = w - pad_r, h - pad_b - pad_t

        if len(self._bars) < 2:
            p.setPen(QColor("#4A5665"))
            p.setFont(mono_font(11))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter,
                       "waiting for bars…")
            p.end()
            return

        lows = [b.low for b in self._bars] + ([min(self._ema)] if self._ema else [])
        highs = [b.high for b in self._bars] + ([max(self._ema)] if self._ema else [])
        lo, hi = min(lows), max(highs)
        span = max(hi - lo, 1e-9)
        lo -= span * 0.06
        hi += span * 0.06
        span = hi - lo

        def y_of(price: float) -> float:
            return pad_t + (hi - price) / span * plot_h

        n = len(self._bars)
        step = plot_w / n
        body_w = max(2.0, step * 0.62)

        # grid + right axis
        p.setFont(mono_font(9))
        for i in range(6):
            price = lo + span * i / 5
            y = y_of(price)
            p.setPen(QPen(GRID, 1))
            p.drawLine(0, int(y), plot_w, int(y))
            p.setPen(AXIS)
            p.drawText(QRectF(plot_w + 4, y - 8, pad_r - 8, 16),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       f"{price:,.0f}")

        # candles
        for i, b in enumerate(self._bars):
            x = i * step + step / 2
            up = b.close >= b.open
            col = UP if up else DOWN
            p.setPen(QPen(col, 1))
            p.drawLine(QPointF(x, y_of(b.high)), QPointF(x, y_of(b.low)))
            top = y_of(max(b.open, b.close))
            bot = y_of(min(b.open, b.close))
            rect = QRectF(x - body_w / 2, top, body_w, max(1.0, bot - top))
            if up:
                p.fillRect(rect, QColor(53, 208, 200, 70))
                p.drawRect(rect)
            else:
                p.fillRect(rect, QColor(255, 93, 93, 70))
                p.drawRect(rect)

        # overlays
        if self.show_ema and self._ema:
            p.setPen(QPen(EMBER, 1.4))
            prev = None
            for i, val in enumerate(self._ema):
                pt = QPointF(i * step + step / 2, y_of(val))
                if prev:
                    p.drawLine(prev, pt)
                prev = pt
        if self.show_vwap and self._vwap:
            p.setPen(QPen(VIOLET, 1.2))
            prev = None
            for i, val in enumerate(self._vwap):
                pt = QPointF(i * step + step / 2, y_of(val))
                if prev:
                    p.drawLine(prev, pt)
                prev = pt

        # buy/sell markers
        p.setFont(mono_font(9, bold=True))
        for idx, price, side in self._markers:
            if 0 <= idx < n:
                x = idx * step + step / 2
                y = y_of(price)
                if side == "BUY":
                    p.setPen(QPen(UP, 2))
                    p.setBrush(UP)
                    pts = [QPointF(x, y - 4), QPointF(x - 5, y + 5), QPointF(x + 5, y + 5)]
                else:
                    p.setPen(QPen(DOWN, 2))
                    p.setBrush(DOWN)
                    pts = [QPointF(x, y + 4), QPointF(x - 5, y - 5), QPointF(x + 5, y - 5)]
                p.drawPolygon(pts)

        # bottom time axis (every ~40 bars)
        p.setPen(AXIS)
        p.setFont(mono_font(8))
        for i in range(0, n, max(1, n // 6)):
            ts = self._bars[i].ts.strftime("%H:%M")
            p.drawText(QRectF(i * step, h - pad_b + 2, 70, pad_b),
                       Qt.AlignmentFlag.AlignLeft, ts)

        # legend
        p.setFont(mono_font(9))
        p.setPen(EMBER)
        p.drawText(10, 18, "EMA")
        p.setPen(VIOLET)
        p.drawText(44, 18, "VWAP")
        p.setPen(AXIS)
        p.drawText(86, 18, f"{n} bars")
        p.end()
