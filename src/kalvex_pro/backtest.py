"""Conservative long-options-only intraday backtest primitives."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Sequence

from .models import LongOptionSignal, OptionQuote, Trade


@dataclass(frozen=True)
class BacktestSettings:
    initial_capital: float = 100_000.0
    slippage_bps: float = 20.0
    fee_fraction_of_premium: float = 0.001
    max_holding_minutes: int = 90
    max_open_positions: int = 1


@dataclass(frozen=True)
class BacktestResult:
    trades: tuple[Trade, ...]
    ending_capital: float
    max_drawdown: float

    @property
    def net_pnl(self) -> float:
        return sum(trade.net_pnl for trade in self.trades)

    @property
    def win_rate(self) -> float:
        return sum(trade.net_pnl > 0 for trade in self.trades) / len(self.trades) if self.trades else 0.0


class LongOptionsBacktester:
    """One-position-at-a-time simulator using ask for buys and bid for exits.

    This deliberately refuses to use candle highs/lows as executable prices. A
    quote history with bid/ask is required for trustworthy options results.
    """

    def __init__(self, settings: BacktestSettings = BacktestSettings()):
        self.settings = settings

    def run(self, signals: Iterable[LongOptionSignal], quotes: Iterable[OptionQuote], lot_sizes: dict[str, int]) -> BacktestResult:
        by_instrument: dict[str, list[OptionQuote]] = {}
        for quote in quotes:
            by_instrument.setdefault(quote.instrument_key, []).append(quote)
        for rows in by_instrument.values():
            rows.sort(key=lambda item: item.timestamp)

        trades: list[Trade] = []
        active_until: list[datetime] = []
        for signal in sorted(signals, key=lambda item: item.timestamp):
            active_until = [timestamp for timestamp in active_until if timestamp > signal.timestamp]
            if len(active_until) >= self.settings.max_open_positions:
                continue
            rows = by_instrument.get(signal.instrument_key, [])
            entry = next((row for row in rows if row.timestamp >= signal.timestamp), None)
            if entry is None or entry.ask is None or entry.ask <= 0:
                continue
            quantity = max(1, signal.lots) * max(1, lot_sizes.get(signal.instrument_key, 1))
            entry_price = _buy_price(entry.ask, self.settings.slippage_bps)
            stop = entry_price * (1 - signal.stop_loss_fraction)
            target = entry_price * (1 + signal.take_profit_fraction)
            deadline = entry.timestamp.timestamp() + min(signal.holding_minutes, self.settings.max_holding_minutes) * 60
            exit_quote = None
            exit_reason = "time_exit"
            for quote in rows:
                if quote.timestamp <= entry.timestamp:
                    continue
                if quote.timestamp.timestamp() > deadline:
                    break
                reference = quote.bid if quote.bid is not None else quote.ltp
                if reference <= stop:
                    exit_quote, exit_reason = quote, "stop_loss"
                    break
                if reference >= target:
                    exit_quote, exit_reason = quote, "take_profit"
                    break
            if exit_quote is None:
                exit_quote = next((row for row in rows if row.timestamp.timestamp() >= deadline), rows[-1] if rows else None)
            if exit_quote is None:
                continue
            raw_exit = exit_quote.bid if exit_quote.bid is not None else exit_quote.ltp
            if raw_exit <= 0:
                continue
            exit_price = _sell_price(raw_exit, self.settings.slippage_bps)
            gross = (exit_price - entry_price) * quantity
            fees = (entry_price + exit_price) * quantity * self.settings.fee_fraction_of_premium
            trades.append(
                Trade(
                    instrument_key=signal.instrument_key,
                    entry_time=entry.timestamp,
                    exit_time=exit_quote.timestamp,
                    quantity=quantity,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    gross_pnl=gross,
                    fees=fees,
                    net_pnl=gross - fees,
                    exit_reason=exit_reason,
                )
            )
        return BacktestResult(tuple(trades), self.settings.initial_capital + sum(item.net_pnl for item in trades), _max_drawdown(self.settings.initial_capital, trades))


def _buy_price(price: float, slippage_bps: float) -> float:
    return price * (1 + slippage_bps / 10_000)


def _sell_price(price: float, slippage_bps: float) -> float:
    return max(0.0, price * (1 - slippage_bps / 10_000))


def _max_drawdown(start: float, trades: Sequence[Trade]) -> float:
    equity = peak = start
    worst = 0.0
    for trade in trades:
        equity += trade.net_pnl
        peak = max(peak, equity)
        if peak:
            worst = min(worst, (equity - peak) / peak)
    return abs(worst)
