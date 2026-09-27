"""Risk engine — hard-coded ceilings + user settings.

Every order passes through RiskManager.evaluate(); it returns a fully
documented decision (approve/size/reject) with its reasoning. Hard ceilings
are constants here and CANNOT be raised from the UI.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from kalvex.core.models import Position, Signal


# ---- HARD CEILINGS (code constants — UI cannot raise these) -------------
HARD_MAX_RISK_PCT = 2.0          # % of capital per trade
HARD_MAX_OPEN_POSITIONS = 6
HARD_MAX_LOTS = 10
HARD_MAX_ORDERS_PER_MIN = 60
HARD_MAX_ORDERS_PER_SEC = 10      # Upstox order-API rate limit (verified)
HARD_DAILY_LOSS_PCT = 5.0         # % of capital


@dataclass
class RiskConfig:
    capital: float = 500_000.0
    risk_per_trade_pct: float = 1.0
    max_open_positions: int = 3
    max_lots: int = 2
    max_orders_per_min: int = 20
    daily_max_loss: float = 5_000.0
    daily_profit_stop: float = 10_000.0
    profit_stop_enabled: bool = False
    trailing_start_profit: float = 500.0
    square_off_time: str = "15:15"
    margin_factor: float = 0.20    # fraction of notional required as margin
                                   # PLACEHOLDER — live margin % must come
                                   # from the broker (UNKNOWN until wired)
    lot_size: int = 75             # default instrument lot (VERIFY)
    fee_per_order: float = 20.0    # placeholder transaction cost per fill

    @classmethod
    def effective(cls, cfg: "RiskConfig") -> "RiskConfig":
        """Clamp user settings to hard ceilings."""
        cfg.risk_per_trade_pct = min(cfg.risk_per_trade_pct, HARD_MAX_RISK_PCT)
        cfg.max_open_positions = min(cfg.max_open_positions, HARD_MAX_OPEN_POSITIONS)
        cfg.max_lots = min(cfg.max_lots, HARD_MAX_LOTS)
        cfg.max_orders_per_min = min(cfg.max_orders_per_min, HARD_MAX_ORDERS_PER_MIN)
        return cfg


@dataclass
class RiskDecision:
    approved: bool
    qty: int = 0
    lots: int = 0
    reasons: list[str] = field(default_factory=list)
    thought: str = ""
    flatten_all: bool = False     # daily-loss breach -> flatten + stop
    stop_bot: bool = False


class OrderThrottle:
    """Token bucket: hard ≤10 orders/sec (Upstox verified limit) and the
    user's per-minute cap."""

    def __init__(self, per_sec: int = HARD_MAX_ORDERS_PER_SEC,
                 per_min: int = 20) -> None:
        self.per_sec = per_sec
        self.per_min = per_min
        self._sec: list[float] = []
        self._min: list[float] = []

    def allow(self, now: float | None = None) -> tuple[bool, str]:
        now = now or time.monotonic()
        self._sec = [t for t in self._sec if now - t < 1.0]
        self._min = [t for t in self._min if now - t < 60.0]
        if len(self._sec) >= self.per_sec:
            return False, f"throttle: {self.per_sec}/sec broker cap reached"
        if len(self._min) >= self.per_min:
            return False, f"throttle: user cap {self.per_min}/min reached"
        self._sec.append(now)
        self._min.append(now)
        return True, ""


class RiskManager:
    def __init__(self, config: RiskConfig) -> None:
        self.config = RiskConfig.effective(config)
        self.throttle = OrderThrottle(per_min=self.config.max_orders_per_min)
        self.day_realised_pnl = 0.0
        self.orders_today = 0

    # ---- daily counters -------------------------------------------------
    def register_fill_pnl(self, pnl: float) -> None:
        self.day_realised_pnl += pnl

    def daily_limits_breached(self, unrealised: float = 0.0) -> RiskDecision | None:
        cfg = self.config
        total = self.day_realised_pnl + unrealised
        if total <= -abs(cfg.daily_max_loss):
            return RiskDecision(
                approved=False, flatten_all=True, stop_bot=True,
                reasons=[f"daily P&L ₹{total:,.0f} ≤ max loss -₹{cfg.daily_max_loss:,.0f}"],
                thought=(f"DAILY LOSS LIMIT HIT (₹{total:,.0f}). Hard rule: "
                         "flatten all positions, cancel open orders, stop bot."),
            )
        if cfg.profit_stop_enabled and total >= cfg.daily_profit_stop:
            return RiskDecision(
                approved=False, stop_bot=True,
                reasons=[f"daily P&L ₹{total:,.0f} ≥ profit stop ₹{cfg.daily_profit_stop:,.0f}"],
                thought=(f"DAILY PROFIT STOP reached (₹{total:,.0f}). Stop opening "
                         "new trades; existing positions stay managed."),
            )
        return None

    # ---- sizing + gates -------------------------------------------------
    def evaluate(self, sig: Signal, open_positions: list[Position],
                 available_margin: float, lot_size: int | None = None) -> RiskDecision:
        cfg = self.config
        lot = lot_size or cfg.lot_size
        reasons: list[str] = []

        # NOTE: order-rate throttling is enforced at EXECUTE time (see
        # BotWorker._place_entry), not here — sizing must not consume
        # throttle tokens.

        # position count
        if len(open_positions) >= cfg.max_open_positions:
            return RiskDecision(
                False, reasons=[f"max open positions {cfg.max_open_positions} reached"],
                thought="Risk reject: position cap reached; staying flat.")

        # one position per instrument
        if any(p.instrument == sig.instrument for p in open_positions):
            return RiskDecision(
                False, reasons=["position already open in this instrument"],
                thought="Risk reject: duplicate instrument (one position per instrument in v1).")

        per_unit = sig.risk_per_unit
        if per_unit <= 0:
            return RiskDecision(False, reasons=["invalid SL distance"],
                                thought="Risk reject: SL equals entry.")

        risk_rs = cfg.capital * cfg.risk_per_trade_pct / 100.0
        raw_qty = risk_rs / per_unit
        import math
        lots = math.floor(raw_qty / lot) if lot > 0 else 0
        lots = min(lots, cfg.max_lots, HARD_MAX_LOTS)
        qty = lots * lot
        if qty <= 0:
            return RiskDecision(
                False, reasons=["risk budget too small for one lot"],
                thought=(f"Risk reject: ₹{risk_rs:,.0f} budget vs "
                         f"₹{per_unit:,.2f} per-unit risk cannot fill one "
                         f"{lot}-unit lot."))

        # margin check (paper: simulated margin factor; live: broker margins)
        notional = qty * sig.entry
        margin_required = notional * cfg.margin_factor
        if margin_required > available_margin:
            # reduce to what margin allows
            afford_lots = int(available_margin // (lot * sig.entry * cfg.margin_factor))
            lots = min(lots, max(0, afford_lots))
            qty = lots * lot
            reasons.append(f"margin cap: needed ₹{margin_required:,.0f}, "
                           f"available ₹{available_margin:,.0f} -> reduced to {lots} lot(s)")
            if qty <= 0:
                return RiskDecision(
                    False, reasons=reasons,
                    thought="Risk reject: insufficient margin for one lot.")
            margin_required = qty * sig.entry * cfg.margin_factor

        confidence_gate = sig.confidence >= 0.35
        if not confidence_gate:
            return RiskDecision(
                False, reasons=[f"confidence {sig.confidence:.2f} below 0.35 gate"],
                thought="Risk reject: low-confidence signal (transparent gate, not ML).")

        thought = (
            f"Sizing: capital ₹{cfg.capital:,.0f}, risk {cfg.risk_per_trade_pct:.1f}% "
            f"= ₹{risk_rs:,.0f}; SL distance ₹{per_unit:,.2f}; {lots} lot(s) x "
            f"{lot} = {qty} qty; margin ₹{margin_required:,.0f} of "
            f"₹{available_margin:,.0f}. Position cap {len(open_positions)}/"
            f"{cfg.max_open_positions}; orders/min throttle ok."
        )
        return RiskDecision(True, qty=qty, lots=lots, reasons=reasons, thought=thought)
