"""Small append-only JSONL storage for raw decoded market events."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterable

from .models import OptionQuote


class JsonlQuoteStore:
    """Append quotes with an ingestion timestamp for replay and auditability."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, quotes: Iterable[OptionQuote]) -> int:
        count = 0
        with self.path.open("a", encoding="utf-8") as handle:
            for quote in quotes:
                payload = {
                    "ingested_at": datetime.now(timezone.utc).isoformat(),
                    "timestamp": quote.timestamp.isoformat(),
                    "instrument_key": quote.instrument_key,
                    "ltp": quote.ltp,
                    "bid": quote.bid,
                    "ask": quote.ask,
                    "bid_quantity": quote.bid_quantity,
                    "ask_quantity": quote.ask_quantity,
                    "volume": quote.volume,
                    "open_interest": quote.open_interest,
                    "implied_volatility": quote.implied_volatility,
                    "delta": quote.delta,
                    "gamma": quote.gamma,
                    "theta": quote.theta,
                    "vega": quote.vega,
                }
                handle.write(json.dumps(payload, separators=(",", ":")) + "\n")
                count += 1
        return count
