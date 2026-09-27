"""Options helpers — v1: index options BUYING only, data from Upstox.

Rules (from product spec):
  - underlying universe: NIFTY / SENSEX / BANKNIFTY / FINNIFTY / MIDCAPNIFTY
  - strike picker: ATM or ATM ± N strikes OTM, chosen from the LIVE option
    contract list (GET /v2/option/contract) — lot size, strike step, freeze
    quantity and instrument_key all come from the exchange rows
  - current expiry first (expiry list from contracts / instrument master)
  - qty from capital * risk% / (entry - SL) rounded to the contract lot size
  - forced max holding time (theta-aware time exit)
  - IV & Greeks displayed only if the option chain provides them —
    no invented pricing models (no Black-Scholes anywhere)
"""

from __future__ import annotations

import math

from kalvex.core.upstox_api import OptionContract


def pick_strike_from_contracts(contracts: list[OptionContract], spot: float,
                               side_bias: str, otm_width: int = 0,
                               ) -> tuple[OptionContract | None, str]:
    """Choose a CE or PE contract. side_bias: 'CE' (bullish) or 'PE'.

    ATM = strike closest to spot; OTM width walks further out of the money
    (CE: strikes above spot, PE: strikes below). Returns (contract, thought).
    """
    want_type = side_bias if side_bias in ("CE", "PE") else "CE"
    rows = [c for c in contracts
            if c.instrument_type == want_type and c.strike_price > 0]
    if not rows:
        return None, (f"NO CONTRACT: no {want_type} rows in the Upstox "
                      f"contract list for this expiry — cannot trade.")
    rows.sort(key=lambda c: c.strike_price)

    # ATM index: first strike >= spot, then step toward the money
    atm_idx = 0
    for i, c in enumerate(rows):
        if c.strike_price >= spot:
            atm_idx = i
            break
    else:
        atm_idx = len(rows) - 1
    # refine: whichever neighbour is closer to spot
    if atm_idx > 0 and abs(rows[atm_idx - 1].strike_price - spot) < \
            abs(rows[atm_idx].strike_price - spot):
        atm_idx -= 1

    if want_type == "CE":
        idx = min(len(rows) - 1, atm_idx + otm_width)   # CE OTM = higher strikes
    else:
        idx = max(0, atm_idx - otm_width)               # PE OTM = lower strikes

    chosen = rows[idx]
    atm = rows[atm_idx].strike_price
    direction = "OTM" if idx != atm_idx else "ATM"
    thought = (
        f"Options pick (Upstox contracts): spot {spot:,.2f} -> ATM {atm:,.0f}; "
        f"bias {want_type}; width {otm_width} -> {chosen.strike_price:,.0f} "
        f"{want_type} ({direction}); symbol {chosen.trading_symbol}; "
        f"expiry {chosen.expiry} (current first); lot size {chosen.lot_size} "
        f"(exchange row); freeze qty {chosen.freeze_quantity}."
    )
    return chosen, thought


def lots_for_risk(capital: float, risk_pct: float, entry: float, sl: float,
                  lot_size: int, max_lots: int) -> tuple[int, int, str]:
    """(lots, qty, thought) from capital * risk% / (entry - SL), rounded to
    whole lots, capped at max_lots. lot_size MUST come from the exchange
    contract row."""
    per_unit = abs(entry - sl)
    if per_unit <= 0 or lot_size <= 0:
        return 0, 0, ("Sizing rejected: invalid entry/SL/lot size "
                      f"(lot_size={lot_size} must come from the exchange row).")
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
