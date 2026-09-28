"""Safe integration metadata for Microsoft's RD-Agent(Q)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess


QLIB_REPOSITORY = "https://github.com/microsoft/qlib.git"
RDAGENT_REPOSITORY = "https://github.com/microsoft/RD-Agent.git"


@dataclass(frozen=True)
class ResearchSandbox:
    """Policy for an RD-Agent research run.

    This object only creates a command plan. It never places orders and never
    receives a brokerage token.
    """

    workspace: Path
    max_iterations: int = 10
    allow_network: bool = False
    allow_order_placement: bool = False

    def validate(self) -> None:
        if self.max_iterations < 1:
            raise ValueError("max_iterations must be positive")
        if self.allow_order_placement:
            raise ValueError("RD-Agent cannot be granted order-placement permission")

    def environment(self) -> dict[str, str]:
        self.validate()
        return {
            "KALVEX_RESEARCH_ONLY": "true",
            "KALVEX_LIVE_TRADING_ENABLED": "false",
            "KALVEX_RDAGENT_MAX_ITERATIONS": str(self.max_iterations),
        }


def clone_research_repositories(destination: str | Path, run: bool = False) -> list[list[str]]:
    """Return, or optionally run, shallow clone commands for the two upstream repos."""
    root = Path(destination)
    commands = [
        ["git", "clone", "--depth", "1", QLIB_REPOSITORY, str(root / "qlib")],
        ["git", "clone", "--depth", "1", RDAGENT_REPOSITORY, str(root / "RD-Agent")],
    ]
    if run:
        root.mkdir(parents=True, exist_ok=True)
        for command in commands:
            subprocess.run(command, check=True)
    return commands


def quant_run_command() -> list[str]:
    """Canonical upstream entry point; the options data handler remains ours."""
    return ["rdagent", "fin_quant"]
