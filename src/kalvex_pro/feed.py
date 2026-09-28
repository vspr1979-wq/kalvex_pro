"""Normalize decoded Upstox V3 market-feed messages into option quotes.

The official V3 WebSocket transports a binary protobuf message. The decoder is
kept separate from normalization: callers may use the official SDK/protobuf
schema, then pass the decoded mapping to ``parse_feed_payload``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from .models import OptionQuote


def parse_feed_payload(payload: dict[str, Any], received_at: datetime | None = None) -> list[OptionQuote]:
    received_at = received_at or datetime.now(timezone.utc)
    feeds = payload.get("feeds", {}) if isinstance(payload, dict) else {}
    result: list[OptionQuote] = []
    for instrument_key, raw in feeds.items():
        if not isinstance(raw, dict):
            continue
        result.append(_quote_from_feed(str(instrument_key), raw, received_at))
    return [item for item in result if item.ltp >= 0]


def _quote_from_feed(instrument_key: str, raw: dict[str, Any], received_at: datetime) -> OptionQuote:
    outer = _find_node(raw, "firstLevelWithGreeks", "fullFeed", "oc") or raw
    node = _find_node(outer, "marketFF", "firstLevelWithGreeks", "oc") or outer
    ltpc = _find_node(node, "ltpc") or {}
    depth = _find_node(node, "firstDepth", "bidAskQuote") or {}
    if not depth:
        market_level = _find_node(node, "marketLevel") or {}
        quotes = market_level.get("bidAskQuote")
        if isinstance(quotes, list) and quotes and isinstance(quotes[0], dict):
            depth = quotes[0]
    greeks = _find_node(node, "optionGreeks") or {}
    details = _find_node(node, "eFeedDetails") or {}

    timestamp = _timestamp(_first(ltpc, "ltt", "timestamp"), received_at)
    ltp = _float(_first(ltpc, "ltp", "op"), default=0.0)
    bid = _float(_first(depth, "bidP", "bp"))
    ask = _float(_first(depth, "askP", "ap"))
    return OptionQuote(
        timestamp=timestamp,
        instrument_key=instrument_key,
        ltp=ltp,
        bid=bid,
        ask=ask,
        bid_quantity=_int(_first(depth, "bidQ", "bq")),
        ask_quantity=_int(_first(depth, "askQ", "aq")),
        volume=_int(_first(details, "vtt", "volume")),
        open_interest=_int(_first(details, "oi", "openInterest")),
        implied_volatility=_float(_first(greeks, "iv")),
        delta=_float(_first(greeks, "delta")),
        gamma=_float(_first(greeks, "gamma")),
        theta=_float(_first(greeks, "theta")),
        vega=_float(_first(greeks, "vega")),
    )


def _find_node(raw: dict[str, Any], *keys: str) -> dict[str, Any] | None:
    for key in keys:
        value = raw.get(key)
        if isinstance(value, dict):
            return value
    return None


def _first(raw: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in raw:
            return raw[key]
    return None


def _float(value: Any, default: float | None = None) -> float | None:
    if value is None or value == "":
        return default
    return float(value)


def _int(value: Any) -> int:
    if value is None or value == "":
        return 0
    return int(float(value))


def _timestamp(value: Any, fallback: datetime) -> datetime:
    if value is None:
        return fallback
    if isinstance(value, (int, float, str)) and str(value).isdigit():
        return datetime.fromtimestamp(float(value) / 1000, tz=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return fallback
