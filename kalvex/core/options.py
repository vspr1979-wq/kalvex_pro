"""Options helpers — v1: index options BUYING only.

Rules (from product spec):
  - strike picker: ATM or ATM ± N strikes OTM (width configurable)
  - current expiry first
  - lot sizing via risk engine (capital * risk% / (entry - SL)) and
    exchange lot size
  - forced max holding time + theta-aware time exit
  - IV & Greeks displayed only if the feed provides them — no invented
    pricing models (no Black-Scholes anywhere in this codebase)
"""

from __future__ import annotations

import math

from kalvex.core.instruments import InstrumentSpec, OptionRequest


def round_to_strike(spot: float, strike_step: float) -> float:
    if strike_step <= 0:
        return spot
    return round(spot / strike_step) * strike_step


def pick_strike(spot: float, spec: InstrumentSpec, side_bias: str,
                otm_width: int = 0, expiry: str = "current") -> OptionRequest:
    """Pick an ATM/OTM CE or PE. side_bias: 'CE' (bullish) or 'PE' (bearish).

    thought documents the pick for the decision journal.
    """
    atm = round_to_strike(spot, spec.strike_step)
    if side_bias == "CE":
        strike = atm + otm_width * spec.strike_step
        bias_txt = "bullish -> CE"
    else:
        strike = atm - otm_width * spec.strike_step
        bias_txt = "bearish -> PE"
    thought = (
        f"Options pick: spot {spot:,.2f} -> ATM {atm:,.0f}; {bias_txt}; "
        f"width {otm_width} strike(s) -> {strike:,.0f} {side_bias}, "
        f"expiry={expiry} (current first). Lot size {spec.lot_size} "
        f"(VERIFY exchange contract)."
    )
    return OptionRequest(
        underlying=spec.name, expiry=expiry, option_type=side_bias,
        strike=strike, side="BUY", lots=0, lot_size=spec.lot_size,
        thought=thought,
        meta={"atm": atm, "otm_width": otm_width, "spot": spot},
    )


def lots_for_risk(capital: float, risk_pct: float, entry: float, sl: float,
                  lot_size: int, max_lots: int) -> tuple[int, int, str]:
    """(lots, qty, thought) from capital * risk% / (entry - SL), rounded to
    whole lots, capped at max_lots."""
    per_unit = abs(entry - sl)
    if per_unit <= 0 or lot_size <= 0:
        return 0, 0, "Sizing rejected: invalid entry/SL/lot size."
    risk_rs = capital * risk_pct / 100.0
    raw_units = risk_rs / per_unit
    lots = math.floor(raw_units / lot_size)
    capped = min(lots, max_lots)
    qty = capped * lot_size
    thought = (
        f"Size: risk ₹{risk_rs:,.0f} = {risk_pct:.2f}% of ₹{capital:,.0f}; "
        f"per-unit risk ₹{per_unit:,.2f}; raw {raw_units:.1f} units -> "
        f"{lots} lot(s) x {lot_size} = {qty} qty"
        + (f" (capped to max_lots={max_lots})" if lots != capped else "")
    )
    return capped, qty, thought


def time_exit_due(opened_epoch: float, now_epoch: float,
                  max_hold_seconds: int) -> bool:
    """Theta-aware time exit: options positions are force-flattened after the
    configured max holding time (v1 makes no assumptions about theta decay
    magnitude — only elapsed time and feed-provided theta, if any)."""
    return max_hold_seconds > 0 and (now_epoch - opened_epoch) >= max_hold_seconds
