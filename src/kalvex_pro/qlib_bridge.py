"""Bridge canonical option data into a Qlib-friendly research table.

Qlib is an optional research dependency. The bridge remains importable without
Qlib so ingestion, universe selection, and tests can run in a small environment.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from .models import Candle, Instrument


def qlib_available() -> bool:
    try:
        import qlib  # noqa: F401
    except ImportError:
        return False
    return True


def qlib_columns() -> tuple[str, ...]:
    return (
        "$open",
        "$high",
        "$low",
        "$close",
        "$volume",
        "$open_interest",
        "$instrument_key",
        "$underlying_key",
        "$expiry",
        "$strike_price",
        "$option_type",
    )


def write_qlib_csv(candles: Iterable[Candle], instruments: dict[str, Instrument], output: str | Path) -> int:
    """Write a deterministic long CSV that can be used by a Qlib loader.

    The CSV is intentionally not presented as Qlib's binary provider format.
    A later data-build job can convert this canonical table into the selected
    Qlib provider backend without changing the Upstox ingestion layer.
    """
    import csv

    fieldnames = ["datetime", "instrument"] + [item.lstrip("$") for item in qlib_columns()]
    rows = []
    for candle in sorted(candles, key=lambda item: (item.timestamp, item.instrument_key)):
        instrument = instruments.get(candle.instrument_key)
        if instrument is None:
            continue
        rows.append(
            {
                "datetime": candle.timestamp.isoformat(),
                "instrument": candle.instrument_key,
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
                "open_interest": candle.open_interest,
                "instrument_key": instrument.instrument_key,
                "underlying_key": instrument.underlying_key,
                "expiry": instrument.expiry.isoformat() if instrument.expiry else "",
                "strike_price": instrument.strike_price if instrument.strike_price is not None else "",
                "option_type": instrument.option_type or "",
            }
        )
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def qlib_handler_config(csv_path: str | Path) -> dict:
    """Return a Qlib DataHandlerLP config backed by the canonical CSV."""
    return {
        "class": "DataHandlerLP",
        "module_path": "qlib.data.dataset.handler",
        "kwargs": {
            "data_loader": {
                "class": "CSVDataLoader",
                "module_path": "kalvex_pro.qlib_bridge",
                "kwargs": {"filepath": str(csv_path)},
            },
            "infer_processors": [],
            "learn_processors": [],
            "shared_processors": [],
            "drop_raw": False,
        },
    }


try:
    import pandas as _pd
    from qlib.data.dataset.loader import DataLoader as _QlibDataLoader
except ImportError:  # pragma: no cover - exercised when optional research deps are absent
    _pd = None
    _QlibDataLoader = None


if _QlibDataLoader is not None:
    class CSVDataLoader(_QlibDataLoader):
        """Qlib loader for Kalvex's canonical long CSV."""

        def __init__(self, filepath: str):
            self.filepath = filepath

        def load(self, instruments=None, start_time=None, end_time=None):
            frame = _pd.read_csv(self.filepath, parse_dates=["datetime"])
            frame = frame.rename(columns={
                "open": "$open",
                "high": "$high",
                "low": "$low",
                "close": "$close",
                "volume": "$volume",
                "open_interest": "$open_interest",
            })
            frame = frame.set_index(["datetime", "instrument"]).sort_index()
            if instruments and isinstance(instruments, (list, tuple, set)):
                frame = frame[frame.index.get_level_values("instrument").isin(instruments)]
            if start_time is not None:
                frame = frame[frame.index.get_level_values("datetime") >= _pd.Timestamp(start_time)]
            if end_time is not None:
                frame = frame[frame.index.get_level_values("datetime") <= _pd.Timestamp(end_time)]
            return frame
else:
    class CSVDataLoader:  # pragma: no cover - only a helpful error path
        def __init__(self, filepath: str):
            self.filepath = filepath

        def load(self, *args, **kwargs):
            raise ImportError("Install the 'research' extra to use CSVDataLoader with Qlib")


def qlib_workflow_config(provider_uri: str, start: str, end: str) -> dict:
    """Return a starter Qlib workflow config for option data.

    Model/label configuration remains deliberately explicit. It is unsafe to
    silently apply Qlib's equity Alpha158 handler to option contracts.
    """
    return {
        "qlib_init": {"provider_uri": provider_uri, "region": "cn"},
        "data_handler_config": {
            "start_time": start,
            "end_time": end,
            "fit_start_time": start,
            "fit_end_time": end,
            "instruments": "kalvex_options",
        },
        "notes": [
            "Use a custom option data handler for expiry, strike, option type, Greeks and bid/ask.",
            "Do not use future quote rows in feature processors.",
            "Backtest with ask-side entry and bid-side exit prices.",
        ],
    }
