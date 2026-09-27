"""Broker session lifecycle: connect (OAuth) / disconnect / token state.

Verified Upstox facts baked in here (Sept 2026 docs):
  * OAuth authorization-code flow: GET /v2/login/authorization/dialog then
    POST /v2/login/authorization/token (code, client_id, client_secret,
    redirect_uri, grant_type=authorization_code).
  * There is NO refresh token — the access token dies at 03:30 IST the
    following day. Expiry is computed from that fixed wall-clock rule
    (never 'now + 24h').
  * Tokens are stored with Windows DPAPI (TokenStore) — never plaintext.

The exchange call is injectable so the state machine is unit-testable
without network access.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

from kalvex.core.execution import LiveBrokerAdapter
from kalvex.core.security import TokenStore

IST = ZoneInfo("Asia/Kolkata")

# Verified: token cut-off is 03:30 IST daily.
TOKEN_CUTOFF_HH = 3
TOKEN_CUTOFF_MM = 30
# Safety buffer: treat the token as dead this many seconds before cut-off so
# a cycle never starts an order that dies mid-flight.
TOKEN_EXPIRY_BUFFER_S = 900


class ConnectionState(str, Enum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    EXPIRED = "EXPIRED"
    ERROR = "ERROR"


@dataclass
class SessionStatus:
    state: ConnectionState
    detail: str = ""
    expires_at: str = ""          # ISO IST wall-clock
    sandbox: bool = True
    algo_name: str = ""

    def describe(self) -> str:
        if self.state == ConnectionState.CONNECTED:
            return f"UPSTOX · CONNECTED · token until {self.expires_at}"
        if self.state == ConnectionState.EXPIRED:
            return "UPSTOX · TOKEN EXPIRED · re-login required"
        if self.state == ConnectionState.CONNECTING:
            return "UPSTOX · CONNECTING…"
        if self.state == ConnectionState.ERROR:
            return f"UPSTOX · ERROR · {self.detail[:40]}"
        return "DISCONNECTED"


def compute_token_expiry(issue_time: datetime | None = None) -> datetime:
    """The next 03:30 IST strictly after issue_time (verified rule).

    A token issued at 20:00 IST expires 03:30 IST the next morning — NOT
    24h later. A token issued at 02:00 IST still expires at 03:30 the same
    morning.
    """
    now = issue_time or datetime.now(IST)
    if now.tzinfo is None:
        now = now.replace(tzinfo=IST)
    cutoff = now.replace(hour=TOKEN_CUTOFF_HH, minute=TOKEN_CUTOFF_MM,
                         second=0, microsecond=0)
    if cutoff <= now:
        cutoff += timedelta(days=1)
    return cutoff


def extract_code(text: str) -> str:
    """Accepts a full redirect URL (…?code=abc&state=…) or a bare code."""
    text = text.strip().strip('"').strip("'")
    if not text:
        return ""
    if "://" in text or "?" in text or "code=" in text:
        query = parse_qs(urlparse(text).query)
        codes = query.get("code", [])
        return codes[0] if codes else ""
    if any(ch.isspace() for ch in text):
        return ""          # prose/paste error — codes never contain spaces
    return text            # bare authorization code


class BrokerSession:
    """Owns the Upstox connection state. Qt-free and unit-testable."""

    def __init__(self, token_store: TokenStore, client_id: str = "",
                 client_secret: str = "", redirect_uri: str = "",
                 algo_name: str = "", sandbox: bool = True) -> None:
        self.store = token_store
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.algo_name = algo_name
        self.sandbox = sandbox
        self._last_error = ""

    # ---- configuration -------------------------------------------------
    def configure(self, client_id: str, client_secret: str, redirect_uri: str,
                  algo_name: str, sandbox: bool) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.algo_name = algo_name
        self.sandbox = sandbox

    # ---- URLs ----------------------------------------------------------
    def login_url(self) -> str:
        return LiveBrokerAdapter.build_login_url(
            self.client_id, self.redirect_uri, state="kalvex-pro")

    # ---- state ---------------------------------------------------------
    def status(self) -> SessionStatus:
        token, expires_iso = self.store.load()
        if self._last_error and not token:
            return SessionStatus(ConnectionState.ERROR, self._last_error,
                                 sandbox=self.sandbox, algo_name=self.algo_name)
        if not token:
            return SessionStatus(ConnectionState.DISCONNECTED,
                                 sandbox=self.sandbox, algo_name=self.algo_name)
        expiry = self._parse_expiry(expires_iso)
        if expiry is None or not self._token_alive(expiry):
            return SessionStatus(ConnectionState.EXPIRED,
                                 "access token past its 03:30 IST cut-off",
                                 expires_iso, self.sandbox, self.algo_name)
        return SessionStatus(ConnectionState.CONNECTED, "", expires_iso,
                             self.sandbox, self.algo_name)

    @staticmethod
    def _parse_expiry(iso: str) -> datetime | None:
        if not iso:
            return None
        try:
            dt = datetime.fromisoformat(iso)
            return dt if dt.tzinfo else dt.replace(tzinfo=IST)
        except ValueError:
            return None

    @staticmethod
    def _token_alive(expiry: datetime, now: datetime | None = None) -> bool:
        now = now or datetime.now(IST)
        return (expiry - now).total_seconds() > TOKEN_EXPIRY_BUFFER_S

    # ---- connect / disconnect -----------------------------------------
    def connect_with_code(self, pasted: str,
                          exchanger=None) -> SessionStatus:
        """Exchange a pasted redirect URL/code for an access token.

        Returns the ATTEMPT result (ERROR on failure — an existing valid
        token is left untouched). `exchanger` is injectable for tests;
        defaults to the verified Upstox endpoint call.
        """
        self._last_error = ""
        code = extract_code(pasted)
        if not code:
            self._last_error = "no authorization code found in pasted text"
            return SessionStatus(ConnectionState.ERROR, self._last_error,
                                 sandbox=self.sandbox, algo_name=self.algo_name)
        if not self.client_id or not self.client_secret or not self.redirect_uri:
            self._last_error = "API key / secret / redirect URI not configured"
            return SessionStatus(ConnectionState.ERROR, self._last_error,
                                 sandbox=self.sandbox, algo_name=self.algo_name)

        exchanger = exchanger or LiveBrokerAdapter.exchange_code
        try:
            resp = exchanger(code, self.client_id, self.client_secret,
                             self.redirect_uri)
        except Exception as e:  # network/HTTP/SDK failures -> ERROR result
            self._last_error = f"token exchange failed: {e}"
            return SessionStatus(ConnectionState.ERROR, self._last_error,
                                 sandbox=self.sandbox, algo_name=self.algo_name)

        token = (resp or {}).get("access_token", "")
        if not token:
            self._last_error = "no access_token in response (check the code/secret)"
            return SessionStatus(ConnectionState.ERROR, self._last_error,
                                 sandbox=self.sandbox, algo_name=self.algo_name)

        # Verified rule: expiry is the 03:30 IST cut-off, not now+24h.
        expiry = compute_token_expiry()
        self.store.save(token, expiry.isoformat())
        return self.status()

    def disconnect(self) -> SessionStatus:
        """Wipe the stored token — live routing is impossible afterwards."""
        self._last_error = ""
        try:
            self.store.wipe()
        except OSError:
            pass
        return self.status()

    # ---- helpers for the live adapter ---------------------------------
    def adapter(self) -> LiveBrokerAdapter:
        return LiveBrokerAdapter(self.store, algo_name=self.algo_name,
                                 client_id=self.client_id, sandbox=self.sandbox)
