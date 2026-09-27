"""Bot orchestrator — the automated decision loop.

Pipeline per cycle (each stage writes its reasoning to the decision journal
and the UI 'Decision Stream'):

    ANALYSE  -> indicators & structure from fresh bars/ticks
    DECIDE   -> strategies emit signals with reasoning chains
    RISK     -> sizing (capital*risk%/(entry-SL), lots), margin, ceilings
    EXECUTE  -> paper fills / semi-auto confirm / live adapter
    MANAGE   -> SL, target, trailing-after-min-profit, theta time-exit,
                square-off time
    REVIEW   -> self-improvement (bounded, transparent)

Threads: this worker runs in a QThread; the UI thread only talks to it via
Qt signals/slots; market data (sim or websocket) feeds it ticks.
"""

from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from PySide6.QtCore import QThread
from PySide6.QtCore import Signal as QtSignal

from kalvex.core import indicators as ind
from kalvex.core.db import Database, ist_now_str
from kalvex.core.instruments import DEFAULT_BOOK
from kalvex.core.models import (
    Bar, BotMode, BotState, OrderRequest, OrderSource, OrderType, Position,
    Side, Signal, Stage,
)
from kalvex.core.options import pick_strike, time_exit_due
from kalvex.core.risk import RiskConfig, RiskManager
from kalvex.core.self_improve import review_strategy
from kalvex.core.strategies import ALL_STRATEGIES, Strategy, StrategyContext

IST = ZoneInfo("Asia/Kolkata")


class BotWorker(QThread):
    thought = QtSignal(dict)          # {ts, stage, strategy, text}
    tick_update = QtSignal(dict)      # {instrument, ltp, bars}
    pnl_update = QtSignal(float, float)   # realised, unrealised
    state_changed = QtSignal(str)
    toast = QtSignal(str)
    semi_confirm = QtSignal(object)   # Signal awaiting user confirmation
    positions_changed = QtSignal()

    def __init__(self, db: Database, feed, broker, risk_cfg: RiskConfig,
                 mode: BotMode = BotMode.PAPER, instruments: dict | None = None,
                 cycle_seconds: float = 1.0, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self.feed = feed
        self.broker = broker
        self.mode = mode
        self.cycle_seconds = cycle_seconds
        self.risk = RiskManager(risk_cfg)
        self.book = dict(instruments or DEFAULT_BOOK)
        self.strategies: dict[str, Strategy] = {}
        self.pending_signals: list[Signal] = []
        self._lock = threading.Lock()   # guards broker state across threads
        self._stop = False
        self._kill = False
        self.state = BotState.STOPPED
        self.cycle_no = 0
        self.trades_by_strategy: dict[str, list] = {}
        self.reviews_since: dict[str, int] = {}
        self._last_analysed_bars = 0
        self.auto_tune = db.get_setting("auto_tune", "0") == "1"
        self._load_strategies()

    # ------------------------------------------------------------------ #
    def _load_strategies(self) -> None:
        import json
        for key, cls in ALL_STRATEGIES.items():
            row = self.db.one("SELECT * FROM strategies WHERE key=?", (key,))
            if row is None:
                self.db.execute(
                    "INSERT OR IGNORE INTO strategies(key,name,enabled,mode,params) "
                    "VALUES(?,?,?,?,?)",
                    (key, cls.name, 1, "Paper", json.dumps(cls().params)))
                params = cls().params
            else:
                params = json.loads(row["params"] or "{}")
            self.strategies[key] = cls(params)
            self.reviews_since[key] = 0

    def set_strategy_enabled(self, key: str, enabled: bool) -> None:
        self.db.execute("UPDATE strategies SET enabled=? WHERE key=?",
                        (int(enabled), key))

    def set_strategy_param(self, key: str, param: str, value) -> None:
        import json
        s = self.strategies.get(key)
        if not s:
            return
        s.params[param] = value
        self.db.execute("UPDATE strategies SET params=? WHERE key=?",
                        (json.dumps(s.params), key))

    def enabled_strategies(self) -> list[Strategy]:
        rows = {r["key"]: r["enabled"] for r in
                self.db.query("SELECT key, enabled FROM strategies")}
        return [s for k, s in self.strategies.items() if rows.get(k, 0)]

    # ------------------------------------------------------------------ #
    # lifecycle
    # ------------------------------------------------------------------ #
    def stop(self) -> None:
        self._stop = True

    def kill_switch(self) -> None:
        """Cancel everything, flatten, stop — immediate."""
        with self._lock:
            self._kill_switch_locked()

    def _kill_switch_locked(self) -> None:
        self._kill = True
        self._set_state(BotState.KILLED)
        self._think(Stage.SYSTEM, "KILL SWITCH", 
                    "Kill switch armed: cancelling open orders, flattening all positions, stopping bot.")
        self._flatten_all("KILL SWITCH")
        self.db.log("WARNING", "Bot", "KILL_SWITCH", "executed")
        self._stop = True

    def request_flatten_all(self, reason: str) -> None:
        self._think(Stage.SYSTEM, "MANAGE", f"Flatten-all requested: {reason}")
        with self._lock:
            self._flatten_all(reason)

    def _set_state(self, st: BotState) -> None:
        self.state = st
        self.db.set_state("state", st.value)
        self.state_changed.emit(st.value)

    def _think(self, stage: Stage, strategy: str, text: str, data: dict | None = None) -> None:
        cid = f"c{self.cycle_no}"
        self.db.log_decision(cid, stage.value, strategy, text, data)
        self.thought.emit({"ts": ist_now_str(), "stage": stage.value,
                           "strategy": strategy, "text": text})

    def _mark_paper_used(self) -> None:
        """Paper-first gate: only Paper/Semi runs (which trade paper) unlock Auto."""
        if self.mode in (BotMode.PAPER, BotMode.SEMI_AUTO):
            self.db.set_state("paper_used", "1")

    # ------------------------------------------------------------------ #
    def run(self) -> None:
        self._set_state(BotState.RUNNING)
        self._think(Stage.SYSTEM, "SYSTEM",
                    f"Bot started in {self.mode.value} mode. Feed: "
                    f"{type(self.feed).__name__}. Recovery: "
                    f"{len(self.db.load_positions())} position(s), "
                    f"{len(self.db.load_open_orders())} open order(s) restored from DB.")
        self._mark_paper_used()

        while not self._stop:
            cycle_start = time.monotonic()
            try:
                with self._lock:
                    self._cycle()
            except Exception as e:  # keep the loop alive; log the fault
                self.db.log("ERROR", "Bot", "CYCLE_ERROR", repr(e))
                self._think(Stage.SYSTEM, "SYSTEM", f"Cycle error (contained): {e!r}")
            self._mark_paper_used()
            elapsed = time.monotonic() - cycle_start
            self.msleep(int(max(0.0, self.cycle_seconds - elapsed) * 1000))

        self._set_state(BotState.STOPPED)
        self._think(Stage.SYSTEM, "SYSTEM", "Bot stopped cleanly.")

    # ------------------------------------------------------------------ #
    def _cycle(self) -> None:
        self.cycle_no += 1
        now = self.feed.now()

        # session gate: unattended operation only during configured hours
        hhmm = now.strftime("%H:%M")
        open_t = self.db.get_setting("session_open", "09:15")
        close_t = self.db.get_setting("session_close", "15:30")
        square_off = self.db.get_setting("square_off_time", "15:15")

        if hhmm >= square_off and self.broker.get_positions():
            self._think(Stage.MANAGE, "SYSTEM",
                        f"Square-off time {square_off} IST reached — flattening.")
            self._flatten_all("SQUARE-OFF")
        if hhmm >= close_t or hhmm < open_t:
            return   # outside session: no new decisions (bot idles)

        # ---- ANALYSE -----------------------------------------------------
        ltps: dict[str, float] = {}
        bars_map: dict[str, list[Bar]] = {}
        for name in self.book:
            ltps[name] = self.feed.ltp(name)
            bars_map[name] = self.feed.bars(name)

        # narrate the analysis once per closed bar (keeps the thought stream
        # informative without spamming every cycle)
        primary = list(self.book.keys())[0]
        bars = bars_map.get(primary, [])
        if bars and len(bars) != self._last_analysed_bars:
            self._last_analysed_bars = len(bars)
            closes = [b.close for b in bars]
            if len(closes) >= 21:
                e9, e21 = ind.ema(closes, 9)[-1], ind.ema(closes, 21)[-1]
                r = ind.rsi(closes, 14)[-1]
                _, dirn = ind.supertrend([b.high for b in bars],
                                         [b.low for b in bars], closes, 10, 3.0)
                self._think(Stage.ANALYSE, "SYSTEM",
                            f"Bar closed {primary} @ {closes[-1]:,.2f}: EMA9 "
                            f"{e9:,.2f} {'>' if e9 > e21 else '<'} EMA21 {e21:,.2f}, "
                            f"RSI {r:.0f}, Supertrend "
                            f"{'UP' if dirn[-1] == 1 else 'DOWN'}. Structure "
                            f"updated; evaluating {len(self.enabled_strategies())} "
                            f"strategy plan(s).")

        open_positions = self.broker.get_positions()
        unrealised = sum(p.unrealised(ltps.get(p.instrument, p.avg_price))
                         for p in open_positions)

        # hard daily limits
        breach = self.risk.daily_limits_breached(unrealised)
        if breach:
            self._think(Stage.RISK, "RISK", breach.thought, {"reasons": breach.reasons})
            if breach.flatten_all:
                self._flatten_all("DAILY LOSS LIMIT")
            if breach.stop_bot:
                self.toast.emit("DAILY LIMIT — bot stopped")
                self._stop = True
                return

        # ---- MANAGE open positions first ---------------------------------
        self._manage_positions(open_positions, ltps, now)

        # matching engine updates (paper fills against fresh prices)
        if hasattr(self.broker, "on_tick"):
            for t in self.broker.on_tick(ltps):
                self.risk.register_fill_pnl(t.pnl)
                self.positions_changed.emit()

        self.pnl_update.emit(self.risk.day_realised_pnl, unrealised)

        # ---- DECIDE ------------------------------------------------------
        signals: list[Signal] = []
        for strat in self.enabled_strategies():
            ctx = self._context_for(strat, bars_map, ltps, now)
            if ctx is None:
                continue
            sigs = strat.evaluate(ctx)
            for s in sigs:
                self.db.insert_signal(f"c{self.cycle_no}", s)
                self._think(Stage.DECIDE, s.strategy_key, s.thought,
                            {"reasons": s.reasons, "entry": s.entry,
                             "sl": s.sl, "target": s.target,
                             "confidence": s.confidence})
                signals.append(s)

        # ---- RISK + EXECUTE ---------------------------------------------
        for sig in signals:
            self._execute_signal(sig, ltps, open_positions, now)

        # ---- REVIEW ------------------------------------------------------
        self._maybe_review()

    # ------------------------------------------------------------------ #
    def _context_for(self, strat: Strategy, bars_map: dict, ltps: dict,
                     now: datetime) -> StrategyContext | None:
        instrument = self._instrument_for(strat)
        bars = bars_map.get(instrument, [])
        min_bars = 30
        if len(bars) < min_bars:
            return None
        session_minute = (now.hour * 60 + now.minute) - (9 * 60 + 15)
        spec = self.book.get(instrument)
        return StrategyContext(
            instrument=instrument, bars=bars, spot=ltps.get(instrument, 0.0),
            session_minute=session_minute,
            params={"segment": spec.segment if spec else "EQ"},
        )

    def _instrument_for(self, strat: Strategy) -> str:
        # v1: strategies bound to a user-selected instrument (default first)
        return self.db.get_setting(f"instrument_for_{strat.key}",
                                   list(self.book.keys())[0])

    def _execute_signal(self, sig: Signal, ltps: dict,
                        open_positions: list[Position], now: datetime) -> None:
        spec = self.book.get(sig.instrument)
        lot = spec.lot_size if spec else self.risk.config.lot_size

        # Options path: convert directional signal into a defined-risk
        # option buy (v1: buying only) before sizing.
        if self.db.get_setting("options_enabled", "0") == "1" and spec and spec.is_index:
            bias = "CE" if sig.side == Side.BUY else "PE"
            width = int(self.db.get_setting("options_otm_width", "0"))
            req_opt = pick_strike(sig.entry, spec, bias, otm_width=width,
                                  expiry="current")
            self._think(Stage.DECIDE, sig.strategy_key, req_opt.thought)
            sig.is_options = True
            sig.option_meta = {"strike": req_opt.strike,
                               "type": req_opt.option_type,
                               "expiry": req_opt.expiry}

        funds = self.broker.get_funds()
        decision = self.risk.evaluate(sig, open_positions,
                                      funds.get("available_margin", 0.0), lot)
        self._think(Stage.SIZE, sig.strategy_key, decision.thought,
                    {"approved": decision.approved, "qty": decision.qty,
                     "reasons": decision.reasons})
        if not decision.approved:
            return

        max_hold = int(self.db.get_setting("options_max_hold_min", "45")) * 60 \
            if sig.is_options else 0

        if self.mode == BotMode.SEMI_AUTO:
            self._think(Stage.EXECUTE, sig.strategy_key,
                        "Semi-auto: awaiting user confirmation (Windows toast sent).")
            self.toast.emit(
                f"SIGNAL {sig.side.value} {sig.instrument} @ {sig.entry:,.2f} "
                f"(SL {sig.sl:,.2f}) — confirm in app")
            self.semi_confirm.emit((sig, decision))
            return

        self._place_entry(sig, decision.qty, max_hold)

    def confirm_semi(self, payload, accept: bool) -> None:
        """User response to a semi-auto confirmation."""
        with self._lock:
            self._confirm_semi_locked(payload, accept)

    def _confirm_semi_locked(self, payload, accept: bool) -> None:
        sig, decision = payload
        if accept:
            self._place_entry(sig, decision.qty, 0)
        else:
            self._think(Stage.EXECUTE, sig.strategy_key,
                        "Semi-auto: user REJECTED the signal. No order sent.")

    def _place_entry(self, sig: Signal, qty: int, max_hold: int) -> None:
        source = OrderSource.LIVE if self.mode == BotMode.AUTO else OrderSource.PAPER

        # Rate-limit gate at execution time (verified Upstox cap: 10/sec).
        ok, why = self.risk.throttle.allow()
        if not ok:
            self._think(Stage.EXECUTE, sig.strategy_key,
                        f"Order NOT sent — throttled: {why}")
            return

        tag = f"KLV-{datetime.now(IST):%Y%m%d}-{sig.strategy_key}-{uuid.uuid4().hex[:6]}"
        # Prefer LIMIT entries (policy: raw MARKET not sent live).
        req = OrderRequest(
            instrument=sig.instrument, side=sig.side,
            order_type=OrderType.LIMIT, qty=qty, price=sig.entry,
            strategy_key=sig.strategy_key, source=source, tag=tag,
        )
        o = self.broker.place_order(req)

        # Paper: the engine OWNS the position lifecycle — fill immediately at
        # the signal price and attach the trade plan to the resulting
        # position. (Live: position is provisional until broker confirm.)
        if hasattr(self.broker, "_fill"):
            self.broker._fill(o, sig.entry)

        pos = None
        if hasattr(self.broker, "positions"):
            pos = self.broker.positions.get(sig.instrument)
        if pos is None:
            pos = Position(
                instrument=sig.instrument,
                qty=qty if sig.side == Side.BUY else -qty,
                avg_price=sig.entry, strategy_key=sig.strategy_key,
                source=source, opened_at=ist_now_str(),
            )
            if hasattr(self.broker, "positions"):
                self.broker.positions[sig.instrument] = pos

        pos.sl = sig.sl
        pos.target = sig.target
        pos.strategy_key = sig.strategy_key
        pos.is_options = sig.is_options
        pos.option_meta = sig.option_meta
        pos.max_hold_seconds = max_hold
        self.db.upsert_position(pos)

        self._think(Stage.EXECUTE, sig.strategy_key,
                    f"ORDER SENT ({source.value}): {sig.side.value} {qty} "
                    f"{sig.instrument} LIMIT {sig.entry:,.2f}, SL {sig.sl:,.2f}, "
                    f"target {sig.target:,.2f}, tag {tag}.")
        self.positions_changed.emit()

    # ------------------------------------------------------------------ #
    def _manage_positions(self, positions: list[Position], ltps: dict,
                          now: datetime) -> None:
        cfg = self.risk.config
        for p in positions:
            ltp = ltps.get(p.instrument, p.avg_price)
            upnl = p.unrealised(ltp)
            hit_sl = (p.qty > 0 and ltp <= p.sl > 0) or (p.qty < 0 and ltp >= p.sl > 0)
            hit_tgt = (p.qty > 0 and ltp >= p.target > 0) or (p.qty < 0 and ltp <= p.target > 0)

            # trailing SL: only after minimum profit
            if (not p.trail_active and cfg.trailing_start_profit > 0
                    and upnl >= cfg.trailing_start_profit):
                p.trail_active = True
                p.trail_price = ltp
                self._think(Stage.MANAGE, p.strategy_key,
                            f"Trailing SL ARMED on {p.instrument}: unrealised "
                            f"₹{upnl:,.0f} ≥ min profit ₹{cfg.trailing_start_profit:,.0f}.")
            if p.trail_active:
                if (p.qty > 0 and ltp > p.trail_price):
                    p.trail_price = ltp
                    p.sl = max(p.sl, ltp * 0.998)
                elif (p.qty < 0 and ltp < p.trail_price):
                    p.trail_price = ltp
                    p.sl = min(p.sl, ltp * 1.002) if p.sl > 0 else ltp * 1.002

            # theta-aware time exit (options) + hard max holding
            if p.is_options and p.opened_at:
                opened = datetime.strptime(p.opened_at, "%Y-%m-%d %H:%M:%S") \
                    .replace(tzinfo=IST)
                if time_exit_due(opened.timestamp(), now.timestamp(),
                                 p.max_hold_seconds):
                    self._think(Stage.MANAGE, p.strategy_key,
                                f"TIME EXIT {p.instrument}: max holding "
                                f"{p.max_hold_seconds//60}m reached (theta-aware "
                                f"rule) — flattening regardless of P&L.")
                    self._close_position(p, ltp, "TIME EXIT")
                    continue

            if hit_sl:
                self._think(Stage.MANAGE, p.strategy_key,
                            f"SL HIT {p.instrument} @ {ltp:,.2f} (SL {p.sl:,.2f}). "
                            f"Realised ≈ ₹{upnl:,.0f}.")
                self._close_position(p, ltp, "SL")
            elif hit_tgt:
                self._think(Stage.MANAGE, p.strategy_key,
                            f"TARGET HIT {p.instrument} @ {ltp:,.2f} "
                            f"(target {p.target:,.2f}). Realised ≈ ₹{upnl:,.0f}.")
                self._close_position(p, ltp, "TARGET")

    def _close_position(self, p: Position, ltp: float, reason: str) -> None:
        side = Side.SELL if p.qty > 0 else Side.BUY
        tag = f"KLV-EXIT-{uuid.uuid4().hex[:8]}"
        req = OrderRequest(
            instrument=p.instrument, side=side, order_type=OrderType.LIMIT,
            qty=abs(p.qty), price=ltp, strategy_key=p.strategy_key,
            source=p.source, tag=tag,
        )
        self.broker.place_order(req)
        if hasattr(self.broker, "on_tick"):
            # force immediate fill at current price for exits
            open_o = [o for o in self.broker.open_orders.values()
                      if o.tag == tag]
            for o in open_o:
                self.broker._fill(o, ltp)
        self.risk.register_fill_pnl(p.unrealised(ltp))
        if hasattr(self.broker, "positions"):
            self.broker.positions.pop(p.instrument, None)
        self.db.delete_position(p.instrument)
        self.db.log("INFO", "Bot", f"CLOSE_{reason}",
                    f"{p.instrument} @ {ltp:.2f}")
        self.positions_changed.emit()

    def _flatten_all(self, reason: str) -> None:
        for p in list(self.broker.get_positions()):
            ltp = self.feed.ltp(p.instrument) or p.avg_price
            self._think(Stage.MANAGE, p.strategy_key,
                        f"Flatten {p.instrument} ({reason}) at {ltp:,.2f}.")
            self._close_position(p, ltp, reason)
        if hasattr(self.broker, "open_orders"):
            for o in list(self.broker.open_orders.values()):
                self.broker.cancel_order(o.id)
        self._think(Stage.MANAGE, "SYSTEM",
                    f"All positions flat, open orders cancelled ({reason}).")

    # ------------------------------------------------------------------ #
    def _maybe_review(self) -> None:
        # group trades by strategy from the DB
        rows = self.db.query(
            "SELECT * FROM trades WHERE source='PAPER' ORDER BY id")
        by_strat: dict[str, list] = {}
        for r in rows:
            from kalvex.core.models import Trade
            t = Trade(id=r["id"], instrument=r["instrument"],
                      side=Side(r["side"]), qty=r["qty"], price=r["price"],
                      fee=r["fee"], pnl=r["pnl"], strategy_key=r["strategy_key"],
                      source=OrderSource(r["source"]), ts=r["ts"])
            by_strat.setdefault(r["strategy_key"], []).append(t)

        for key, trades in by_strat.items():
            strat = self.strategies.get(key)
            if not strat:
                continue
            since = self.reviews_since.get(key, 0) + 1
            self.reviews_since[key] = since
            if since < 5:
                continue
            self.reviews_since[key] = 0
            rev = review_strategy(key, strat.params, trades, self.auto_tune)
            self.db.insert_review(key, rev.window, rev.stats, rev.suggestion,
                                  rev.apply or rev.disable_strategy)
            self._think(Stage.REVIEW, key, rev.thought,
                        {"stats": rev.stats, "suggestion": rev.suggestion})
            if rev.disable_strategy:
                self.set_strategy_enabled(key, False)
                self.toast.emit(f"Strategy {key} auto-disabled after losses")
            elif rev.apply and rev.suggestion:
                for param, val in rev.suggestion.items():
                    self.set_strategy_param(key, param, val)
                self._think(Stage.REVIEW, key,
                            f"Auto-tune applied within hard bands: {rev.suggestion}")
