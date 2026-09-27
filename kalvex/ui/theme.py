"""Dark theme stylesheet for Kalvex Pro.

Practical dark theme (not a full Fluent clone). Colors are kept in one
place so a later theme pass only touches this file.
"""

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

# Palette
BG = "#0e1116"
SURFACE = "#161b22"
SURFACE_2 = "#1c232d"
BORDER = "#2a323d"
TEXT = "#e6edf3"
TEXT_MUTED = "#8b98a9"
ACCENT = "#3d8bfd"
ACCENT_SOFT = "#1d2f4a"
GREEN = "#2ea36e"
RED = "#e5534b"
RED_DEEP = "#b4232a"
AMBER = "#d29922"

DARK_QSS = f"""
/* ---------- base ---------- */
QWidget {{
    background-color: {BG};
    color: {TEXT};
    font-size: 13px;
}}
QToolTip {{
    background-color: {SURFACE_2};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 4px 8px;
}}

/* ---------- top bar ---------- */
QFrame#topBar {{
    background-color: {SURFACE};
    border-bottom: 1px solid {BORDER};
}}
QLabel#appTitle {{
    font-size: 16px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#pill {{
    background-color: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 4px 12px;
    color: {TEXT_MUTED};
    font-size: 12px;
}}
QLabel#pillGreen {{ color: {GREEN}; border-color: {GREEN}; }}
QLabel#pillRed   {{ color: {RED};  border-color: {RED}; }}
QLabel#pillAmber {{ color: {AMBER}; border-color: {AMBER}; }}

QLabel#metricTitle {{
    color: {TEXT_MUTED};
    font-size: 11px;
}}
QLabel#metricValue {{
    font-size: 15px;
    font-weight: 700;
}}

QPushButton#segButton {{
    background-color: {SURFACE_2};
    border: 1px solid {BORDER};
    padding: 6px 14px;
    color: {TEXT_MUTED};
}}
QPushButton#segButton:checked {{
    background-color: {ACCENT_SOFT};
    border: 1px solid {ACCENT};
    color: {TEXT};
}}
QPushButton#segButton:disabled {{
    color: #55606e;
    background-color: {SURFACE};
}}
QPushButton#segButtonLeft  {{ border-top-left-radius: 6px; border-bottom-left-radius: 6px; }}
QPushButton#segButtonRight {{ border-top-right-radius: 6px; border-bottom-right-radius: 6px; }}

QPushButton#killSwitch {{
    background-color: {RED_DEEP};
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 10px 18px;
    font-weight: 700;
    font-size: 13px;
}}
QPushButton#killSwitch:hover   {{ background-color: {RED}; }}
QPushButton#killSwitch:pressed {{ background-color: #8f1c22; }}

/* ---------- left nav ---------- */
QFrame#navPanel {{
    background-color: {SURFACE};
    border-right: 1px solid {BORDER};
}}
QPushButton#navButton {{
    background-color: transparent;
    border: none;
    border-radius: 6px;
    padding: 10px 14px;
    text-align: left;
    color: {TEXT_MUTED};
    font-size: 13px;
}}
QPushButton#navButton:hover    {{ background-color: {SURFACE_2}; color: {TEXT}; }}
QPushButton#navButton:checked  {{
    background-color: {ACCENT_SOFT};
    color: {TEXT};
    border-left: 3px solid {ACCENT};
    font-weight: 600;
}}
QLabel#navSectionLabel {{
    color: #5c6875;
    font-size: 10px;
    letter-spacing: 1px;
    padding: 6px 14px;
}}

/* ---------- pages ---------- */
QLabel#pageTitle    {{ font-size: 18px; font-weight: 700; }}
QLabel#pageSubtitle {{ color: {TEXT_MUTED}; font-size: 12px; }}
QLabel#sectionTitle {{ font-size: 13px; font-weight: 700; color: {ACCENT}; }}
QLabel#emptyState {{
    color: #5c6875;
    font-size: 13px;
    padding: 24px;
}}
QLabel#hint {{ color: {TEXT_MUTED}; font-size: 11px; }}
QLabel#pnlPositive {{ color: {GREEN}; font-weight: 700; }}
QLabel#pnlNegative {{ color: {RED}; font-weight: 700; }}

QFrame#card {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
QFrame#placeholder {{
    background-color: {SURFACE};
    border: 1px dashed {BORDER};
    border-radius: 8px;
}}
QLabel#placeholderText {{ color: #5c6875; font-size: 13px; }}

/* ---------- tables ---------- */
QTableWidget, QTableView {{
    background-color: {SURFACE};
    alternate-background-color: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 6px;
    gridline-color: {BORDER};
    selection-background-color: {ACCENT_SOFT};
    selection-color: {TEXT};
}}
QHeaderView::section {{
    background-color: {SURFACE_2};
    color: {TEXT_MUTED};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 7px 10px;
    font-size: 11px;
    font-weight: 600;
}}
QTableWidget::item {{ padding: 4px 8px; }}

/* ---------- tabs ---------- */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 6px;
    top: -1px;
    background-color: {BG};
}}
QTabBar::tab {{
    background-color: {SURFACE};
    color: {TEXT_MUTED};
    border: 1px solid {BORDER};
    border-bottom: none;
    padding: 8px 18px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}}
QTabBar::tab:selected {{
    background-color: {ACCENT_SOFT};
    color: {TEXT};
    border-color: {ACCENT};
}}

/* ---------- inputs ---------- */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTimeEdit, QDateEdit, QTextEdit {{
    background-color: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 6px 8px;
    selection-background-color: {ACCENT_SOFT};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {ACCENT};
}}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
    color: #55606e;
}}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background-color: {SURFACE_2};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT_SOFT};
}}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {BORDER};
    border-radius: 4px;
    background-color: {SURFACE_2};
}}
QCheckBox::indicator:checked {{ background-color: {ACCENT}; border-color: {ACCENT}; }}
QCheckBox:disabled {{ color: #55606e; }}

QPushButton#secondary {{
    background-color: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 7px 14px;
    color: {TEXT};
}}
QPushButton#secondary:hover   {{ border-color: {ACCENT}; }}
QPushButton#secondary:disabled {{ color: #55606e; }}
QPushButton#primary {{
    background-color: {ACCENT};
    border: none;
    border-radius: 5px;
    padding: 7px 14px;
    color: #ffffff;
    font-weight: 600;
}}
QPushButton#primary:hover {{ background-color: #5a9bff; }}
QPushButton#primary:disabled {{ background-color: {SURFACE_2}; color: #55606e; }}

/* ---------- misc ---------- */
QScrollArea {{ border: none; }}
QStatusBar {{
    background-color: {SURFACE};
    border-top: 1px solid {BORDER};
    color: {TEXT_MUTED};
    font-size: 11px;
}}
QScrollBar:vertical {{
    background: {BG};
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {BG};
    height: 10px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QSplitter::handle {{ background: {BORDER}; }}
"""


def apply_theme(app: QApplication) -> None:
    """Apply the dark theme and base font to the application."""
    app.setStyle("Fusion")
    font = QFont("Segoe UI", 10)  # Segoe UI on Windows 11; falls back elsewhere
    app.setFont(font)
    app.setStyleSheet(DARK_QSS)
