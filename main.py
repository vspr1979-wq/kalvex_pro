"""Kalvex Pro — entry point.

Paper trading is the DEFAULT. Live auto-trading is an opt-in phase behind
hard risk limits. This is a spec-driven tool, not trading advice.

Run:
    python main.py               # GUI (sim feed demo; broker connect in Settings)
    python main.py --selftest    # headless engine self-test (no GUI)
"""

import sys

if sys.version_info < (3, 11):
    raise SystemExit("Kalvex Pro requires Python 3.11+")

if __name__ == "__main__":
    if "--selftest" in sys.argv:
        from kalvex.selftest import main as selftest_main
        raise SystemExit(selftest_main())
    from kalvex.app import run
    raise SystemExit(run())
