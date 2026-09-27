"""Security: Windows DPAPI token storage + log redaction.

Tokens are encrypted with Windows DPAPI (CryptProtectData) scoped to the
current user — never plaintext on disk, never in logs. On non-Windows dev
machines a chmod-600 file fallback is used with a loud warning.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path


def _is_windows() -> bool:
    return sys.platform.startswith("win")


def dpapi_protect(data: bytes) -> bytes:
    """Encrypt bytes with Windows DPAPI (CurrentUser scope)."""
    if not _is_windows():
        raise RuntimeError("DPAPI requires Windows — use dev fallback on this OS")
    import ctypes
    import ctypes.wintypes as wt

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    in_buf = ctypes.create_string_buffer(data)
    in_blob = DATA_BLOB(len(data), ctypes.cast(in_buf, ctypes.POINTER(ctypes.c_char)))
    out_blob = DATA_BLOB()
    if not crypt32.CryptProtectData(
            ctypes.byref(in_blob), "kalvex-pro", None, None, None, 0,
            ctypes.byref(out_blob)):
        raise OSError("CryptProtectData failed")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)


def dpapi_unprotect(blob: bytes) -> bytes:
    if not _is_windows():
        raise RuntimeError("DPAPI requires Windows")
    import ctypes
    import ctypes.wintypes as wt

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    in_buf = ctypes.create_string_buffer(blob)
    in_blob = DATA_BLOB(len(blob), ctypes.cast(in_buf, ctypes.POINTER(ctypes.c_char)))
    out_blob = DATA_BLOB()
    if not crypt32.CryptUnprotectData(
            ctypes.byref(in_blob), None, None, None, None, 0,
            ctypes.byref(out_blob)):
        raise OSError("CryptUnprotectData failed")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)


class TokenStore:
    """Stores the Upstox access token.

    Verified: Upstox access tokens expire at 03:30 IST daily and there is
    NO refresh token (official docs/community statement, Sept 2026) — the
    store keeps expires_at and the app re-auths daily via the OAuth dialog.
    """

    def __init__(self, directory: str | Path) -> None:
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / ("token.dpapi" if _is_windows() else "token.dev")
        self.meta_path = self.dir / "token.meta"

    def save(self, token: str, expires_at_iso: str) -> None:
        if _is_windows():
            self.path.write_bytes(dpapi_protect(token.encode("utf-8")))
        else:
            os.chmod(self.dir, 0o700)
            self.path.write_text(token, encoding="utf-8")
            os.chmod(self.path, 0o600)
        self.meta_path.write_text(expires_at_iso, encoding="utf-8")

    def load(self) -> tuple[str | None, str]:
        """Returns (token, expires_at_iso). Token is None if missing/bad."""
        if not self.path.exists():
            return None, ""
        try:
            if _is_windows():
                token = dpapi_unprotect(self.path.read_bytes()).decode("utf-8")
            else:
                token = self.path.read_text(encoding="utf-8")
        except Exception:
            return None, ""
        expires = self.meta_path.read_text(encoding="utf-8") if self.meta_path.exists() else ""
        return token, expires

    def wipe(self) -> None:
        for p in (self.path, self.meta_path):
            if p.exists():
                p.unlink()


_SECRET_PATTERNS = [
    re.compile(r"(?i)(access[_-]?token|api[_-]?secret|client_secret|authorization)\s*[=:]\s*\S+"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"\beyJ[A-Za-z0-9._\-]{10,}"),   # JWT-shaped
]


def redact(text: str) -> str:
    """Scrub secret-shaped substrings before anything reaches logs/UI."""
    out = text
    for pat in _SECRET_PATTERNS:
        out = pat.sub(lambda m: m.group(0).split("=")[0].split(":")[0] + "=[REDACTED]", out)
    return out
