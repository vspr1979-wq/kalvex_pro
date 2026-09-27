"""Connect dialog — Upstox OAuth login flow (verified endpoints).

Flow shown to the user:
  1. Fill API key / secret / redirect URI (must match the Upstox app).
  2. 'Open Upstox login' launches the browser at the verified dialog URL.
  3. After login, the browser redirects to your redirect URI with ?code=… —
     paste the full URL (or just the code) below.
  4. Connect exchanges the code at POST /v2/login/authorization/token and
     stores the token with Windows DPAPI.

Token state text always reflects the verified 03:30 IST expiry rule.
"""

from __future__ import annotations

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from kalvex.core.session import BrokerSession, ConnectionState
from kalvex.ui.theme import mono_font
from kalvex.ui.widgets import hint_label, legend, section_title


class ConnectDialog(QDialog):
    connected = Signal(dict)   # emits session config on success

    def __init__(self, session: BrokerSession, parent=None) -> None:
        super().__init__(parent)
        self.session = session
        self.setWindowTitle("Connect Upstox Broker")
        self.setMinimumWidth(560)
        self.setStyleSheet("QDialog { background-color: #0A0D12; }")

        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(18, 16, 18, 16)

        root.addWidget(section_title("UPSTOX OAUTH 2.0 — AUTHORIZATION CODE FLOW"))

        form = QFormLayout()
        form.setSpacing(8)
        self.api_key = QLineEdit(session.client_id)
        self.api_key.setPlaceholderText("API key (client_id) from Developer Apps")
        self.api_secret = QLineEdit(session.client_secret)
        self.api_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_secret.setPlaceholderText("API secret (client_secret)")
        self.redirect = QLineEdit(session.redirect_uri)
        self.redirect.setPlaceholderText(
            "registered redirect URI — must match EXACTLY (e.g. http://127.0.0.1:8765/callback)")
        self.algo_name = QLineEdit(session.algo_name)
        self.algo_name.setPlaceholderText("algo name configured in My Apps (X-Algo-Name)")
        form.addRow("API key", self.api_key)
        form.addRow("API secret", self.api_secret)
        form.addRow("Redirect URI", self.redirect)
        form.addRow("Algo name", self.algo_name)
        root.addLayout(form)

        # step buttons
        steps = QHBoxLayout()
        self.open_btn = QPushButton("① OPEN UPSTOX LOGIN IN BROWSER")
        self.open_btn.setObjectName("ember")
        self.open_btn.clicked.connect(self._open_login)
        steps.addWidget(self.open_btn)
        copy_btn = QPushButton("Copy login URL")
        copy_btn.setObjectName("ghost")
        copy_btn.clicked.connect(self._copy_url)
        steps.addWidget(copy_btn)
        steps.addStretch(1)
        root.addLayout(steps)

        root.addWidget(legend("② paste the redirect url (or just the code) after login"))
        self.code_box = QLineEdit()
        self.code_box.setPlaceholderText("https://127.0.0.1:8765/callback?code=……  (paste here)")
        self.code_box.setFont(mono_font(11))
        root.addWidget(self.code_box)

        # connect row
        conn = QHBoxLayout()
        self.connect_btn = QPushButton("③ CONNECT")
        self.connect_btn.setObjectName("ember")
        self.connect_btn.clicked.connect(self._connect)
        conn.addWidget(self.connect_btn)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("ghost")
        self.cancel_btn.clicked.connect(self.reject)
        conn.addWidget(self.cancel_btn)
        conn.addStretch(1)
        root.addLayout(conn)

        # status
        self.status_lbl = QLabel(self.session.status().describe())
        self.status_lbl.setFont(mono_font(10))
        self.status_lbl.setWordWrap(True)
        self.status_lbl.setStyleSheet("color: #7A8798;")
        root.addWidget(self.status_lbl)

        root.addWidget(hint_label(
            "Verified: the access token expires at 03:30 IST the next day — "
            "there is no refresh token, so this is a daily step. The token "
            "is stored with Windows DPAPI and never written to logs. "
            "Order APIs additionally require a registered static IP "
            "(X-Algo-Name header is sent automatically)."))

    # ------------------------------------------------------------------ #
    def _open_login(self) -> None:
        if not self._save_config():
            return
        url = self.session.login_url()
        QDesktopServices.openUrl(QUrl(url))

    def _copy_url(self) -> None:
        if not self._save_config():
            return
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self.session.login_url())
        self.status_lbl.setText("Login URL copied to clipboard.")
        self.status_lbl.setStyleSheet("color: #FFB020;")

    def _save_config(self) -> bool:
        key = self.api_key.text().strip()
        secret = self.api_secret.text().strip()
        redirect = self.redirect.text().strip()
        if not key or not secret or not redirect:
            QMessageBox.warning(self, "Missing config",
                                "API key, API secret and redirect URI are all "
                                "required (they must match your Upstox app).")
            return False
        self.session.configure(key, secret, redirect,
                               self.algo_name.text().strip(),
                               self.session.sandbox)
        return True

    def _connect(self) -> None:
        if not self._save_config():
            return
        pasted = self.code_box.text()
        if not pasted.strip():
            QMessageBox.warning(self, "Missing code",
                                "Paste the redirect URL (or the authorization "
                                "code) you received after logging in.")
            return
        self.connect_btn.setEnabled(False)
        self.status_lbl.setText("CONNECTING… exchanging code for access token")
        self.status_lbl.setStyleSheet("color: #FFB020;")
        self.repaint()

        status = self.session.connect_with_code(pasted)

        self.connect_btn.setEnabled(True)
        self.status_lbl.setText(status.describe())
        if status.state == ConnectionState.CONNECTED:
            self.status_lbl.setStyleSheet("color: #35D0C8;")
            self.connected.emit({
                "client_id": self.api_key.text().strip(),
                "client_secret": self.api_secret.text().strip(),
                "redirect_uri": self.redirect.text().strip(),
                "algo_name": self.algo_name.text().strip(),
                "expires_at": status.expires_at,
                "sandbox": status.sandbox,
            })
            self.accept()
        else:
            self.status_lbl.setStyleSheet("color: #FF5D5D;")
