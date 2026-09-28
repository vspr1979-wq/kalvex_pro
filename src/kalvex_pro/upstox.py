"""Minimal Upstox REST client using the standard library.

No token is read at import time and no order endpoint is exposed in this first
release. This keeps research and market-data credentials separate from live
execution credentials.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
import os
from time import sleep
from typing import Any, Iterator
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .models import Candle


@dataclass(frozen=True)
class UpstoxSettings:
    access_token: str
    base_url: str = "https://api.upstox.com"
    timeout_seconds: float = 20.0
    max_retries: int = 3

    @classmethod
    def from_env(cls) -> "UpstoxSettings":
        token = os.getenv("UPSTOX_ACCESS_TOKEN", "").strip()
        if not token:
            raise ValueError("UPSTOX_ACCESS_TOKEN is not set")
        return cls(
            access_token=token,
            base_url=os.getenv("UPSTOX_API_BASE_URL", cls.base_url).rstrip("/"),
            timeout_seconds=float(os.getenv("UPSTOX_TIMEOUT_SECONDS", "20")),
        )


class UpstoxAPIError(RuntimeError):
    pass


class UpstoxClient:
    def __init__(self, settings: UpstoxSettings):
        self.settings = settings

    def request_json(self, method: str, path: str, query: dict[str, str] | None = None) -> Any:
        url = f"{self.settings.base_url}/{path.lstrip('/')}"
        if query:
            url += "?" + "&".join(f"{quote(str(k))}={quote(str(v), safe='|,') }" for k, v in query.items())
        request = Request(
            url,
            method=method.upper(),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.settings.access_token}",
            },
        )
        for attempt in range(self.settings.max_retries + 1):
            try:
                with urlopen(request, timeout=self.settings.timeout_seconds) as response:
                    return json.loads(response.read().decode("utf-8"))
            except HTTPError as error:
                body = error.read().decode("utf-8", errors="replace")
                if error.code in {429, 500, 502, 503, 504} and attempt < self.settings.max_retries:
                    sleep(2**attempt)
                    continue
                raise UpstoxAPIError(f"Upstox {error.code} for {path}: {body[:500]}") from error
            except URLError as error:
                if attempt < self.settings.max_retries:
                    sleep(2**attempt)
                    continue
                raise UpstoxAPIError(f"Unable to reach Upstox: {error}") from error
        raise AssertionError("unreachable")

    def historical_candles(
        self,
        instrument_key: str,
        unit: str,
        interval: int,
        to_date: date,
        from_date: date | None = None,
    ) -> list[Candle]:
        path = f"/v3/historical-candle/{quote(instrument_key, safe='')}/{unit}/{interval}/{to_date.isoformat()}"
        if from_date:
            path += f"/{from_date.isoformat()}"
        payload = self.request_json("GET", path)
        return parse_candles(payload, instrument_key)

    def expired_historical_candles(
        self,
        expired_instrument_key: str,
        interval: str,
        to_date: date,
        from_date: date,
    ) -> list[Candle]:
        path = (
            f"/v2/expired-instruments/historical-candle/{quote(expired_instrument_key, safe='')}/"
            f"{quote(interval, safe='')}/{to_date.isoformat()}/{from_date.isoformat()}"
        )
        payload = self.request_json("GET", path)
        return parse_candles(payload, expired_instrument_key)

    def option_chain(self, underlying_key: str, expiry_date: date) -> dict[str, Any]:
        return self.request_json(
            "GET",
            "/v2/option/chain",
            {"instrument_key": underlying_key, "expiry_date": expiry_date.isoformat()},
        )

    def option_greeks(self, instrument_keys: Iterator[str] | list[str]) -> dict[str, Any]:
        keys = ",".join(instrument_keys)
        return self.request_json("GET", "/v3/market-quote/option-greek", {"instrument_key": keys})


def parse_candles(payload: Any, instrument_key: str) -> list[Candle]:
    """Parse Upstox candle arrays: timestamp, OHLC, volume, open-interest."""
    candles = payload.get("data", {}).get("candles", []) if isinstance(payload, dict) else []
    parsed: list[Candle] = []
    from datetime import datetime

    for row in candles:
        if len(row) < 6:
            continue
        timestamp = row[0]
        if isinstance(timestamp, (int, float)):
            dt = datetime.fromtimestamp(timestamp / 1000).astimezone()
        else:
            dt = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        parsed.append(
            Candle(
                timestamp=dt,
                instrument_key=instrument_key,
                open=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=float(row[4]),
                volume=int(row[5] or 0),
                open_interest=int(row[6] or 0) if len(row) > 6 else 0,
            )
        )
    return sorted(parsed, key=lambda item: item.timestamp)
