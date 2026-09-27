"""Left navigation sidebar."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from kalvex.core.constants import NAV_WIDTH, PAGE_TITLES, PageId


class NavSidebar(QFrame):
    """Vertical nav: Dashboard, Charts, Strategies, Positions/Orders, Logs, Settings."""

    page_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("navPanel")
        self.setFixedWidth(NAV_WIDTH)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 14, 10, 14)
        lay.setSpacing(4)

        section = QLabel("TRADING")
        section.setObjectName("navSectionLabel")
        lay.addWidget(section)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        self._buttons: dict[str, QPushButton] = {}
        for page in (
            PageId.DASHBOARD,
            PageId.CHARTS,
            PageId.STRATEGIES,
            PageId.ACTIVITY,
            PageId.LOGS,
        ):
            self._add_nav_button(page.value, PAGE_TITLES[page])

        section2 = QLabel("SYSTEM")
        section2.setObjectName("navSectionLabel")
        lay.addWidget(section2)
        lay.addSpacing(2)
        self._add_nav_button(PageId.SETTINGS.value, PAGE_TITLES[PageId.SETTINGS])

        lay.addStretch(1)

        # Footer: current mode reminder (always visible in the skeleton).
        self.mode_note = QLabel("Mode: Paper")
        self.mode_note.setObjectName("navSectionLabel")
        lay.addWidget(self.mode_note)

        self._group.buttonClicked.connect(self._on_clicked)

        # Select Dashboard by default.
        self._buttons[PageId.DASHBOARD.value].setChecked(True)

    def _add_nav_button(self, page_id: str, text: str) -> None:
        btn = QPushButton(text)
        btn.setObjectName("navButton")
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setMinimumHeight(40)
        self._group.addButton(btn)
        self._buttons[page_id] = btn
        self.layout().addWidget(btn)

    def _on_clicked(self, btn: QPushButton) -> None:
        for page_id, b in self._buttons.items():
            if b is btn:
                self.page_selected.emit(page_id)
                return

    def select_page(self, page_id: str) -> None:
        """Programmatic selection (used by tray menu / keyboard later)."""
        btn = self._buttons.get(page_id)
        if btn:
            btn.setChecked(True)
            self.page_selected.emit(page_id)

    def set_mode_note(self, mode: str) -> None:
        self.mode_note.setText(f"Mode: {mode}")
