"""v1 strategy set — exactly four live strategies, each producing signals
with an explicit, human-readable reasoning chain (the bot's 'thought
process'). No black-box ML anywhere: every decision is rule-based and
auditable.

1. Opening Range Breakout  (index / liquid F&O)
2. EMA Crossover + VWAP filter
3. Supertrend trend-follow
4. RSI mean-reversion (cash or futures only in v1)

Nice-to-have later (not live auto-entry): Bollinger squeeze, MACD,
SMC FVG/OB/BOS/CHoCH as overlays + optional alert only.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kalvex.core import indicators as ind
from kalvex.core.models import Bar, Side, Signal


# --------------------------------------------------------------------- #
# Context shared by all strategies on each decision cycle
# --------------------------------------------------------------------- #
@dataclass
class StrategyContext:
    instrument: str
    bars: list[Bar]
    spot: float
    session_minute: int          # minutes since market open
    params: dict = field(default_factory=dict)
    allow_options: bool = False

    # lazily-computed indicator cache
    _cache: dict = field(default_factory=dict)

    @property
    def closes(self) -> list[float]:
        return [b.close for b in self.bars]

    @property
    def highs(self) -> list[float]:
        return [b.high for b in self.bars]

    @property
    def lows(self) -> list[float]:
        return [b.low for b in self.bars]

    @property
    def volumes(self) -> list[float]:
        return [b.volume for b in self.bars]

    @property
    def day_ids(self) -> list[str]:
        return [b.ts.strftime("%Y-%m-%d") for b in self.bars]

    def ema(self, period: int) -> list[float]:
        key = ("ema", period)
        if key not in self._cache:
            self._cache[key] = ind.ema(self.closes, period)
        return self._cache[key]

    def rsi(self, period: int) -> list[float]:
        key = ("rsi", period)
        if key not in self._cache:
            self._cache[key] = ind.rsi(self.closes, period)
        return self._cache[key]

    def supertrend(self, period: int, mult: float):
        key = ("st", period, mult)
        if key not in self._cache:
            self._cache[key] = ind.supertrend(self.highs, self.lows, self.closes,
                                              period, mult)
        return self._cache[key]

    def vwap(self) -> list[float]:
        key = ("vwap",)
        if key not in self._cache:
            self._cache[key] = ind.vwap_session(
                self.highs, self.lows, self.closes, self.volumes, self.day_ids)
        return self._cache[key]


class Strategy:
    key = "base"
    name = "Base"

    def __init__(self, params: dict | None = None) -> None:
        self.params = dict(self.default_params())
        if params:
            self.params.update(params)

    def default_params(self) -> dict:
        return {}

    def evaluate(self, ctx: StrategyContext) -> list[Signal]:
        raise NotImplementedError


def _sig(ctx: StrategyContext, strat: str, side: Side, entry: float,
         sl: float, target: float, confidence: float, reasons: list[str],
         thought: str) -> Signal:
    return Signal(
        strategy_key=strat, instrument=ctx.instrument, side=side,
        entry=round(entry, 2), sl=round(sl, 2), target=round(target, 2),
        confidence=max(0.0, min(1.0, confidence)), reasons=reasons,
        thought=thought,
    )


# --------------------------------------------------------------------- #
# 1. Opening Range Breakout
# --------------------------------------------------------------------- #
class OpeningRangeBreakout(Strategy):
    key = "orb"
    name = "Opening Range Breakout (index / liquid F&O)"

    def default_params(self) -> dict:
        return {
            "range_minutes": 15,     # opening range window (self-tune band 5-30)
            "buffer_pct": 0.02,      # breakout buffer above range H/L
            "rr": 1.6,               # target = range height * rr
            "stop_after_minute": 210,# no fresh entries late in the session
            "min_range_pct": 0.02,   # skip dead-flat ranges
            "trend_ema": 20,
        }

    def evaluate(self, ctx: StrategyContext) -> list[Signal]:
        p = self.params
        need = p["range_minutes"] + 2
        if len(ctx.bars) < need:
            return []
        # one-shot per direction per session: the setup is the FIRST break,
        # not every subsequent candle above the level.
        day = ctx.bars[-1].ts.strftime("%Y-%m-%d")
        if getattr(self, "_fired_day", "") != day:
            self._fired = set()
            self._fired_day = day
        rng_bars = ctx.bars[-need: -2]  # completed range bars
        if len(rng_bars) < p["range_minutes"]:
            return []
        hi = max(b.high for b in rng_bars[-p["range_minutes"]:])
        lo = min(b.low for b in rng_bars[-p["range_minutes"]:])
        height = hi - lo
        if height <= 0:
            return []
        range_pct = height / ctx.spot * 100.0
        if range_pct < p["min_range_pct"]:
            return []  # thought recorded by caller via empty cycle notes
        if ctx.session_minute > p["stop_after_minute"]:
            return []

        close = ctx.spot
        ema20 = ctx.ema(p["trend_ema"])[-1]
        buf = hi * (1 + p["buffer_pct"] / 100.0)
        buf_lo = lo * (1 - p["buffer_pct"] / 100.0)

        if close > buf and close > ema20:
            if "L" in self._fired:
                return []
            sl = lo - height * 0.1
            target = close + height * p["rr"]
            reasons = [
                f"close {close:,.2f} broke range high {hi:,.2f} (+buffer)",
                f"range {lo:,.2f}–{hi:,.2f} = {range_pct:.2f}% wide (min {p['min_range_pct']}%)",
                f"trend filter: close > EMA{p['trend_ema']} ({ema20:,.2f})",
            ]
            thought = (
                f"ORB breakout LONG: opening range {lo:,.2f}–{hi:,.2f} "
                f"({p['range_minutes']}m, {range_pct:.2f}%). Price {close:,.2f} "
                f"cleared {buf:,.2f} with EMA trend filter agreeing. "
                f"SL under range low, target = range x {p['rr']}. "
                f"One-shot setup (first break only)."
            )
            self._fired.add("L")
            return [_sig(ctx, self.key, Side.BUY, close, sl, target,
                         0.55 + min(0.3, range_pct / 2), reasons, thought)]

        if close < buf_lo and close < ema20:
            if "S" in self._fired:
                return []
            sl = hi + height * 0.1
            target = close - height * p["rr"]
            reasons = [
                f"close {close:,.2f} broke range low {lo:,.2f} (-buffer)",
                f"range {lo:,.2f}–{hi:,.2f} = {range_pct:.2f}% wide",
                f"trend filter: close < EMA{p['trend_ema']} ({ema20:,.2f})",
            ]
            thought = (
                f"ORB breakout SHORT: range {lo:,.2f}–{hi:,.2f}; price "
                f"{close:,.2f} fell through {buf_lo:,.2f} with EMA agreement. "
                f"One-shot setup (first break only)."
            )
            self._fired.add("S")
            return [_sig(ctx, self.key, Side.SELL, close, sl, target,
                         0.55 + min(0.3, range_pct / 2), reasons, thought)]
        return []


# --------------------------------------------------------------------- #
# 2. EMA crossover + VWAP filter
# --------------------------------------------------------------------- #
class EmaCrossoverVwap(Strategy):
    key = "ema_vwap"
    name = "EMA Crossover + VWAP Filter"

    def default_params(self) -> dict:
        return {
            "fast": 9, "slow": 21,
            "use_vwap_filter": True,
            "min_conf": 0.4,
            "sl_atr_mult": 1.2, "target_rr": 1.8,
        }

    def evaluate(self, ctx: StrategyContext) -> list[Signal]:
        p = self.params
        if len(ctx.bars) < p["slow"] + 3:
            return []
        fast, slow = ctx.ema(p["fast"]), ctx.ema(p["slow"])
        vwap = ctx.vwap()
        cross_up = fast[-2] <= slow[-2] and fast[-1] > slow[-1]
        cross_dn = fast[-2] >= slow[-2] and fast[-1] < slow[-1]
        if not (cross_up or cross_dn):
            return []
        atr = ind.atr(ctx.highs, ctx.lows, ctx.closes, 14)[-1]
        close = ctx.spot
        if cross_up:
            filter_ok = (not p["use_vwap_filter"]) or close > vwap[-1]
            if not filter_ok:
                return []
            sl = close - atr * p["sl_atr_mult"]
            target = close + (close - sl) * p["target_rr"]
            reasons = [f"EMA{p['fast']} crossed above EMA{p['slow']}",
                       f"VWAP filter: close {close:,.2f} > VWAP {vwap[-1]:,.2f}",
                       f"ATR {atr:,.2f} -> SL = {p['sl_atr_mult']}x ATR"]
            thought = (f"EMA cross UP confirmed. VWAP filter PASS "
                       f"({close:,.2f} > {vwap[-1]:,.2f}). Structure: entry at "
                       f"close, SL {sl:,.2f} = 1.2x ATR, target {target:,.2f} "
                       f"(RR {p['target_rr']}).")
            return [_sig(ctx, self.key, Side.BUY, close, sl, target, 0.6,
                         reasons, thought)]
        filter_ok = (not p["use_vwap_filter"]) or close < vwap[-1]
        if not filter_ok:
            return []
        sl = close + atr * p["sl_atr_mult"]
        target = close - (sl - close) * p["target_rr"]
        reasons = [f"EMA{p['fast']} crossed below EMA{p['slow']}",
                   f"VWAP filter: close {close:,.2f} < VWAP {vwap[-1]:,.2f}",
                   f"ATR {atr:,.2f} -> SL = {p['sl_atr_mult']}x ATR"]
        thought = (f"EMA cross DOWN confirmed. VWAP filter PASS. SL {sl:,.2f}, "
                   f"target {target:,.2f} (RR {p['target_rr']}).")
        return [_sig(ctx, self.key, Side.SELL, close, sl, target, 0.6,
                     reasons, thought)]


# --------------------------------------------------------------------- #
# 3. Supertrend trend-follow
# --------------------------------------------------------------------- #
class SupertrendFollow(Strategy):
    key = "supertrend"
    name = "Supertrend Trend-Follow"

    def default_params(self) -> dict:
        return {"period": 10, "mult": 3.0,   # self-tune band 2.0-4.0
                "target_rr": 2.0}

    def evaluate(self, ctx: StrategyContext) -> list[Signal]:
        p = self.params
        if len(ctx.bars) < p["period"] + 3:
            return []
        line, direction = ctx.supertrend(p["period"], p["mult"])
        if direction[-1] == direction[-2]:
            return []
        close = ctx.spot
        st = line[-1]
        if direction[-1] == 1:
            sl = st
            target = close + (close - sl) * p["target_rr"]
            reasons = [f"Supertrend flipped UP (line {st:,.2f})",
                       f"params period={p['period']} mult={p['mult']}"]
            thought = (f"Supertrend flip LONG at {close:,.2f}; trailing anchor "
                       f"{st:,.2f}. Target {target:,.2f} = {p['target_rr']}x risk.")
            return [_sig(ctx, self.key, Side.BUY, close, sl, target, 0.55,
                         reasons, thought)]
        sl = st
        target = close - (sl - close) * p["target_rr"]
        reasons = [f"Supertrend flipped DOWN (line {st:,.2f})",
                   f"params period={p['period']} mult={p['mult']}"]
        thought = (f"Supertrend flip SHORT at {close:,.2f}; anchor {st:,.2f}.")
        return [_sig(ctx, self.key, Side.SELL, close, sl, target, 0.55,
                     reasons, thought)]


# --------------------------------------------------------------------- #
# 4. RSI mean-reversion (cash or futures only in v1)
# --------------------------------------------------------------------- #
class RsiMeanReversion(Strategy):
    key = "rsi_mr"
    name = "RSI Mean-Reversion (cash / futures only)"

    def default_params(self) -> dict:
        return {"period": 14, "oversold": 30, "overbought": 70,  # bands 40-80
                "target_rr": 1.2, "sl_atr_mult": 1.0}

    def evaluate(self, ctx: StrategyContext) -> list[Signal]:
        p = self.params
        if ctx.params.get("segment") == "OPT":
            return []   # v1: options excluded from mean-reversion
        if len(ctx.bars) < p["period"] + 5:
            return []
        r = ctx.rsi(p["period"])
        close = ctx.spot
        prev_close = ctx.closes[-2]
        atr = ind.atr(ctx.highs, ctx.lows, ctx.closes, 14)[-1]

        if r[-2] < p["oversold"] <= r[-1] and close >= prev_close:
            sl = close - atr * p["sl_atr_mult"]
            target = close + (close - sl) * p["target_rr"]
            reasons = [f"RSI({p['period']}) recovered from oversold: "
                       f"{r[-2]:.1f} -> {r[-1]:.1f} (band <{p['oversold']})",
                       "confirmation candle closed up",
                       "v1 scope: cash/futures only"]
            thought = (f"RSI mean-reversion LONG: RSI re-entered above "
                       f"{p['oversold']} from {r[-2]:.1f}. Fade with SL 1x ATR "
                       f"({sl:,.2f}), modest RR {p['target_rr']}.")
            return [_sig(ctx, self.key, Side.BUY, close, sl, target, 0.5,
                         reasons, thought)]

        if r[-2] > p["overbought"] >= r[-1] and close <= prev_close:
            sl = close + atr * p["sl_atr_mult"]
            target = close - (sl - close) * p["target_rr"]
            reasons = [f"RSI({p['period']}) fell from overbought: "
                       f"{r[-2]:.1f} -> {r[-1]:.1f} (band >{p['overbought']})",
                       "confirmation candle closed down",
                       "v1 scope: cash/futures only"]
            thought = (f"RSI mean-reversion SHORT: RSI dropped below "
                       f"{p['overbought']}. SL {sl:,.2f}, target {target:,.2f}.")
            return [_sig(ctx, self.key, Side.SELL, close, sl, target, 0.5,
                         reasons, thought)]
        return []


ALL_STRATEGIES: dict[str, type[Strategy]] = {
    OpeningRangeBreakout.key: OpeningRangeBreakout,
    EmaCrossoverVwap.key: EmaCrossoverVwap,
    SupertrendFollow.key: SupertrendFollow,
    RsiMeanReversion.key: RsiMeanReversion,
}

# Hard self-tune bands — the improvement loop may only move soft parameters
# inside these ranges, and never touches risk ceilings.
TUNE_BANDS: dict[str, dict[str, tuple[float, float]]] = {
    "orb": {"range_minutes": (5, 30), "rr": (1.2, 2.5), "buffer_pct": (0.0, 0.1)},
    "ema_vwap": {"fast": (5, 15), "slow": (15, 40), "target_rr": (1.2, 2.5)},
    "supertrend": {"mult": (2.0, 4.0), "period": (7, 14)},
    "rsi_mr": {"oversold": (20, 40), "overbought": (60, 80), "target_rr": (1.0, 2.0)},
}
