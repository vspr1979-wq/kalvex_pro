"""Instrument registry — everything comes from the Upstox instrument master.

Verified: the master JSON (complete.json) carries instrument_key,
trading_symbol, name, segment, instrument_type, lot_size, tick_size,
strike_price, expiry, underlying_key, freeze_quantity.

Nothing here is guessed: index instrument keys are RESOLVED from the master
by trading symbol. If an instrument cannot be resolved it is reported as
UNKNOWN and cannot be traded — no placeholder lot sizes ever reach an order.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from kalvex.core.upstox_api import OptionContract, UpstoxApi

# v1 option-buying universe (user can extend in settings). Resolution is by
# trading_symbol against the live master — the keys are data, not code.
INDEX_UNIVERSE: tuple[str, ...] = (
    "NIFTY",        # NSE_INDEX|Nifty 50        (verified key format)
    "SENSEX",       # BSE index                 (key resolved from master)
    "BANKNIFTY",    # NSE_INDEX|Nifty Bank      (verified key format)
    "FINNIFTY",     # Nifty Fin Service         (key resolved from master)
    "MIDCAPNIFTY",  # Nifty Midcap Select       (key resolved from master)
)

# Master rows sometimes spell these differently — try each candidate.
_SYMBOL_CANDIDATES: dict[str, tuple[str, ...]] = {
    "NIFTY": ("NIFTY", "NIFTY 50"),
    "SENSEX": ("SENSEX", "BSE SENSEX"),
    "BANKNIFTY": ("BANKNIFTY", "NIFTY BANK"),
    "FINNIFTY": ("FINNIFTY", "NIFTY FIN SERVICE", "NIFTY FINANCIAL SERVICES"),
    "MIDCAPNIFTY": ("MIDCAPNIFTY", "MIDCPNIFTY", "NIFTY MIDCAP SELECT"),
}


@dataclass
class InstrumentSpec:
    display: str            # "NIFTY", "BANKNIFTY"…
    key: str                # Upstox instrument_key
    trading_symbol: str
    name: str
    segment: str
    instrument_type: str
    lot_size: int           # from the master — NEVER guessed
    tick_size: float
    resolved: bool = True
    note: str = ""

    @property
    def is_index(self) -> bool:
        return self.instrument_type == "INDEX"


class InstrumentMaster:
    """Parses and caches the Upstox instrument master."""

    def __init__(self, cache_dir: str | Path = "data") -> None:
        self.cache_path = Path(cache_dir) / "instrument_master.json"
        self.rows: list[dict] = []
        self.fetched_at: str = ""
        self._by_key: dict[str, dict] = {}
        self._by_symbol: dict[tuple[str, str], dict] = {}   # (exchange, symbol)
        self._load_cache()

    # ---- cache ---------------------------------------------------------
    def _load_cache(self) -> None:
        if self.cache_path.exists():
            try:
                blob = json.loads(self.cache_path.read_text(encoding="utf-8"))
                self.fetched_at = blob.get("fetched_at", "")
                self._index(blob.get("rows", []))
            except (OSError, json.JSONDecodeError):
                pass

    def _index(self, rows: list[dict]) -> None:
        self.rows = rows
        self._by_key = {}
        self._by_symbol = {}
        for r in rows:
            key = r.get("instrument_key", "")
            if key:
                self._by_key[key] = r
            sym = (r.get("exchange", ""), (r.get("trading_symbol") or "").upper())
            self._by_symbol.setdefault(sym, r)

    def fetch(self) -> int:
        """Download the master from Upstox and refresh the cache."""
        from datetime import datetime
        from zoneinfo import ZoneInfo
        rows = UpstoxApi.fetch_instrument_master()
        self.fetched_at = datetime.now(ZoneInfo("Asia/Kolkata")).strftime(
            "%Y-%m-%d %H:%M:%S")
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps({"fetched_at": self.fetched_at, "rows": rows}),
            encoding="utf-8")
        self._index(rows)
        return len(rows)

    @property
    def count(self) -> int:
        return len(self.rows)

    # ---- resolution ----------------------------------------------------
    def resolve_index(self, display: str) -> InstrumentSpec:
        """Resolve a watchlist name (NIFTY/SENSEX/…) to a live master row.

        Returns resolved=False with an explicit UNKNOWN note if the master
        has not been fetched or the symbol cannot be found — the UI blocks
        trading on unresolved instruments.
        """
        candidates = _SYMBOL_CANDIDATES.get(display.upper(), (display.upper(),))
        for exchange in ("NSE", "BSE"):
            for cand in candidates:
                row = self._by_symbol.get((exchange, cand))
                if row and row.get("instrument_type") == "INDEX":
                    return self._spec(display, row)
        # fallback: match by name
        for row in self.rows:
            if row.get("instrument_type") != "INDEX":
                continue
            name = (row.get("name") or "").upper()
            if any(cand in name for cand in candidates):
                return self._spec(display, row)
        return InstrumentSpec(
            display=display, key="", trading_symbol=display, name=display,
            segment="", instrument_type="INDEX", lot_size=0, tick_size=0.0,
            resolved=False,
            note="UNKNOWN — not in instrument master; fetch master or edit key")

    @staticmethod
    def _spec(display: str, row: dict) -> InstrumentSpec:
        return InstrumentSpec(
            display=display, key=row.get("instrument_key", ""),
            trading_symbol=row.get("trading_symbol", ""),
            name=row.get("name", ""), segment=row.get("segment", ""),
            instrument_type=row.get("instrument_type", ""),
            lot_size=int(row.get("lot_size") or 0),
            tick_size=float(row.get("tick_size") or 0.0),
            note="from Upstox instrument master")

    def watchlist(self) -> list[InstrumentSpec]:
        return [self.resolve_index(name) for name in INDEX_UNIVERSE]

    def expiries_from_master(self, underlying_key: str) -> list[str]:
        """Distinct expiry dates for the underlying's options in the master,
        sorted ascending (current expiry first)."""
        expiries = {
            r.get("expiry") for r in self.rows
            if r.get("underlying_key") == underlying_key and r.get("expiry")
        }
        return sorted(expiries)

    def option_contracts(self, api: UpstoxApi, underlying_key: str,
                         expiry: str | None = None) -> list[OptionContract]:
        """Live option contracts from Upstox (lot sizes/strikes come from
        the exchange rows themselves)."""
        return api.option_contracts(underlying_key, expiry)
