"""Transparent self-improvement loop.

This is NOT black-box ML and NOT a walk-forward optimizer (both are out of
scope per product spec). It is a rule-based review of the bot's own journal:

  * after every N completed trades per strategy, compute plain stats
    (win rate, expectancy, profit factor, max consecutive losses)
  * propose SMALL parameter adjustments strictly INSIDE hard-coded bands
    (TUNE_BANDS in strategies.py)
  * one hard safety rule is always-on: disable a strategy after
    MAX_CONSEC_LOSSES consecutive losses (needs manual re-arm)
  * every suggestion is stored with its rationale ('thought') and can be
    applied automatically only if the user enabled auto_tune

Risk ceilings are NEVER touched by this module.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from kalvex.core.models import Trade
from kalvex.core.strategies import TUNE_BANDS

MAX_CONSEC_LOSSES = 5          # hard safety rule
REVIEW_EVERY_N_TRADES = 5


@dataclass
class Review:
    strategy_key: str
    window: str
    stats: dict
    suggestion: dict
    thought: str
    apply: bool = False
    disable_strategy: bool = False


@dataclass
class StrategyStats:
    trades: list[Trade] = field(default_factory=list)

    def compute(self) -> dict:
        pnls = [t.pnl - t.fee for t in self.trades]
        n = len(pnls)
        if n == 0:
            return {"n": 0}
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        max_consec = cur = 0
        for p in pnls:
            if p <= 0:
                cur += 1
                max_consec = max(max_consec, cur)
            else:
                cur = 0
        gross_win = sum(wins) if wins else 0.0
        gross_loss = abs(sum(losses)) if losses else 0.0
        return {
            "n": n,
            "win_rate": len(wins) / n,
            "expectancy": statistics.mean(pnls),
            "profit_factor": (gross_win / gross_loss) if gross_loss > 0 else float("inf"),
            "max_consec_losses": max_consec,
            "net_pnl": sum(pnls),
        }


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def review_strategy(strategy_key: str, params: dict, trades: list[Trade],
                    auto_tune: bool = False) -> Review:
    stats = StrategyStats(trades=list(trades[-40:])).compute()
    window = f"last {stats.get('n', 0)} trades"
    suggestion: dict = {}
    thought = ""
    disable = False

    if stats.get("n", 0) >= 3:
        if stats["max_consec_losses"] >= MAX_CONSEC_LOSSES:
            disable = True
            thought = (
                f"SAFETY STOP: {stats['max_consec_losses']} consecutive losses "
                f"({window}). Hard rule disables '{strategy_key}' — needs manual "
                f"re-arm after review. No auto parameter change applied."
            )
        elif stats["n"] >= REVIEW_EVERY_N_TRADES:
            bands = TUNE_BANDS.get(strategy_key, {})
            wr, exp = stats["win_rate"], stats["expectancy"]
            # Single transparent heuristic: shrink target RR when wins are rare
            # but average win is decent (cutting over-ambitious targets), widen
            # SL buffer when stop-outs dominate. All moves stay in-band.
            if "target_rr" in bands and "target_rr" in params:
                lo, hi = bands["target_rr"]
                cur = float(params["target_rr"])
                new_rr = cur
                if wr < 0.40 and exp < 0:
                    new_rr = _clamp(cur * 0.9, lo, hi)
                elif wr > 0.60 and exp > 0:
                    new_rr = _clamp(cur * 1.05, lo, hi)
                if abs(new_rr - cur) > 1e-9:
                    suggestion = {"target_rr": round(new_rr, 2)}
                    thought = (
                        f"Review {window}: win rate {wr:.0%}, expectancy "
                        f"₹{exp:,.0f}, profit factor {stats['profit_factor']:.2f}. "
                        f"Suggest target_rr {cur:.2f} -> {new_rr:.2f} "
                        f"(band {lo}-{hi}) because "
                        + ("losses dominate; trimming ambition." if new_rr < cur
                           else "edge is positive; letting winners run slightly.")
                    )
            if not thought:
                thought = (
                    f"Review {window}: win rate {wr:.0%}, expectancy ₹{exp:,.0f}, "
                    f"PF {stats['profit_factor']:.2f}. Stats inside normal band — "
                    f"no parameter change (stability preferred over churn)."
                )
    else:
        thought = f"Review {window}: not enough data yet (need {REVIEW_EVERY_N_TRADES})."

    return Review(
        strategy_key=strategy_key, window=window, stats=stats,
        suggestion=suggestion, thought=thought,
        apply=auto_tune and bool(suggestion) and not disable,
        disable_strategy=disable,
    )


def maybe_review(strategy_key: str, params: dict, trades: list[Trade],
                 since_last_review: int, auto_tune: bool) -> Review | None:
    if since_last_review < REVIEW_EVERY_N_TRADES:
        return None
    return review_strategy(strategy_key, params, trades, auto_tune)
