"""Instrument registry: lot sizes, strike steps, segments.

IMPORTANT: lot sizes / strike steps are exchange facts that change over
time. Values below are USER-EDITABLE CONFIGURATION with placeholder
defaults — verify against the current exchange contract master or the
Upstox instrument dump before any live use (README checklist).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class InstrumentSpec:
    name: str                     # display name, e.g. "NIFTY 50"
    key: str                      # Upstox instrument_key when known, e.g.
                                  # "NSE_INDEX|Nifty 50" (format verified);
                                  # exact key strings must come from the
                                  # instrument master — UNKNOWN until fetched.
    segment: str                  # "IDX" | "EQ" | "FUT" | "OPT"
    lot_size: int = 1             # VERIFY current exchange lot size
    strike_step: float = 0.0      # options only — VERIFY
    tick_size: float = 0.05       # VERIFY
    base_price: float = 100.0     # sim starting price only
    is_index: bool = False
    notes: str = "PLACEHOLDER DEFAULTS — VERIFY BEFORE LIVE"


# Paper/sim defaults. Editable in Settings; nothing here is sent to a broker
# without explicit live opt-in.
DEFAULT_BOOK: dict[str, InstrumentSpec] = {
    "NIFTY 50": InstrumentSpec(
        name="NIFTY 50", key="NSE_INDEX|Nifty 50", segment="IDX",
        lot_size=75, strike_step=50.0, tick_size=0.05,
        base_price=24800.0, is_index=True),
    "BANK NIFTY": InstrumentSpec(
        name="BANK NIFTY", key="NSE_INDEX|Nifty Bank", segment="IDX",
        lot_size=35, strike_step=100.0, tick_size=0.05,
        base_price=52100.0, is_index=True),
    "NIFTY FUT": InstrumentSpec(
        name="NIFTY FUT", key="", segment="FUT",
        lot_size=75, strike_step=50.0, tick_size=0.05,
        base_price=24820.0),
    "RELIANCE": InstrumentSpec(
        name="RELIANCE", key="NSE_EQ|INE002A01018", segment="EQ",
        lot_size=1, strike_step=0.0, tick_size=0.05, base_price=2900.0),
}


@dataclass
class OptionRequest:
    """Result of the v1 options strike picker (index options buying only)."""

    underlying: str
    expiry: str            # "current" expiry label from user config
    option_type: str       # "CE" | "PE"
    strike: float
    side: str              # always "BUY" in v1
    lots: int
    lot_size: int
    thought: str = ""
    meta: dict = field(default_factory=dict)
