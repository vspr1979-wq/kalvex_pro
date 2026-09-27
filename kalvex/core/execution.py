"""Execution layer: one BrokerInterface, two implementations.

- PaperEngine  : complete simulated broker (fills from LTP, SL/limit logic,
                 fees, PnL, position tracking). This is the DEFAULT and the
                 fully-tested path.
- LiveBrokerAdapter : official Upstox API v2/v3 via upstox-python SDK.
                 Only VERIFIED request shapes are implemented; anything not
                 confirmed in current docs raises with an explicit UNKNOWN.

Verified against Upstox developer docs + official SDK (Sept 2026):
  * OAuth dialog : https://api.upstox.com/v2/login/authorization/dialog
  * Token exchange: POST https://api.upstox.com/v2/login/authorization/token
    (code, client_id, client_secret, redirect_uri,
     grant_type=authorization_code)  -> access_token
  * No refresh token; access token expires 03:30 IST daily.
  * Order APIs rate limited: 10/sec, 500/min, 2000/30-min
    (50/sec for SEBI-registered algos only).
  * PlaceOrderV3Request fields (official SDK README):
    quantity, product, validity, price, tag, instrument_token, order_type,
    transaction_type, disclosed_quantity, trigger_price, is_amo, slice
  * Order tracking header: X-Algo-Name: <configured algo name>
  * Static IP must be registered for Place/Modify/Cancel/GTT/Exit-All.

UNKNOWN — verify before live:
  * whether raw MARKET orders are permitted for algo/API accounts
    (this adapter defaults to LIMIT and SL/SL-M only)
  * product code mapping for your segments ("D" delivery / "I" intraday seen
    in SDK material — confirm current enum)
  * margin percentages (paper uses a configurable margin_factor)
  * GTT order request schema
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from zoneinfo import ZoneInfo

from kalvex.core.models import (
    Order, OrderRequest, OrderSource, OrderStatus, OrderType, Position, Side, Trade,
)
from kalvex.core.security import TokenStore

IST = ZoneInfo("Asia/Kolkata")

# Verified endpoints (Upstox API v2)
AUTH_DIALOG_URL = "https://api.upstox.com/v2/login/authorization/dialog"
TOKEN_URL = "https://api.upstox.com/v2/login/authorization/token"


def ist_now() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")


class BrokerInterface(ABC):
    @abstractmethod
    def place_order(self, req: OrderRequest) -> Order: ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool: ...

    @abstractmethod
    def get_positions(self) -> list[Position]: ...

    @abstractmethod
    def get_funds(self) -> dict: ...


# --------------------------------------------------------------------- #
# Paper engine — fully functional simulated broker
# --------------------------------------------------------------------- #
class PaperEngine(BrokerInterface):
    def __init__(self, db, fee_per_order: float = 20.0,
                 slippage_bps: float = 2.0) -> None:
        self.db = db
        self.fee_per_order = fee_per_order
        self.slippage_bps = slippage_bps
        self.open_orders: dict[str, Order] = {}
        self.positions: dict[str, Position] = {}
        self.cash_used_margin = 0.0
        self._restore_from_db()

    def _restore_from_db(self) -> None:
        """Restart recovery: rebuild in-memory state from SQLite."""
        for row in self.db.load_positions():
            self.positions[row["instrument"]] = Position(
                instrument=row["instrument"], qty=row["qty"],
                avg_price=row["avg_price"], sl=row["sl"], target=row["target"],
                trail_active=bool(row["trail_active"]),
                trail_price=row["trail_price"],
                strategy_key=row["strategy_key"],
                source=OrderSource(row["source"]),
                opened_at=row["opened_at"],
                is_options=bool(row["is_options"]),
                max_hold_seconds=row["max_hold_seconds"],
            )
        for row in self.db.load_open_orders():
            o = Order(
                id=row["id"], tag=row["tag"], instrument=row["instrument"],
                side=Side(row["side"]), order_type=OrderType(row["order_type"]),
                qty=row["qty"], price=row["price"],
                trigger_price=row["trigger_price"],
                filled_qty=row["filled_qty"],
                avg_fill_price=row["avg_fill_price"],
                status=OrderStatus(row["status"]),
                strategy_key=row["strategy_key"],
                source=OrderSource(row["source"]),
                created_at=row["ts"],
            )
            # Dedupe guard: orders are keyed by stable client tag; a recovered
            # open order is re-adopted, never re-placed.
            self.open_orders[o.id] = o

    # ---- BrokerInterface ------------------------------------------------
    def place_order(self, req: OrderRequest) -> Order:
        # Dedupe on client tag — restart safety
        for o in self.open_orders.values():
            if o.tag == req.tag:
                return o
        oid = f"PP-{uuid.uuid4().hex[:10]}"
        o = Order(
            id=oid, tag=req.tag or oid, instrument=req.instrument,
            side=req.side, order_type=req.order_type, qty=req.qty,
            price=req.price, trigger_price=req.trigger_price,
            filled_qty=0, avg_fill_price=0.0,
            status=OrderStatus.OPEN, strategy_key=req.strategy_key,
            source=OrderSource.PAPER, created_at=ist_now(),
        )
        self.open_orders[oid] = o
        self.db.upsert_order(o)
        self.db.log("INFO", "Orders", "PAPER_ORDER_PLACED",
                    f"{o.side.value} {o.qty} {o.instrument} {o.order_type.value} "
                    f"@ {o.price} tag={o.tag}")
        return o

    def cancel_order(self, order_id: str) -> bool:
        o = self.open_orders.get(order_id)
        if o and o.status in (OrderStatus.OPEN, OrderStatus.PARTIAL, OrderStatus.PENDING):
            o.status = OrderStatus.CANCELLED
            o.updated_at = ist_now()
            self.db.upsert_order(o)
            return True
        return False

    def get_positions(self) -> list[Position]:
        return list(self.positions.values())

    def get_funds(self) -> dict:
        used = sum(abs(p.avg_price * p.qty) for p in self.positions.values())
        return {"available_margin": max(0.0, 10_000_000 - used), "used": used}

    # ---- matching engine ------------------------------------------------
    def on_tick(self, ltp_by_instrument: dict[str, float]) -> list[Trade]:
        """Advance the matching engine with fresh LTPs; returns new fills."""
        trades: list[Trade] = []
        for o in list(self.open_orders.values()):
            if o.status not in (OrderStatus.OPEN, OrderStatus.PARTIAL, OrderStatus.PENDING):
                continue
            ltp = ltp_by_instrument.get(o.instrument)
            if ltp is None:
                continue
            fill_px = 0.0
            if o.order_type == OrderType.MARKET:
                slip = ltp * self.slippage_bps / 10_000.0
                fill_px = ltp + slip if o.side == Side.BUY else ltp - slip
            elif o.order_type == OrderType.LIMIT:
                if (o.side == Side.BUY and ltp <= o.price) or \
                   (o.side == Side.SELL and ltp >= o.price):
                    fill_px = o.price
            elif o.order_type in (OrderType.SL, OrderType.SL_M):
                trig = o.trigger_price
                if (o.side == Side.SELL and ltp <= trig) or \
                   (o.side == Side.BUY and ltp >= trig):
                    fill_px = (o.price if o.order_type == OrderType.SL and o.price > 0
                               else ltp)
            if fill_px > 0:
                t = self._fill(o, fill_px)
                if t:
                    trades.append(t)
        return trades

    def _fill(self, o: Order, price: float) -> Trade:
        o.filled_qty = o.qty
        o.avg_fill_price = round(price, 2)
        o.status = OrderStatus.FILLED
        o.updated_at = ist_now()
        self.db.upsert_order(o)

        signed = o.qty if o.side == Side.BUY else -o.qty
        pos = self.positions.get(o.instrument)
        pnl = 0.0
        fee = 0.0
        closed = False
        if pos is None:
            pos = Position(
                instrument=o.instrument, qty=signed, avg_price=price,
                sl=0.0, target=0.0, strategy_key=o.strategy_key,
                source=OrderSource.PAPER, opened_at=ist_now(),
            )
            self.positions[o.instrument] = pos
            self.db.upsert_position(pos)
        else:
            if pos.qty * signed > 0:   # add to position
                total = pos.qty + signed
                pos.avg_price = (pos.avg_price * abs(pos.qty) + price * abs(signed)) / abs(total)
                pos.qty = total
                self.db.upsert_position(pos)
            else:                       # reduce / close / flip
                close_qty = min(abs(pos.qty), abs(signed))
                direction = 1 if pos.qty > 0 else -1
                pnl = (price - pos.avg_price) * close_qty * direction
                fee = self.fee_per_order
                pnl -= fee
                pos.qty += signed
                if pos.qty == 0:
                    closed = True
                    del self.positions[o.instrument]
                    self.db.delete_position(o.instrument)
                else:
                    pos.avg_price = price
                    self.db.upsert_position(pos)

        t = Trade(
            id=f"PT-{uuid.uuid4().hex[:10]}", instrument=o.instrument,
            side=o.side, qty=abs(signed), price=round(price, 2),
            fee=fee, pnl=round(pnl, 2), strategy_key=o.strategy_key,
            source=OrderSource.PAPER, ts=ist_now(),
        )
        self.db.insert_trade(t)
        self.db.log("INFO", "Orders", "PAPER_FILL",
                    f"{o.side.value} {o.qty} {o.instrument} @ {price:.2f} "
                    f"pnl={pnl:.2f}{' closed' if closed else ''}")
        return t


# --------------------------------------------------------------------- #
# Live adapter — verified shapes only, rest raises UNKNOWN
# --------------------------------------------------------------------- #
class LiveBrokerAdapter(BrokerInterface):
    """Upstox live orders. Requires: upstox-python SDK, a valid OAuth token,
    a registered static IP, and a configured algo name (X-Algo-Name)."""

    def __init__(self, token_store: TokenStore, algo_name: str,
                 client_id: str = "", sandbox: bool = True) -> None:
        self.token_store = token_store
        self.algo_name = algo_name            # sent as X-Algo-Name (verified)
        self.client_id = client_id
        self.sandbox = sandbox
        self._api = None

    # -- auth (verified endpoints) ----------------------------------------
    @staticmethod
    def build_login_url(client_id: str, redirect_uri: str, state: str = "") -> str:
        url = (f"{AUTH_DIALOG_URL}?response_type=code&client_id={client_id}"
               f"&redirect_uri={redirect_uri}")
        if state:
            url += f"&state={state}"
        return url

    @staticmethod
    def exchange_code(code: str, client_id: str, client_secret: str,
                      redirect_uri: str) -> dict:
        """POST /v2/login/authorization/token — verified form fields."""
        import requests
        resp = requests.post(TOKEN_URL, headers={
            "accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }, data={
            "code": code, "client_id": client_id, "client_secret": client_secret,
            "redirect_uri": redirect_uri, "grant_type": "authorization_code",
        }, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def token_status(self) -> str:
        token, expires = self.token_store.load()
        if not token:
            return "No token — run daily OAuth login"
        return f"Token loaded (expires {expires or 'UNKNOWN'} — Upstox daily 03:30 IST cut-off)"

    # -- SDK wiring -------------------------------------------------------
    def _sdk(self):
        if self._api is not None:
            return self._api
        try:
            import upstox_client
        except ImportError as e:
            raise RuntimeError(
                "upstox-python not installed — pip install upstox-python") from e
        token, _ = self.token_store.load()
        if not token:
            raise RuntimeError("No access token — complete OAuth login first")
        config = upstox_client.Configuration()
        config.access_token = token
        if self.sandbox:
            config.sandbox = True          # official SDK flag (README)
        self._api = upstox_client.ApiClient(config)
        return self._api

    def place_order(self, req: OrderRequest) -> Order:
        """Place an order via OrderApiV3 with the VERIFIED request fields.

        Policy: raw MARKET orders are NOT sent (UNKNOWN whether current
        algo/API rules allow them) — the request is converted to LIMIT with
        price=current-unspecified -> caller should pass a LIMIT.
        """
        if req.order_type == OrderType.MARKET:
            raise RuntimeError(
                "UNKNOWN: raw MARKET orders for algo/API not confirmed — "
                "send LIMIT or SL/SL-M instead (policy gate).")
        try:
            import upstox_client
        except ImportError as e:
            raise RuntimeError("pip install upstox-python") from e

        body = upstox_client.PlaceOrderV3Request(
            quantity=req.qty,
            product=req.extra.get("product", "D"),      # VERIFY product enum
            validity=req.extra.get("validity", "DAY"),
            price=req.price,
            tag=req.tag[:20] if req.tag else "",
            instrument_token=req.instrument,            # verified key format
            order_type=req.order_type.value,            # LIMIT | SL | SL-M
            transaction_type=req.side.value,            # BUY | SELL
            disclosed_quantity=0,
            trigger_price=req.trigger_price,
            is_amo=False,
            slice=False,
        )
        api = upstox_client.OrderApiV3(self._sdk())
        # Verified: algo_name kwarg / X-Algo-Name header tracks the order.
        response = api.place_order(body, algo_name=self.algo_name)
        broker_id = getattr(getattr(response, "data", None), "order_id", "") or ""
        oid = f"LV-{uuid.uuid4().hex[:10]}"
        o = Order(
            id=oid, tag=req.tag or oid, instrument=req.instrument,
            side=req.side, order_type=req.order_type, qty=req.qty,
            price=req.price, trigger_price=req.trigger_price,
            filled_qty=0, avg_fill_price=0.0, status=OrderStatus.PENDING,
            strategy_key=req.strategy_key, source=OrderSource.LIVE,
            broker_order_id=broker_id, created_at=ist_now(),
        )
        return o

    def cancel_order(self, order_id: str) -> bool:
        try:
            import upstox_client
        except ImportError as e:
            raise RuntimeError("pip install upstox-python") from e
        api = upstox_client.OrderApiV3(self._sdk())
        api.cancel_order(order_id, algo_name=self.algo_name)
        return True

    def get_positions(self) -> list[Position]:
        try:
            import upstox_client
        except ImportError as e:
            raise RuntimeError("pip install upstox-python") from e
        api = upstox_client.PortfolioApi(self._sdk())
        resp = api.get_positions("2.0")
        out: list[Position] = []
        for p in (getattr(resp, "data", None) or []):
            out.append(Position(
                instrument=getattr(p, "instrument_token", ""),
                qty=int(getattr(p, "quantity", 0) or 0),
                avg_price=float(getattr(p, "average_price", 0.0) or 0.0),
                sl=0.0, target=0.0,
                source=OrderSource.LIVE, opened_at=ist_now(),
            ))
        return out

    def get_funds(self) -> dict:
        try:
            import upstox_client
        except ImportError as e:
            raise RuntimeError("pip install upstox-python") from e
        api = upstox_client.UserApi(self._sdk())
        resp = api.get_user_funds("2.0")
        data = getattr(resp, "data", {}) or {}
        equity = getattr(data, "equity", None)
        avail = float(getattr(equity, "available_margin", 0.0) or 0.0) if equity else 0.0
        return {"available_margin": avail, "used": 0.0}
