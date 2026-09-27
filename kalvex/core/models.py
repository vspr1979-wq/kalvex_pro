"""Domain models shared across the engine and UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    # Per Upstox SDK: LIMIT / SL / SL-M. Raw MARKET kept but policy-gated
    # (verify current algo/API rules before enabling for live).
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    SL = "SL"          # stop-loss limit
    SL_M = "SL-M"      # stop-loss market


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    FILLED = "FILLED"
    PARTIAL = "PARTIAL"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class OrderSource(str, Enum):
    PAPER = "PAPER"
    LIVE = "LIVE"


class BotMode(str, Enum):
    PAPER = "Paper"
    SEMI_AUTO = "Semi-auto"
    AUTO = "Auto"


class BotState(str, Enum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    FLATTENING = "FLATTENING"
    KILLED = "KILLED"


class Stage(str, Enum):
    """Pipeline stages of the bot's decision loop — the 'thought process'."""

    ANALYSE = "ANALYSE"
    DECIDE = "DECIDE"
    SIZE = "SIZE"
    EXECUTE = "EXECUTE"
    MANAGE = "MANAGE"
    REVIEW = "REVIEW"
    RISK = "RISK"
    SYSTEM = "SYSTEM"


@dataclass
class Bar:
    ts: datetime            # bar open time (IST)
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass
class Tick:
    ts: datetime
    ltp: float
    bid: float = 0.0
    ask: float = 0.0
    # Option-only fields — passthrough when the feed provides them
    # (option_greeks mode). Never synthesised.
    iv: float | None = None
    delta: float | None = None
    theta: float | None = None


@dataclass
class Signal:
    """A strategy decision, with its full transparent reasoning chain."""

    strategy_key: str
    instrument: str
    side: Side
    entry: float
    sl: float
    target: float
    confidence: float                 # 0..1, from explicit rule confluence
    reasons: list[str] = field(default_factory=list)
    thought: str = ""                 # human-readable reasoning, shown in UI
    is_options: bool = False
    option_meta: dict | None = None   # strike/expiry/type once picked
    created_at: datetime | None = None

    @property
    def risk_per_unit(self) -> float:
        return abs(self.entry - self.sl)


@dataclass
class OrderRequest:
    instrument: str
    side: Side
    order_type: OrderType
    qty: int
    price: float = 0.0
    trigger_price: float = 0.0
    strategy_key: str = ""
    source: OrderSource = OrderSource.PAPER
    tag: str = ""            # client order id — dedupe key on recovery
    extra: dict = field(default_factory=dict)


@dataclass
class Order:
    id: str
    tag: str
    instrument: str
    side: Side
    order_type: OrderType
    qty: int
    price: float
    trigger_price: float
    filled_qty: int
    avg_fill_price: float
    status: OrderStatus
    strategy_key: str
    source: OrderSource
    broker_order_id: str = ""
    created_at: str = ""
    updated_at: str = ""
    message: str = ""


@dataclass
class Position:
    instrument: str
    qty: int                       # signed: + long, - short
    avg_price: float
    sl: float
    target: float
    trail_active: bool = False
    trail_price: float = 0.0
    strategy_key: str = ""
    source: OrderSource = OrderSource.PAPER
    opened_at: str = ""
    is_options: bool = False
    option_meta: dict | None = None
    max_hold_seconds: int = 0      # theta-aware time exit (options)

    @property
    def side(self) -> Side:
        return Side.BUY if self.qty > 0 else Side.SELL

    def unrealised(self, ltp: float) -> float:
        return (ltp - self.avg_price) * self.qty


@dataclass
class Trade:
    id: str
    instrument: str
    side: Side
    qty: int
    price: float
    fee: float
    pnl: float
    strategy_key: str
    source: OrderSource
    ts: str = ""


@dataclass
class DecisionEvent:
    """One step of the bot's thought process, for the journal + UI stream."""

    cycle_id: str
    stage: Stage
    strategy_key: str
    thought: str
    data: dict = field(default_factory=dict)
    ts: str = ""
