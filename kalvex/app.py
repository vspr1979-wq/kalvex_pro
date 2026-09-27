"""Application bootstrap: theme, main window, event loop."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from kalvex.core.constants import APP_NAME
from kalvex.ui.main_window import MainWindow
from kalvex.ui.theme import apply_theme


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)

    apply_theme(app)

    window = MainWindow()
    window.show()
    return app.exec()
