"""Kalvex Pro — entry point (UI layout skeleton).

PAPER TRADING DEFAULT. This build is UI layout only: no broker
connectivity, no order placement, no market data, no strategy logic.
Run:  python main.py
"""

import sys

if sys.version_info < (3, 11):
    raise SystemExit("Kalvex Pro requires Python 3.11+")

from kalvex.app import run  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(run())
