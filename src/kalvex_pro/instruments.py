"""Instrument-master parsing and dynamic NSE/BSE options universe selection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import gzip
import json
from pathlib import Path
import re
from typing import Iterable, Sequence
from urllib.request import Request, urlopen

from .models import Instrument


INDEX_ALIASES: dict[str, tuple[str, ...]] = {
    "NIFTY": ("NIFTY 50", "NIFTY50", "NIFTY"),
    "SENSEX": ("SENSEX", "BSE SENSEX"),
    "BANKNIFTY": ("NIFTY BANK", "BANKNIFTY", "NIFTYBANK", "BANK NIFTY"),
    "FINNIFTY": ("NIFTY FIN SERVICE", "NIFTY FINANCIAL SERVICES", "FINNIFTY", "NIFTY FIN"),
    "MIDCAPNIFTY": ("NIFTY MID SELECT", "NIFTY MIDCAP SELECT", "MIDCPNIFTY", "MIDCAPNIFTY"),
}


def normalize_symbol(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def canonical_index_alias(value: str) -> str | None:
    normalized = normalize_symbol(value)
    for alias, names in INDEX_ALIASES.items():
        if normalized in {normalize_symbol(name) for name in names}:
            return alias
    return None


def load_instrument_master(path: str | Path) -> list[Instrument]:
    """Load an Upstox JSON or gzip-compressed JSON instrument master."""
    source = Path(path)
    if source.suffix == ".gz":
        with gzip.open(source, "rt", encoding="utf-8") as handle:
            raw = json.load(handle)
    else:
        raw = json.loads(source.read_text())
    records = raw.get("data", raw) if isinstance(raw, dict) else raw
    if isinstance(records, dict):
        records = list(records.values())
    return [Instrument.from_upstox(record) for record in records if isinstance(record, dict)]


def download_instrument_master(exchange: str, destination: str | Path) -> Path:
    """Download the official Upstox BOD JSON file for NSE or BSE."""
    exchange = exchange.upper()
    if exchange not in {"NSE", "BSE"}:
        raise ValueError("exchange must be NSE or BSE")
    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://assets.upstox.com/market-quote/instruments/exchange/{exchange}.json.gz"
    request = Request(url, headers={"User-Agent": "kalvex-pro/0.1"})
    try:
        with urlopen(request, timeout=60) as response, output.open("wb") as handle:
            handle.write(response.read())
    except Exception as exc:
        raise RuntimeError(f"Unable to download the Upstox {exchange} instrument master from {url}: {exc}") from exc
    return output


@dataclass(frozen=True)
class UniverseRequest:
    exchanges: tuple[str, ...] = ("NSE", "BSE")
    index_aliases: tuple[str, ...] = ("NIFTY", "SENSEX", "BANKNIFTY", "FINNIFTY", "MIDCAPNIFTY")
    include_fno_stocks: bool = True
    option_types: tuple[str, ...] = ("CE", "PE")
    as_of: date | None = None
    minimum_days_to_expiry: int = 1
    maximum_days_to_expiry: int = 30


class OptionsUniverse:
    """Builds an options universe from the current or historical instrument master.

    The stock list is deliberately derived from OPTSTK records, so newly eligible
    F&O stocks are included without changing application code.
    """

    def __init__(self, instruments: Iterable[Instrument]):
        self.instruments = tuple(instruments)

    def select(self, request: UniverseRequest = UniverseRequest()) -> list[Instrument]:
        exchanges = {item.upper() for item in request.exchanges}
        aliases = {item.upper() for item in request.index_aliases}
        option_types = {item.upper() for item in request.option_types}
        as_of = request.as_of or date.today()
        selected: list[Instrument] = []
        for instrument in self.instruments:
            if not instrument.is_option or instrument.exchange not in exchanges:
                continue
            if instrument.option_type not in option_types:
                continue
            if instrument.expiry is None:
                continue
            dte = (instrument.expiry - as_of).days
            if dte < request.minimum_days_to_expiry or dte > request.maximum_days_to_expiry:
                continue
            if instrument.is_index_option:
                if self._index_alias(instrument) in aliases:
                    selected.append(instrument)
            elif instrument.is_fno_stock_option and request.include_fno_stocks:
                selected.append(instrument)
        return sorted(selected, key=lambda item: (item.exchange, item.underlying_symbol, item.expiry or date.max, item.strike_price or 0, item.option_type or ""))

    def underlying_symbols(self, request: UniverseRequest = UniverseRequest()) -> set[str]:
        return {item.underlying_key or item.underlying_symbol for item in self.select(request) if item.underlying_key or item.underlying_symbol}

    @staticmethod
    def _index_alias(instrument: Instrument) -> str | None:
        for value in (instrument.underlying_symbol, instrument.name, instrument.trading_symbol, instrument.underlying_key):
            alias = canonical_index_alias(value)
            if alias:
                return alias
        return None


def summarize(universe: Sequence[Instrument]) -> dict[str, int]:
    """Return a compact, serializable inventory summary."""
    result: dict[str, int] = {}
    for item in universe:
        key = f"{item.exchange}:{'index' if item.is_index_option else 'stock'}:{item.option_type}"
        result[key] = result.get(key, 0) + 1
    return dict(sorted(result.items()))
