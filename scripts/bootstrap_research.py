#!/usr/bin/env python3
"""Clone Qlib and RD-Agent into .vendor/ (ignored by Git)."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from kalvex_pro.rdagent import clone_research_repositories  # noqa: E402


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", default=".vendor")
    args = parser.parse_args()
    for command in clone_research_repositories(args.destination, run=True):
        print(" ".join(command))
