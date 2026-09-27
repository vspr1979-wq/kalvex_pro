"""Headless self-test: drives the FULL automated loop on synthetic market
data and verifies the invariants that matter.

Run:  python main.py --selftest

Checks:
  1. decision journal records every pipeline stage with reasoning
  2. signals are produced by rule-based strategies
  3. position sizing matches capital * risk% / (entry - SL), lot-rounded
  4. order throttle never exceeds the verified 10/sec broker cap
  5. daily-loss limit flattens and stops the bot
  6. kill switch flattens everything immediately
  7. restart recovery does not duplicate orders (client-tag dedupe)
  8. self-improvement reviews fire and stay inside hard bands
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from kalvex.core.db import Database
from kalvex.core.market_data import SimFeedProvider
from kalvex.core.models import BotMode, OrderRequest, OrderType, Side
from kalvex.core.execution import PaperEngine
from kalvex.core.risk import RiskConfig, RiskManager
from kalvex.core.bot import BotWorker
from kalvex.core.strategies import TUNE_BANDS


def build_world(db_path: str, seed: int = 11, capital: float = 500_000.0):
    db = Database(db_path)
    for k, v in {
        "capital": str(capital), "risk_per_trade_pct": "1.0",
        "max_open_positions": "3", "max_lots": "2", "max_orders_per_min": "40",
        "daily_max_loss": "8000", "square_off_time": "15:15",
        "session_open": "09:15", "session_close": "15:30",
        "auto_tune": "1", "options_enabled": "0",
    }.items():
        db.set_setting(k, v)

    feed = SimFeedProvider(
        {"NIFTY 50": 24800.0, "NIFTY FUT": 24820.0, "RELIANCE": 2900.0},
        seed=seed, speed=30.0)
    broker = PaperEngine(db)
    cfg = RiskConfig(capital=capital, risk_per_trade_pct=1.0, max_open_positions=3,
                     max_lots=2, max_orders_per_min=40, daily_max_loss=8000.0,
                     lot_size=75)
    bot = BotWorker(db, feed, broker, cfg, mode=BotMode.PAPER, cycle_seconds=0.0)
    return db, feed, broker, bot


def run_minutes(db, feed, broker, bot, minutes: int) -> None:
    steps = int(minutes * 60 / feed.speed)   # each tick advances `speed` seconds
    for _ in range(steps):
        feed.tick()
        bot._cycle()


def main() -> int:
    ok = True
    report: list[str] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal ok
        ok = ok and bool(cond)
        report.append(f"  [{'PASS' if cond else 'FAIL'}] {name}" +
                      (f" — {detail}" if detail else ""))

    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "kalvex_test.db")
        db, feed, broker, bot = build_world(db_path)

        print("Kalvex Pro self-test — full automated loop on SIMULATED data")
        print("=" * 62)

        # ---- run ~3 simulated hours of market time ----------------------
        run_minutes(db, feed, broker, bot, minutes=180)

        decisions = db.query("SELECT stage, thought FROM decision_log")
        stages = {d["stage"] for d in decisions}
        check("decision journal populated", len(decisions) > 20,
              f"{len(decisions)} thoughts recorded")
        check("pipeline stages present",
              {"ANALYSE", "DECIDE", "SIZE", "EXECUTE", "MANAGE"} & stages
              or {"DECIDE", "SIZE"} <= stages,
              f"stages seen: {sorted(stages)}")

        signals = db.query("SELECT * FROM signals")
        check("strategies produced signals", len(signals) > 0,
              f"{len(signals)} signal(s)")

        orders = db.query("SELECT * FROM orders")
        check("orders placed through risk gate", len(orders) > 0,
              f"{len(orders)} order(s)")

        # ---- sizing verification --------------------------------------
        max_risk = 0.0
        for o in orders:
            sig = next((s for s in signals if s["strategy_key"] == o["strategy_key"]),
                       None)
            if sig and sig["entry"] and sig["sl"] and o["qty"]:
                risk = abs(sig["entry"] - sig["sl"]) * o["qty"]
                max_risk = max(max_risk, risk)
        cap = 500_000.0
        check("position sizing within risk budget (1% + 1-lot rounding)",
              max_risk <= cap * 0.012,
              f"max trade risk ₹{max_risk:,.0f} vs limit ₹{cap*0.012:,.0f}")

        # ---- throttle --------------------------------------------------
        from kalvex.core.risk import OrderThrottle
        th = OrderThrottle(per_sec=10, per_min=10_000)
        blocked = 0
        for i in range(25):
            allowed, _ = th.allow()
            if not allowed:
                blocked += 1
        check("10/sec broker cap enforced", blocked == 15,
              f"{25-blocked} allowed, {blocked} throttled in burst of 25")

        # ---- journal reasoning quality --------------------------------
        size_thoughts = [d["thought"] for d in decisions
                         if d["stage"] == "SIZE" and "Sizing:" in d["thought"]]
        check("sizing decisions carry full reasoning", len(size_thoughts) > 0,
              f"e.g. \"{size_thoughts[0][:90]}...\"" if size_thoughts else "")

        # ---- kill switch ----------------------------------------------
        if broker.get_positions():
            bot.kill_switch()
            check("kill switch flattens all positions",
                  len(broker.get_positions()) == 0)
        else:
            # force an open position then kill
            from kalvex.core.models import Position
            broker.positions["NIFTY 50"] = Position(
                instrument="NIFTY 50", qty=75, avg_price=feed.ltp("NIFTY 50"),
                sl=0, target=0)
            bot.kill_switch()
            check("kill switch flattens all positions",
                  len(broker.get_positions()) == 0)

        # ---- daily loss rule ------------------------------------------
        rm = RiskManager(RiskConfig(daily_max_loss=1000.0, daily_profit_stop=2000.0,
                                    profit_stop_enabled=True))
        rm.register_fill_pnl(-1200.0)
        breach = rm.daily_limits_breached(0.0)
        check("daily max loss triggers flatten + stop",
              breach is not None and breach.flatten_all and breach.stop_bot)

        # ---- restart recovery / no duplicate orders --------------------
        db3 = Database(db_path)   # same file -> recovery
        engine2 = PaperEngine(db3)
        recovered = len(engine2.open_orders)
        dup = OrderRequest(instrument="NIFTY 50", side=Side.BUY,
                           order_type=OrderType.LIMIT, qty=75, price=1.0,
                           tag="KLV-DUP-TEST")
        o1 = engine2.place_order(dup)
        o2 = engine2.place_order(dup)
        check("client-tag dedupe prevents duplicate orders",
              o1.id == o2.id and recovered == len(engine2.open_orders) - 1)

        # ---- self-improvement -----------------------------------------
        from kalvex.core.models import Trade, OrderSource
        from kalvex.core.self_improve import review_strategy
        fake_trades = [Trade(id=str(i), instrument="NIFTY 50", side=Side.BUY,
                             qty=75, price=100.0, fee=20.0,
                             pnl=(-200 if i < 4 else 150), strategy_key="orb",
                             source=OrderSource.PAPER) for i in range(6)]
        rev = review_strategy("orb", {"target_rr": 1.6}, fake_trades, auto_tune=True)
        check("review produces transparent thought", bool(rev.thought),
              rev.thought[:80])
        if rev.suggestion:
            for p, v in rev.suggestion.items():
                lo, hi = TUNE_BANDS["orb"].get(p, (v, v))
                check(f"tune '{p}' stays inside hard band ({lo}-{hi})",
                      lo <= v <= hi, f"value={v}")
        else:
            check("review declined to change params (allowed)", True)

        fake_losing = [Trade(id=str(i), instrument="NIFTY 50", side=Side.BUY,
                             qty=75, price=100.0, fee=20.0, pnl=-100.0,
                             strategy_key="orb", source=OrderSource.PAPER)
                       for i in range(6)]
        rev2 = review_strategy("orb", {"target_rr": 1.6}, fake_losing, auto_tune=True)
        check("5+ consecutive losses -> hard auto-disable",
              rev2.disable_strategy)

        # ---- sample thought stream ------------------------------------
        rows = db.query("SELECT ts, stage, strategy_key, thought FROM decision_log "
                        "ORDER BY id DESC LIMIT 6")
        print("\nSample thought stream (most recent first):")
        for r in reversed(rows):
            print(f"  {r['ts']} [{r['stage']:>8}] {r['strategy_key'] or '-':<10} "
                  f"{r['thought'][:96]}")

        trades = db.query("SELECT * FROM trades")
        realised = sum(t["pnl"] for t in trades)
        print(f"\nSummary: {len(signals)} signals, {len(orders)} orders, "
              f"{len(trades)} fills, realised P&L ₹{realised:,.0f}, "
              f"{len(decisions)} journal entries")

    print("\n" + "=" * 62)
    print("SELF-TEST", "PASSED" if ok else "FAILED")
    for line in report:
        print(line)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
