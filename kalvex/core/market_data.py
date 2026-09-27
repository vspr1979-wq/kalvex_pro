"""Market data providers.

- UpstoxLiveFeed : PRODUCTION feed — live quotes polled from the verified
  GET /v2/market-quote/quotes endpoint (bars accumulated from the live
  stream; the websocket protobuf feed can replace the polling loop when
  MarketDataFeed_pb2 is compiled from the official proto).
- SimFeedProvider: TEST HARNESS ONLY — used exclusively by
  `python main.py --selftest` to exercise the engine offline. It is NOT
  wired into the GUI: when the broker is disconnected the app shows no
  data rather than synthetic prices.
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from kalvex.core.models import Bar, Tick
from kalvex.core.upstox_api import UpstoxApi

IST = ZoneInfo("Asia/Kolkata")


class FeedProvider(ABC):
    @abstractmethod
    def now(self) -> datetime: ...

    @abstractmethod
    def ltp(self, instrument: str) -> float: ...

    @abstractmethod
    def bars(self, instrument: str, minutes: int = 1) -> list[Bar]: ...

    def option_greeks(self, instrument: str) -> dict:
        """IV/Greeks passthrough — empty unless the feed provides them."""
        return {}


class UpstoxLiveFeed(FeedProvider):
    """Live quotes from Upstox REST (verified endpoint), 1-minute bars
    accumulated from the stream. Display names map to instrument keys."""

    def __init__(self, api: UpstoxApi, instruments: dict[str, str]) -> None:
        """instruments: display name -> instrument_key (resolved from the
        Upstox instrument master)."""
        self.api = api
        self.keys = dict(instruments)          # display -> key
        self._names = {v: k for k, v in self.keys.items()}
        self._ltp: dict[str, float] = {}
        self._bars: dict[str, list[Bar]] = {k: [] for k in instruments}
        self._open_bar: dict[str, Bar | None] = {k: None for k in instruments}
        self._last_quote_error = ""

    def now(self) -> datetime:
        return datetime.now(IST)

    def set_instruments(self, instruments: dict[str, str]) -> None:
        self.keys = dict(instruments)
        self._names = {v: k for k, v in self.keys.items()}
        for k in self.keys:
            self._bars.setdefault(k, [])
            self._open_bar.setdefault(k, None)

    def ltp(self, instrument: str) -> float:
        return self._ltp.get(instrument, 0.0)

    def bars(self, instrument: str, minutes: int = 1) -> list[Bar]:
        return list(self._bars.get(instrument, []))

    @property
    def last_error(self) -> str:
        return self._last_quote_error

    def poll(self) -> dict[str, Tick]:
        """Fetch one round of live quotes; returns fresh ticks.

        On API errors the previous prices are kept and the error is exposed
        via last_error — the UI shows 'stale' rather than fake numbers.
        """
        if not self.keys:
            return {}
        try:
            quotes = self.api.quotes(list(self.keys.values()))
            self._last_quote_error = ""
        except Exception as e:
            self._last_quote_error = str(e)
            return {}
        out: dict[str, Tick] = {}
        now = self.now()
        for key, q in quotes.items():
            name = self._names.get(key, key)
            self._ltp[name] = q.last_price
            self._accumulate(name, now, q.last_price, q.volume)
            out[name] = Tick(ts=now, ltp=q.last_price)
        return out

    def _accumulate(self, name: str, now: datetime, px: float, vol: float) -> None:
        minute = now.replace(second=0, microsecond=0)
        cur = self._open_bar[name]
        if cur is None or cur.ts != minute:
            if cur is not None:
                self._bars[name].append(cur)
                if len(self._bars[name]) > 1500:
                    self._bars[name] = self._bars[name][-1500:]
            self._open_bar[name] = Bar(ts=minute, open=px, high=px, low=px,
                                       close=px, volume=max(vol, 1.0))
        else:
            cur.high = max(cur.high, px)
            cur.low = min(cur.low, px)
            cur.close = px
            cur.volume = vol or cur.volume

    def option_greeks(self, instrument: str) -> dict:
        """Passthrough from the option chain — only when the caller has
        fetched it (see options.py). Never synthesised."""
        return {}


# --------------------------------------------------------------------- #
# TEST HARNESS — offline self-test only, not used by the GUI
# --------------------------------------------------------------------- #
class SimFeedProvider(FeedProvider):
    """Deterministic regime-switching synthetic feed (SELF-TEST ONLY).

    This is the app's unit-test fixture, not product data. The GUI never
    constructs it: with no broker connected, live mode shows no data.
    """

    def __init__(self, instruments: dict[str, float], seed: int = 7,
                 start: datetime | None = None, speed: float = 1.0,
                 volatility: float = 0.0011) -> None:
        self._rng = random.Random(seed)
        self._prices = dict(instruments)
        self._start = start or datetime.now(IST).replace(
            hour=9, minute=15, second=0, microsecond=0)
        self._tick_count = 0
        self.speed = speed
        self.volatility = volatility
        self._bars: dict[str, list[Bar]] = {k: [] for k in instruments}
        self._bar_open: dict[str, Bar | None] = {k: None for k in instruments}
        self._regime = 1
        self._regime_left = 40

    def now(self) -> datetime:
        return self._start + timedelta(seconds=self._tick_count * self.speed)

    def ltp(self, instrument: str) -> float:
        return self._prices.get(instrument, 0.0)

    def bars(self, instrument: str, minutes: int = 1) -> list[Bar]:
        return list(self._bars.get(instrument, []))

    def tick(self) -> dict[str, Tick]:
        self._tick_count += 1
        self._regime_left -= 1
        if self._regime_left <= 0:
            self._regime = self._rng.choice([1, -1, 0])
            self._regime_left = self._rng.randint(25, 90)
        out: dict[str, Tick] = {}
        now = self.now()
        for name in list(self._prices):
            px = self._prices[name]
            drift = self._regime * self.volatility * px * 0.35
            shock = self._rng.gauss(0, self.volatility * px)
            px = max(1.0, px + drift + shock)
            self._prices[name] = px
            self._accumulate_bar(name, now, px)
            out[name] = Tick(ts=now, ltp=round(px, 2), bid=round(px - 0.05, 2),
                             ask=round(px + 0.05, 2))
        return out

    def _accumulate_bar(self, name: str, now: datetime, px: float) -> None:
        minute = now.replace(second=0, microsecond=0)
        cur = self._bar_open[name]
        if cur is None or cur.ts != minute:
            if cur is not None:
                self._bars[name].append(cur)
                if len(self._bars[name]) > 1500:
                    self._bars[name] = self._bars[name][-1500:]
            self._bar_open[name] = Bar(ts=minute, open=px, high=px, low=px,
                                       close=px, volume=1)
        else:
            cur.high = max(cur.high, px)
            cur.low = min(cur.low, px)
            cur.close = px
            cur.volume += 1

    def flush_open_bars(self) -> None:
        for name, b in self._bar_open.items():
            if b is not None:
                self._bars[name].append(b)
                self._bar_open[name] = None


class UpstoxWebsocketFeed:
    """Official websocket feed (verified flow) — production streaming path.

    Verified: authorize via upstox_client.WebsocketApi
    .get_market_data_feed_authorize('2.0') -> authorized_redirect_uri;
    subscribe JSON {"guid","method":"sub","data":{"mode","instrumentKeys"}};
    frames are protobuf FeedResponse.

    UNKNOWN until the official MarketDataFeed proto is compiled to
    MarketDataFeed_pb2 (see README) — decode_protobuf raises until then.
    """

    def __init__(self, access_token: str, instruments: dict[str, str],
                 mode: str = "ltpc") -> None:
        self.access_token = access_token
        self.instrument_keys = dict(instruments)
        self.mode = mode
        self._connected = False

    def authorize(self):
        try:
            import upstox_client
        except ImportError as e:
            raise RuntimeError(
                "upstox-python SDK not installed — pip install upstox-python") from e
        config = upstox_client.Configuration()
        config.access_token = self.access_token
        api = upstox_client.WebsocketApi(upstox_client.ApiClient(config))
        return api.get_market_data_feed_authorize("2.0")

    def subscription_payload(self) -> bytes:
        import json
        return json.dumps({
            "guid": "kalvex-pro",
            "method": "sub",
            "data": {"mode": self.mode,
                     "instrumentKeys": list(self.instrument_keys.values())},
        }).encode("utf-8")

    @staticmethod
    def decode_protobuf(frame: bytes) -> dict:
        try:
            import MarketDataFeed_pb2 as pb  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "UNKNOWN: MarketDataFeed_pb2 not available. Download the "
                "official MarketDataFeed proto from Upstox docs and compile: "
                "protoc --python_out=. MarketDataFeed.proto") from e
        from google.protobuf.json_format import MessageToDict
        msg = pb.FeedResponse()
        msg.ParseFromString(frame)
        return MessageToDict(msg)

    def connect(self, on_message) -> None:
        """Blocking websocket loop — run in a worker thread."""
        import asyncio

        try:
            import websockets
        except ImportError as e:
            raise RuntimeError("pip install websockets") from e

        async def _run() -> None:
            auth = self.authorize()
            uri = auth.data.authorized_redirect_uri
            async with websockets.connect(uri) as ws:
                await ws.send(self.subscription_payload())
                self._connected = True
                async for frame in ws:
                    on_message(self.decode_protobuf(frame))

        asyncio.run(_run())
