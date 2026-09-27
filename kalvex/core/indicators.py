"""Indicator math — pure Python, deterministic, dependency-free.

Formulas follow the standard definitions (Wilder RSI/ATR, standard EMA,
classic Supertrend, session VWAP). Kept in-house so the Windows build has
no C dependencies (TA-Lib); a pandas-ta adapter can later implement the
same function signatures for cross-checking.
"""

from __future__ import annotations

import math


def ema(values: list[float], period: int) -> list[float]:
    """Standard EMA, seeded with the first value (list length preserved)."""
    if not values or period <= 0:
        return []
    k = 2.0 / (period + 1.0)
    out = [values[0]]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def sma(values: list[float], period: int) -> list[float]:
    out: list[float] = []
    acc = 0.0
    for i, v in enumerate(values):
        acc += v
        if i >= period:
            acc -= values[i - period]
        out.append(acc / min(i + 1, period))
    return out


def rsi(values: list[float], period: int = 14) -> list[float]:
    """Wilder's RSI."""
    if len(values) < 2:
        return [50.0] * len(values)
    gains, losses = 0.0, 0.0
    out = [50.0]
    for i in range(1, len(values)):
        ch = values[i] - values[i - 1]
        g, l = max(ch, 0.0), max(-ch, 0.0)
        if i <= period:
            gains += g / period
            losses += l / period
            out.append(50.0)
            if i == period:
                out[-1] = 100.0 if losses == 0 else 100.0 - 100.0 / (1.0 + gains / losses)
        else:
            gains = (gains * (period - 1) + g) / period
            losses = (losses * (period - 1) + l) / period
            out.append(100.0 if losses == 0 else 100.0 - 100.0 / (1.0 + gains / losses))
    return out


def atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> list[float]:
    """Wilder's ATR."""
    n = len(closes)
    if n == 0:
        return []
    trs = [highs[0] - lows[0]]
    for i in range(1, n):
        trs.append(max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        ))
    out = [trs[0]]
    for i in range(1, n):
        if i < period:
            out.append(sum(trs[: i + 1]) / (i + 1))
        else:
            out.append((out[-1] * (period - 1) + trs[i]) / period)
    return out


def supertrend(highs: list[float], lows: list[float], closes: list[float],
               period: int = 10, multiplier: float = 3.0
               ) -> tuple[list[float], list[int]]:
    """Classic Supertrend. Returns (line, direction) where +1 = up, -1 = down."""
    n = len(closes)
    if n == 0:
        return [], []
    atrs = atr(highs, lows, closes, period)
    line = [0.0] * n
    direction = [1] * n
    upper = [0.0] * n
    lower = [0.0] * n
    for i in range(n):
        mid = (highs[i] + lows[i]) / 2.0
        up = mid + multiplier * atrs[i]
        dn = mid - multiplier * atrs[i]
        if i > 0:
            up = min(up, upper[i - 1]) if closes[i - 1] <= upper[i - 1] else up
            dn = max(dn, lower[i - 1]) if closes[i - 1] >= lower[i - 1] else dn
        upper[i], lower[i] = up, dn
        if i == 0:
            direction[i] = 1
        elif closes[i] > upper[i - 1]:
            direction[i] = 1
        elif closes[i] < lower[i - 1]:
            direction[i] = -1
        else:
            direction[i] = direction[i - 1]
        line[i] = lower[i] if direction[i] == 1 else upper[i]
    return line, direction


def vwap_session(highs: list[float], lows: list[float],
                 closes: list[float], volumes: list[float],
                 day_ids: list[str]) -> list[float]:
    """Session VWAP: resets on each new day_id, anchored at the session open."""
    out: list[float] = []
    acc_pv = 0.0
    acc_v = 0.0
    prev_day = None
    for i in range(len(closes)):
        if day_ids[i] != prev_day:
            acc_pv, acc_v = 0.0, 0.0
            prev_day = day_ids[i]
        typical = (highs[i] + lows[i] + closes[i]) / 3.0
        vol = volumes[i] if volumes[i] > 0 else 1.0
        acc_pv += typical * vol
        acc_v += vol
        out.append(acc_pv / acc_v)
    return out


def rolling_high(values: list[float], n: int) -> list[float]:
    return [max(values[max(0, i - n + 1): i + 1]) for i in range(len(values))]


def rolling_low(values: list[float], n: int) -> list[float]:
    return [min(values[max(0, i - n + 1): i + 1]) for i in range(len(values))]


def stdev(values: list[float], period: int = 20) -> list[float]:
    out: list[float] = []
    for i in range(len(values)):
        window = values[max(0, i - period + 1): i + 1]
        m = sum(window) / len(window)
        var = sum((x - m) ** 2 for x in window) / len(window)
        out.append(math.sqrt(var))
    return out
