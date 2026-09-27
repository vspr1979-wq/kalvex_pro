"""Upstox REST client — VERIFIED endpoints only, nothing invented.

Verified (official docs / examples, Sept 2026):
  * GET  https://assets.upstox.com/market-quote/instruments/exchange/complete.json
         instrument master (public, no auth): instrument_key, trading_symbol,
         name, segment, exchange, instrument_type (INDEX/FUT/CE/PE/EQ…),
         lot_size, tick_size, strike_price, expiry, underlying_key,
         freeze_quantity, minimum_lot
  * GET  /v2/market-quote/quotes?instrument_key=K1,K2   full quotes
         (response: data keyed by instrument_key, incl. last_price, ohlc —
         exact field list to eyeball against the docs sample on first run)
  * GET  /v2/option/contract?instrument_key=<underlying>&expiry_date=YYYY-MM-DD
         option contracts: strike_price, instrument_key, lot_size, tick_size,
         instrument_type (CE/PE), expiry, trading_symbol, freeze_quantity
  * GET  /v2/option/chain?instrument_key=<underlying>&expiry_date=YYYY-MM-DD
         chain with per-strike CE/PE market data (IV etc. — passthrough only)
  * Order placement goes through the SDK (PlaceOrderV3Request) — see
    execution.py. Standard APIs are rate-limited to 50/sec (order APIs
    10/sec) — this client throttles conservatively to 10/sec.
"""

from __future__ import annotations

import gzip
import json
import time
from dataclasses import dataclass, field

import requests

BASE_URL = "https://api.upstox.com"
INSTRUMENT_MASTER_URL = (
    "https://assets.upstox.com/market-quote/instruments/exchange/complete.json")

# Conservative client-side throttle (verified order cap is 10/sec; standard
# APIs 50/sec — stay well under both).
_MIN_REQUEST_GAP_S = 0.1


@dataclass
class Quote:
    instrument_key: str
    last_price: float = 0.0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: float = 0.0
    timestamp: str = ""
    raw: dict = field(default_factory=dict)


@dataclass
class OptionContract:
    instrument_key: str
    trading_symbol: str
    strike_price: float
    instrument_type: str        # "CE" | "PE"
    expiry: str                 # YYYY-MM-DD
    lot_size: int
    tick_size: float
    freeze_quantity: int = 0
    underlying_key: str = ""
    underlying_symbol: str = ""


class UpstoxApi:
    """Thin REST wrapper. `token_provider` is a callable returning the
    current access token (or None when disconnected)."""

    def __init__(self, token_provider) -> None:
        self._token_provider = token_provider
        self._last_call = 0.0

    # ---- plumbing ------------------------------------------------------
    def _headers(self) -> dict:
        token = self._token_provider()
        if not token:
            raise RuntimeError("Not connected — no Upstox access token")
        return {"Accept": "application/json",
                "Authorization": f"Bearer {token}"}

    def _throttle(self) -> None:
        gap = time.monotonic() - self._last_call
        if gap < _MIN_REQUEST_GAP_S:
            time.sleep(_MIN_REQUEST_GAP_S - gap)
        self._last_call = time.monotonic()

    def _get(self, path: str, params: dict | None = None) -> dict:
        self._throttle()
        resp = requests.get(f"{BASE_URL}{path}", params=params,
                            headers=self._headers(), timeout=10)
        resp.raise_for_status()
        body = resp.json()
        if body.get("status") not in (None, "success"):
            raise RuntimeError(f"Upstox API error: {body.get('errors') or body}")
        return body

    # ---- instrument master (public, cached by the caller) --------------
    @staticmethod
    def fetch_instrument_master() -> list[dict]:
        resp = requests.get(INSTRUMENT_MASTER_URL, timeout=60,
                            headers={"Accept": "application/json"})
        resp.raise_for_status()
        if resp.headers.get("Content-Encoding") == "gzip" or \
                resp.content[:2] == b"\x1f\x8b":
            resp.content = gzip.decompress(resp.content)
        return json.loads(resp.content)

    # ---- quotes --------------------------------------------------------
    def quotes(self, instrument_keys: list[str]) -> dict[str, Quote]:
        """GET /v2/market-quote/quotes — comma-separated instrument keys."""
        if not instrument_keys:
            return {}
        body = self._get("/v2/market-quote/quotes",
                         {"instrument_key": ",".join(instrument_keys)})
        out: dict[str, Quote] = {}
        for key, payload in (body.get("data") or {}).items():
            q = Quote(instrument_key=key, raw=payload)
            # field names per docs sample; parsed defensively
            q.last_price = float(payload.get("last_price") or 0.0)
            ohlc = payload.get("ohlc") or {}
            q.open = float(ohlc.get("open") or 0.0)
            q.high = float(ohlc.get("high") or 0.0)
            q.low = float(ohlc.get("low") or 0.0)
            q.close = float(ohlc.get("close") or 0.0)
            q.volume = float(payload.get("volume") or 0.0)
            q.timestamp = str(payload.get("timestamp") or "")
            out[key] = q
        return out

    # ---- options -------------------------------------------------------
    def option_contracts(self, underlying_key: str,
                         expiry: str | None = None) -> list[OptionContract]:
        """GET /v2/option/contract — the exchange contract list (lot sizes,
        strike prices, freeze quantities come straight from here)."""
        params: dict = {"instrument_key": underlying_key}
        if expiry:
            params["expiry_date"] = expiry
        body = self._get("/v2/option/contract", params)
        out: list[OptionContract] = []
        for row in (body.get("data") or []):
            out.append(OptionContract(
                instrument_key=row.get("instrument_key", ""),
                trading_symbol=row.get("trading_symbol", ""),
                strike_price=float(row.get("strike_price") or 0.0),
                instrument_type=row.get("instrument_type", ""),
                expiry=str(row.get("expiry") or ""),
                lot_size=int(row.get("lot_size") or 0),
                tick_size=float(row.get("tick_size") or 0.0),
                freeze_quantity=int(row.get("freeze_quantity") or 0),
                underlying_key=row.get("underlying_key", ""),
                underlying_symbol=row.get("underlying_symbol", ""),
            ))
        return out

    def option_chain(self, underlying_key: str,
                     expiry: str) -> list[dict]:
        """GET /v2/option/chain — rows with CE/PE market data.

        The per-strike market fields (IV, greeks, LTP) are passed through
        UNMODIFIED — no pricing model is applied anywhere in this app.
        """
        body = self._get("/v2/option/chain",
                         {"instrument_key": underlying_key,
                          "expiry_date": expiry})
        return list(body.get("data") or [])

    # ---- funds (verified SDK surface; REST path kept via SDK adapter in
    #      execution.py — direct REST path not re-verified here) ---------
