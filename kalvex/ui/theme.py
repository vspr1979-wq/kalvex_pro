"""Kalvex Pro — 'Ember Terminal' theme.

Design language (deliberately NOT a generic SaaS dashboard):
  * ink-black cockpit background, hairline-bordered panels
  * ember/amber instrument backlight accent; cyan = long/profit,
    coral = short/loss/kill, violet = system/analysis
  * ALL numerics in a monospace face (tabular by construction)
  * micro-labels: small, uppercase, muted — like cockpit legends
  * cards carry a coloured left edge bar instead of rounded blobs
  * squared corners (2-4px), 1px hairlines, no glossy gradients
"""

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

# palette
BG = "#0A0D12"
PANEL = "#10151C"
PANEL_2 = "#151B23"
HAIRLINE = "#222B36"
EMBERS = "#FFB020"
EMBER_DIM = "#B87A12"
CYAN = "#35D0C8"
CORAL = "#FF5D5D"
CORAL_DEEP = "#B32424"
VIOLET = "#8B7CFF"
TEXT = "#E8EEF6"
MUTED = "#7A8798"
FAINT = "#4A5665"

MONO_STACK = "Consolas, 'Cascadia Mono', 'DejaVu Sans Mono', monospace"


def mono_font(size: int = 12, bold: bool = False) -> QFont:
    fams = QFontDatabase.families()
    for name in ("Consolas", "Cascadia Mono", "DejaVu Sans Mono",
                 "Liberation Mono", "Menlo", "monospace"):
        if name in fams:
            f = QFont(name, size)
            break
    else:
        f = QFont("monospace", size)
    f.setBold(bold)
    f.setStyleHint(QFont.StyleHint.Monospace)
    return f


def label_font(size: int = 9, bold: bool = True) -> QFont:
    f = QFont("Segoe UI", size)
    f.setBold(bold)
    f.setCapitalization(QFont.Capitalization.AllUppercase)
    return f


EMBER_QSS = f"""
/* ---------- base ---------- */
QWidget {{
    background-color: {BG};
    color: {TEXT};
    font-size: 12px;
}}
QToolTip {{
    background-color: {PANEL_2};
    color: {TEXT};
    border: 1px solid {EMBERS};
    padding: 4px 8px;
    font-size: 11px;
}}
QLabel#legend {{          /* cockpit micro-label */
    color: {MUTED};
    font-size: 9px;
    font-weight: 700;
}}
QLabel#legendFaint {{ color: {FAINT}; font-size: 9px; font-weight: 700; }}
QLabel#num {{             /* monospace numerics */
    color: {TEXT};
    font-size: 15px;
}}
QLabel#numBig {{
    color: {TEXT};
    font-size: 26px;
}}
QLabel#numPos {{ color: {CYAN}; font-size: 15px; }}
QLabel#numNeg {{ color: {CORAL}; font-size: 15px; }}
QLabel#title {{
    font-size: 17px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#subtitle {{ color: {MUTED}; font-size: 11px; }}
QLabel#hint {{ color: {MUTED}; font-size: 10px; }}
QLabel#section {{
    color: {EMBERS};
    font-size: 10px;
    font-weight: 700;
}}
QLabel#empty {{ color: {FAINT}; font-size: 12px; padding: 18px; }}

/* ---------- command strip (top bar) ---------- */
QFrame#topBar {{
    background-color: {PANEL};
    border-bottom: 1px solid {HAIRLINE};
}}
QLabel#brand {{
    color: {EMBERS};
    font-size: 18px;
    font-weight: 800;
}}
QLabel#brandSub {{
    color: {FAINT};
    font-size: 8px;
    font-weight: 700;
}}
QFrame#chip {{
    background-color: {PANEL_2};
    border: 1px solid {HAIRLINE};
    border-left: 3px solid {EMBERS};
    border-radius: 2px;
}}
QFrame#chipGreen {{ border-left: 3px solid {CYAN}; }}
QFrame#chipRed {{ border-left: 3px solid {CORAL}; }}
QFrame#chipViolet {{ border-left: 3px solid {VIOLET}; }}

QPushButton#seg {{
    background-color: {PANEL_2};
    border: 1px solid {HAIRLINE};
    color: {MUTED};
    padding: 6px 13px;
    font-size: 11px;
}}
QPushButton#seg:checked {{
    background-color: #24190A;
    border: 1px solid {EMBERS};
    color: {EMBERS};
    font-weight: 700;
}}
QPushButton#seg:disabled {{ color: {FAINT}; background-color: {PANEL}; }}
QPushButton#segLeft  {{ border-top-left-radius: 3px; border-bottom-left-radius: 3px; }}
QPushButton#segRight {{ border-top-right-radius: 3px; border-bottom-right-radius: 3px; }}

QPushButton#kill {{
    background-color: {CORAL_DEEP};
    color: #FFFFFF;
    border: 1px solid {CORAL};
    border-radius: 3px;
    padding: 9px 18px;
    font-weight: 800;
    font-size: 12px;
}}
QPushButton#kill:hover {{ background-color: {CORAL}; color: #14060a; }}
QPushButton#kill:pressed {{ background-color: #7E1A1A; }}

QPushButton#ember {{
    background-color: {EMBERS};
    color: #14100A;
    border: none;
    border-radius: 3px;
    padding: 7px 15px;
    font-weight: 700;
    font-size: 11px;
}}
QPushButton#ember:hover {{ background-color: #FFC44D; }}
QPushButton#ember:disabled {{ background-color: {PANEL_2}; color: {FAINT}; }}

QPushButton#ghost {{
    background-color: transparent;
    border: 1px solid {HAIRLINE};
    border-radius: 3px;
    padding: 7px 15px;
    color: {TEXT};
    font-size: 11px;
}}
QPushButton#ghost:hover {{ border-color: {EMBERS}; color: {EMBERS}; }}
QPushButton#ghost:disabled {{ color: {FAINT}; border-color: {PANEL_2}; }}

/* ---------- left rail ---------- */
QFrame#navPanel {{
    background-color: {PANEL};
    border-right: 1px solid {HAIRLINE};
}}
QPushButton#nav {{
    background-color: transparent;
    border: none;
    border-left: 2px solid transparent;
    padding: 9px 12px;
    text-align: left;
    color: {MUTED};
    font-size: 12px;
}}
QPushButton#nav:hover {{ background-color: {PANEL_2}; color: {TEXT}; }}
QPushButton#nav:checked {{
    background-color: #1A1408;
    border-left: 2px solid {EMBERS};
    color: {EMBERS};
    font-weight: 700;
}}
QLabel#navLegend {{
    color: {FAINT};
    font-size: 8px;
    font-weight: 700;
    padding: 10px 12px 2px 12px;
}}

/* ---------- panels / cards ---------- */
QFrame#card {{
    background-color: {PANEL};
    border: 1px solid {HAIRLINE};
    border-left: 3px solid {EMBERS};
    border-radius: 2px;
}}
QFrame#cardCyan {{ border-left: 3px solid {CYAN}; }}
QFrame#cardCoral {{ border-left: 3px solid {CORAL}; }}
QFrame#cardViolet {{ border-left: 3px solid {VIOLET}; }}
QFrame#well {{
    background-color: {PANEL};
    border: 1px solid {HAIRLINE};
    border-radius: 2px;
}}
QFrame#dashed {{
    background-color: {PANEL};
    border: 1px dashed {HAIRLINE};
    border-radius: 2px;
}}

/* ---------- tables ---------- */
QTableWidget, QTableView {{
    background-color: {PANEL};
    alternate-background-color: {PANEL_2};
    border: 1px solid {HAIRLINE};
    gridline-color: {HAIRLINE};
    selection-background-color: #24190A;
    selection-color: {EMBERS};
}}
QHeaderView::section {{
    background-color: {PANEL_2};
    color: {MUTED};
    border: none;
    border-bottom: 1px solid {HAIRLINE};
    padding: 6px 8px;
    font-size: 9px;
    font-weight: 700;
}}
QTableWidget::item {{ padding: 3px 6px; }}

/* ---------- tabs ---------- */
QTabWidget::pane {{
    border: 1px solid {HAIRLINE};
    background-color: {BG};
}}
QTabBar::tab {{
    background-color: {PANEL};
    color: {MUTED};
    border: 1px solid {HAIRLINE};
    border-bottom: none;
    padding: 7px 16px;
    margin-right: 1px;
    font-size: 11px;
}}
QTabBar::tab:selected {{
    background-color: #1A1408;
    color: {EMBERS};
    border-color: {EMBER_DIM};
    font-weight: 700;
}}

/* ---------- inputs ---------- */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTimeEdit, QDateEdit, QTextEdit, QPlainTextEdit {{
    background-color: {PANEL_2};
    border: 1px solid {HAIRLINE};
    border-radius: 2px;
    padding: 5px 7px;
    selection-background-color: #24190A;
    selection-color: {EMBERS};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {EMBERS};
}}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
    color: {FAINT};
}}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background-color: {PANEL_2};
    border: 1px solid {HAIRLINE};
    selection-background-color: #24190A;
    selection-color: {EMBERS};
}}
QCheckBox {{ spacing: 7px; }}
QCheckBox::indicator {{
    width: 14px; height: 14px;
    border: 1px solid {HAIRLINE};
    border-radius: 2px;
    background-color: {PANEL_2};
}}
QCheckBox::indicator:checked {{ background-color: {EMBERS}; border-color: {EMBERS}; }}
QCheckBox:disabled {{ color: {FAINT}; }}

/* ---------- scroll / status ---------- */
QScrollArea {{ border: none; }}
QStatusBar {{
    background-color: {PANEL};
    border-top: 1px solid {HAIRLINE};
    color: {MUTED};
    font-size: 10px;
}}
QScrollBar:vertical {{ background: {BG}; width: 9px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {HAIRLINE}; border-radius: 3px; min-height: 28px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: {BG}; height: 9px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {HAIRLINE}; border-radius: 3px; min-width: 28px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QSplitter::handle {{ background: {HAIRLINE}; }}
QProgressBar {{
    background-color: {PANEL_2};
    border: 1px solid {HAIRLINE};
    border-radius: 2px;
    text-align: center;
    color: {TEXT};
    font-size: 10px;
}}
QProgressBar::chunk {{ background-color: {EMBERS}; }}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    base = QFont("Segoe UI", 10)
    app.setFont(base)
    app.setStyleSheet(EMBER_QSS)
