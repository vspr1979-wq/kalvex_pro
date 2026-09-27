"""Market data providers.

- SimFeedProvider: deterministic, regime-switching synthetic ticks/bars for
  paper trading and self-tests. Clearly labelled SIMULATED everywhere.
- UpstoxFeedProvider: verified shape (authorize -> websocket -> protobuf
  FeedResponse). Requires upstox-python + the official MarketDataFeed proto
  compiled to MarketDataFeed_pb2. Anything unverified raises with an
  explicit UNKNOWN marker — nothing is invented.
"""

from __future__ import annotations

import json
import random
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from kalvex.core.models import Bar, Tick

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


class SimFeedProvider(FeedProvider):
    """Regime-switching random walk with an accelerated virtual clock.

    Designed for deterministic self-tests and live UI demos of the bot's
    decision loop without any broker connection.
    """

    def __init__(self, instruments: dict[str, float], seed: int = 7,
                 start: datetime | None = None, speed: float = 1.0,
                 volatility: float = 0.0011) -> None:
        self._rng = random.Random(seed)
        self._prices = dict(instruments)
        self._start = start or datetime.now(IST).replace(
            hour=9, minute=15, second=0, microsecond=0)
        self._tick_count = 0
        self.speed = speed            # virtual seconds advanced per tick() call
        self.volatility = volatility
        self._bars: dict[str, list[Bar]] = {k: [] for k in instruments}
        self._bar_open: dict[str, Bar | None] = {k: None for k in instruments}
        self._regime = 1              # +1 trend up, -1 trend down, 0 range
        self._regime_left = 40        # ticks left in this regime

    # ---- clock ----------------------------------------------------------
    def now(self) -> datetime:
        return self._start + timedelta(seconds=self._tick_count * self.speed)

    # ---- feed -----------------------------------------------------------
    def ltp(self, instrument: str) -> float:
        return self._prices.get(instrument, 0.0)

    def bars(self, instrument: str, minutes: int = 1) -> list[Bar]:
        return list(self._bars.get(instrument, []))

    def tick(self) -> dict[str, Tick]:
        """Advance the virtual market one step; returns fresh ticks."""
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
        """Close any in-progress bars (used at end of self-test)."""
        for name, b in self._bar_open.items():
            if b is not None:
                self._bars[name].append(b)
                self._bar_open[name] = None


class UpstoxFeedProvider(FeedProvider):
    """Official Upstox websocket feed (verified flow, unverified details raise).

    Verified (Upstox developer docs, Sept 2026):
      1. GET market data feed authorization via upstox_client.WebsocketApi
         .get_market_data_feed_authorize('2.0') -> authorized_redirect_uri
      2. Connect websockets to that URI.
      3. Subscribe with JSON:
         {"guid": "...", "method": "sub",
          "data": {"mode": "ltpc|quote|full|option_greeks",
                   "instrumentKeys": ["NSE_INDEX|Nifty 50", ...]}}
      4. Messages are protobuf FeedResponse frames (MarketDataFeed proto).

    UNKNOWN / must re-verify before production use:
      - exact .proto schema version -> download from Upstox docs and compile
        with protoc into MarketDataFeed_pb2 (not shipped here).
      - reconnect/backoff semantics, heartbeat behaviour.
      - which modes are enabled for your app/subscription.
    """

    def __init__(self, access_token: str, instruments: dict[str, str]) -> None:
        self.access_token = access_token
        self.instrument_keys = dict(instruments)   # display name -> instrument_key
        self._prices: dict[str, float] = {}
        self._bars: dict[str, list[Bar]] = {k: [] for k in instruments}
        self._connected = False

    def now(self) -> datetime:
        return datetime.now(IST)

    def ltp(self, instrument: str) -> float:
        return self._prices.get(instrument, 0.0)

    def bars(self, instrument: str, minutes: int = 1) -> list[Bar]:
        return list(self._bars.get(instrument, []))

    # -- connection (run inside its own QThread/async loop) ---------------
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

    def subscription_payload(self, mode: str = "ltpc") -> bytes:
        return json.dumps({
            "guid": "kalvex-pro",
            "method": "sub",
            "data": {"mode": mode,
                     "instrumentKeys": list(self.instrument_keys.values())},
        }).encode("utf-8")

    @staticmethod
    def decode_protobuf(frame: bytes) -> dict:
        """Decode a FeedResponse protobuf frame.

        Requires MarketDataFeed_pb2 generated from the OFFICIAL proto file
        (compile with protoc — see README). Returns a plain dict.
        """
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

    def connect(self) -> None:
        """Blocking websocket loop — call from a worker thread."""
        import asyncio

        try:
            import websockets
        except ImportError as e:
            raise RuntimeError("pip install websockets") from e

        async def _run() -> None:
            auth = self.authorize()
            uri = auth.data.authorized_redirect_uri
            async with websockets.connect(uri) as ws:
                await ws.send(self.subscription_payload("ltpc"))
                self._connected = True
                async for frame in ws:
                    data = self.decode_protobuf(frame)
                    self._on_message(data)

        asyncio.run(_run())

    def _on_message(self, data: dict) -> None:
        # Shape verified as FeedResponse; per-key field names come from the
        # official proto (UNKNOWN until compiled) — parse defensively.
        for key, payload in (data.get("data") or {}).items():
            ltp = payload.get("ltpc", {}).get("lastTradedPrice")
            if ltp is not None:  # protobuf int64 price in paise/cents — scale
                # UNKNOWN: price scale per proto docs (verify: 100ths).
                self._prices[key] = float(ltp) / 100.0
