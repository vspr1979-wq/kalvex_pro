"""Command-line entry points for the first Kalvex Pro release."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path
import json

from .config import load_config
from .instruments import (
    OptionsUniverse,
    UniverseRequest,
    download_instrument_master,
    load_instrument_master,
    summarize,
)
from .qlib_bridge import qlib_available, qlib_workflow_config
from .rdagent import clone_research_repositories


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kalvex", description="NSE/BSE intraday long-options research tools")
    sub = parser.add_subparsers(dest="command", required=True)

    config = sub.add_parser("validate-config", help="Validate a TOML configuration")
    config.add_argument("path", type=Path)

    download = sub.add_parser("download-instruments", help="Download official Upstox NSE/BSE instrument masters")
    download.add_argument("--exchange", choices=["NSE", "BSE", "both"], default="both")
    download.add_argument("--output-dir", type=Path, default=Path("data/raw/instruments"))

    universe = sub.add_parser("universe", help="Summarize one or more Upstox instrument masters")
    universe.add_argument("paths", type=Path, nargs="+")
    universe.add_argument("--as-of", help="ISO date used for expiry filtering")
    universe.add_argument("--max-dte", type=int, default=30)

    qlib = sub.add_parser("qlib-status", help="Show optional Qlib availability and config")
    qlib.add_argument("--provider-uri", default="data/processed/qlib")
    qlib.add_argument("--start", default="2022-01-01")
    qlib.add_argument("--end", default="2026-12-31")

    bootstrap = sub.add_parser("bootstrap-research", help="Prepare shallow clones outside Git")
    bootstrap.add_argument("--destination", type=Path, default=Path(".vendor"))
    bootstrap.add_argument("--run", action="store_true", help="Actually clone the repositories")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate-config":
        config = load_config(args.path)
        print(json.dumps(asdict(config), indent=2, default=str))
        return 0
    if args.command == "download-instruments":
        exchanges = ["NSE", "BSE"] if args.exchange == "both" else [args.exchange]
        for exchange in exchanges:
            path = download_instrument_master(exchange, args.output_dir / f"{exchange}.json.gz")
            print(path)
        return 0
    if args.command == "universe":
        from datetime import date

        instruments = load_instrument_master(args.path)
        request = UniverseRequest(
            as_of=date.fromisoformat(args.as_of) if args.as_of else None,
            maximum_days_to_expiry=args.max_dte,
        )
        selected = OptionsUniverse(instruments).select(request)
        print(json.dumps({"contracts": len(selected), "summary": summarize(selected)}, indent=2))
        return 0
    if args.command == "qlib-status":
        print(
            json.dumps(
                {
                    "qlib_available": qlib_available(),
                    "workflow": qlib_workflow_config(args.provider_uri, args.start, args.end),
                },
                indent=2,
            )
        )
        return 0
    if args.command == "bootstrap-research":
        commands = clone_research_repositories(args.destination, run=args.run)
        for command in commands:
            print(" ".join(command))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
