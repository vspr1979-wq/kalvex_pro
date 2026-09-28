"""Domain models shared by data, research, backtest, and execution layers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True)
class Instrument:
    instrument_key: str
    exchange: str
    segment: str
    instrument_type: str
    trading_symbol: str = ""
    name: str = ""
    underlying_key: str = ""
    underlying_symbol: str = ""
    expiry: date | None = None
    strike_price: float | None = None
    option_type: str | None = None
    lot_size: int = 1
    freeze_quantity: int | None = None
    tick_size: float = 0.05

    @property
    def is_option(self) -> bool:
        return self.instrument_type.upper() in {"OPTIDX", "OPTSTK"} or self.option_type in {"CE", "PE"}

    @property
    def is_fno_stock_option(self) -> bool:
        return self.instrument_type.upper() == "OPTSTK"

    @property
    def is_index_option(self) -> bool:
        return self.instrument_type.upper() == "OPTIDX"

    @classmethod
    def from_upstox(cls, raw: dict[str, Any]) -> "Instrument":
        key = str(raw.get("instrument_key") or raw.get("instrumentKey") or "")
        exchange = str(raw.get("exchange") or key.split("_", 1)[0]).upper()
        expiry_raw = raw.get("expiry")
        parsed_expiry: date | None = None
        if expiry_raw:
            if isinstance(expiry_raw, (int, float)):
                parsed_expiry = datetime.fromtimestamp(expiry_raw / 1000).date()
            else:
                parsed_expiry = date.fromisoformat(str(expiry_raw)[:10])
        option_type = raw.get("option_type") or raw.get("optionType")
        if option_type:
            option_type = str(option_type).upper()
        return cls(
            instrument_key=key,
            exchange=exchange,
            segment=str(raw.get("segment") or "").upper(),
            instrument_type=str(raw.get("instrument_type") or raw.get("instrumentType") or "").upper(),
            trading_symbol=str(raw.get("trading_symbol") or raw.get("tradingSymbol") or ""),
            name=str(raw.get("name") or raw.get("short_name") or raw.get("shortName") or ""),
            underlying_key=str(raw.get("underlying_key") or raw.get("underlyingKey") or ""),
            underlying_symbol=str(raw.get("underlying_symbol") or raw.get("underlyingSymbol") or ""),
            expiry=parsed_expiry,
            strike_price=_number(raw.get("strike_price", raw.get("strikePrice"))),
            option_type=option_type,
            lot_size=int(raw.get("lot_size") or raw.get("lotSize") or raw.get("minimum_lot") or 1),
            freeze_quantity=_int_or_none(raw.get("freeze_quantity") or raw.get("freezeQuantity")),
            tick_size=float(raw.get("tick_size") or raw.get("tickSize") or 0.05),
        )


@dataclass(frozen=True)
class Candle:
    timestamp: datetime
    instrument_key: str
    open: float
    high: float
    low: float
    close: float
    volume: int = 0
    open_interest: int = 0


@dataclass(frozen=True)
class OptionQuote:
    timestamp: datetime
    instrument_key: str
    ltp: float
    bid: float | None = None
    ask: float | None = None
    bid_quantity: int = 0
    ask_quantity: int = 0
    volume: int = 0
    open_interest: int = 0
    implied_volatility: float | None = None
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None

    @property
    def spread_bps(self) -> float | None:
        if self.bid is None or self.ask is None or self.ltp <= 0 or self.ask < self.bid:
            return None
        return (self.ask - self.bid) / self.ltp * 10_000


@dataclass(frozen=True)
class LongOptionSignal:
    timestamp: datetime
    instrument_key: str
    expected_return: float
    confidence: float
    holding_minutes: int
    stop_loss_fraction: float = 0.35
    take_profit_fraction: float = 0.50
    lots: int = 1


@dataclass(frozen=True)
class Trade:
    instrument_key: str
    entry_time: datetime
    exit_time: datetime
    quantity: int
    entry_price: float
    exit_price: float
    gross_pnl: float
    fees: float
    net_pnl: float
    exit_reason: str


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)
