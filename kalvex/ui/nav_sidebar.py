"""Left navigation rail with cockpit glyphs."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from kalvex.core.constants import NAV_WIDTH, PageId
from kalvex.ui.theme import label_font

GLYPHS = {
    PageId.DASHBOARD: "◈",
    PageId.CHARTS: "▦",
    PageId.BRAIN: "◎",
    PageId.STRATEGIES: "⬡",
    PageId.ACTIVITY: "≡",
    PageId.LOGS: "▤",
    PageId.SETTINGS: "⚙",
}

LABELS = {
    PageId.DASHBOARD: "Dashboard",
    PageId.CHARTS: "Charts",
    PageId.BRAIN: "Bot Brain",
    PageId.STRATEGIES: "Strategies",
    PageId.ACTIVITY: "Positions / Orders",
    PageId.LOGS: "Logs",
    PageId.SETTINGS: "Settings",
}


class NavSidebar(QFrame):
    page_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("navPanel")
        self.setFixedWidth(NAV_WIDTH)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 12, 8, 12)
        lay.setSpacing(2)

        lay.addWidget(self._legend("TRADE"))
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}
        for page in (PageId.DASHBOARD, PageId.CHARTS, PageId.BRAIN,
                     PageId.STRATEGIES, PageId.ACTIVITY, PageId.LOGS):
            self._add(page)
        lay.addWidget(self._legend("SYSTEM"))
        self._add(PageId.SETTINGS)
        lay.addStretch(1)

        self.mode_note = QLabel("MODE: PAPER")
        self.mode_note.setObjectName("navLegend")
        self.mode_note.setFont(label_font(8))
        lay.addWidget(self.mode_note)

        self._group.buttonClicked.connect(self._on_clicked)
        self._buttons[PageId.DASHBOARD.value].setChecked(True)

    def set_mode_note(self, mode: str) -> None:
        self.mode_note.setText(f"MODE: {mode.upper()}")

    def _legend(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("navLegend")
        lbl.setFont(label_font(8))
        return lbl

    def _add(self, page: PageId) -> None:
        btn = QPushButton(f"  {GLYPHS[page]}   {LABELS[page]}")
        btn.setObjectName("nav")
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setMinimumHeight(38)
        self._group.addButton(btn)
        self._buttons[page.value] = btn
        self.layout().addWidget(btn)

    def _on_clicked(self, btn: QPushButton) -> None:
        for page_id, b in self._buttons.items():
            if b is btn:
                self.page_selected.emit(page_id)
                return

    def select_page(self, page_id: str) -> None:
        btn = self._buttons.get(page_id)
        if btn:
            btn.setChecked(True)
            self.page_selected.emit(page_id)

