"""Small, dependency-free configuration helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import tomllib


@dataclass(frozen=True)
class MarketConfig:
    exchanges: tuple[str, ...] = ("NSE", "BSE")
    index_underlyings: tuple[str, ...] = (
        "nifty",
        "sensex",
        "banknifty",
        "finnifty",
        "midcapnifty",
    )
    include_fno_stocks: bool = True
    option_types: tuple[str, ...] = ("CE", "PE")


@dataclass(frozen=True)
class ContractFilterConfig:
    minimum_volume: int = 0
    minimum_open_interest: int = 0
    maximum_spread_bps: float = 150.0
    minimum_delta_abs: float = 0.25
    maximum_delta_abs: float = 0.75
    max_strikes_from_atm: int = 5


@dataclass(frozen=True)
class ResearchConfig:
    bar_interval: str = "5minute"
    underlying_bar_unit: str = "minutes"
    underlying_bar_interval: int = 5
    train_days: int = 504
    validation_days: int = 126
    test_days: int = 126
    walk_forward: bool = True
    exclude_expiry_day: bool = True
    minimum_days_to_expiry: int = 1
    maximum_days_to_expiry: int = 30


@dataclass(frozen=True)
class RiskConfig:
    long_options_only: bool = True
    max_open_positions: int = 1
    max_lots_per_trade: int = 1
    risk_per_trade_fraction: float = 0.005
    max_daily_loss_fraction: float = 0.02
    max_consecutive_losses: int = 3
    no_averaging_down: bool = True
    force_square_off_time: str = "15:15:00+05:30"
    last_entry_time: str = "14:45:00+05:30"


@dataclass(frozen=True)
class BacktestConfig:
    entry_fill: str = "ask_plus_slippage"
    exit_fill: str = "bid_minus_slippage"
    slippage_bps: float = 20.0
    fee_fraction_of_premium: float = 0.001
    initial_capital: float = 100_000.0
    max_holding_minutes: int = 90


@dataclass(frozen=True)
class ExecutionConfig:
    mode: str = "shadow"
    allow_order_placement: bool = False
    require_manual_promotion: bool = True
    require_static_ip_check: bool = True
    algo_name: str = "KALVEX_LONG_OPTIONS"


@dataclass(frozen=True)
class AppConfig:
    market: MarketConfig = field(default_factory=MarketConfig)
    research: ResearchConfig = field(default_factory=ResearchConfig)
    contract_filter: ContractFilterConfig = field(default_factory=ContractFilterConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)

    def validate(self) -> None:
        if not self.market.exchanges:
            raise ValueError("At least one exchange is required")
        if not set(self.market.exchanges).issubset({"NSE", "BSE"}):
            raise ValueError("Only NSE and BSE are supported")
        if set(self.market.option_types) != {"CE", "PE"}:
            raise ValueError("The first release supports CE and PE buying only")
        if not self.risk.long_options_only:
            raise ValueError("Short options are disabled")
        if self.execution.mode not in {"research", "shadow", "paper", "live"}:
            raise ValueError("execution.mode must be research, shadow, paper, or live")
        if self.execution.mode == "live" and not self.execution.allow_order_placement:
            raise ValueError("Live mode requires explicit allow_order_placement=true")
        if self.risk.max_open_positions < 1 or self.risk.max_lots_per_trade < 1:
            raise ValueError("Position and lot limits must be positive")
        if not 0 < self.risk.risk_per_trade_fraction <= 1:
            raise ValueError("risk_per_trade_fraction must be between 0 and 1")
        if self.research.minimum_days_to_expiry < 0:
            raise ValueError("minimum_days_to_expiry cannot be negative")
        if self.research.maximum_days_to_expiry < self.research.minimum_days_to_expiry:
            raise ValueError("maximum_days_to_expiry must be >= minimum_days_to_expiry")


def _tuple(value: Any, default: tuple[str, ...]) -> tuple[str, ...]:
    if value is None:
        return default
    return tuple(str(item).upper() for item in value)


def load_config(path: str | Path) -> AppConfig:
    """Load and validate a TOML configuration file."""
    with Path(path).open("rb") as handle:
        raw = tomllib.load(handle)
    market = raw.get("market", {})
    research = raw.get("research", {})
    contract = raw.get("contract_filter", {})
    risk = raw.get("risk", {})
    backtest = raw.get("backtest", {})
    execution = raw.get("execution", {})
    config = AppConfig(
        market=MarketConfig(
            exchanges=_tuple(market.get("exchanges"), ("NSE", "BSE")),
            index_underlyings=_tuple(market.get("index_underlyings"), MarketConfig().index_underlyings),
            include_fno_stocks=bool(market.get("include_fno_stocks", True)),
            option_types=_tuple(market.get("option_types"), ("CE", "PE")),
        ),
        research=ResearchConfig(**{k: v for k, v in research.items() if k in ResearchConfig.__dataclass_fields__}),
        contract_filter=ContractFilterConfig(**{k: v for k, v in contract.items() if k in ContractFilterConfig.__dataclass_fields__}),
        risk=RiskConfig(**{k: v for k, v in risk.items() if k in RiskConfig.__dataclass_fields__}),
        backtest=BacktestConfig(**{k: v for k, v in backtest.items() if k in BacktestConfig.__dataclass_fields__}),
        execution=ExecutionConfig(**{k: v for k, v in execution.items() if k in ExecutionConfig.__dataclass_fields__}),
    )
    config.validate()
    return config
