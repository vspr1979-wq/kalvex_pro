# Kalvex Pro

Research-first intraday **long-options-only** platform for NSE and BSE, using Upstox market data, Microsoft Qlib, and optional Microsoft RD-Agent(Q) research automation.

> This repository is a research and paper/shadow-trading foundation. It does not enable live order placement by default and it does not promise profitable strategies.

## Supported scope

- Exchanges: NSE and BSE
- Index options: NIFTY, SENSEX, BANKNIFTY, FINNIFTY, and MIDCPNIFTY
- Stock options: dynamically discovered from the Upstox F&O instrument master
- Position type: long CE/PE buying only
- Intended holding: intraday; no overnight carry
- Research interval: configurable, with 5-minute defaults
- Modes: research, shadow, paper, and guarded live configuration

The application never hard-codes a stock list or a fixed RSI/EMA strategy. It derives the option universe from the broker instrument master and leaves feature/model discovery to the research workflow.

## Design

```text
Upstox history + live feed
        ↓
Canonical data and contract resolver
        ↓
Qlib custom option dataset
        ↓
Features / option surface / labels
        ↓
Model forecast
        ↓
CE/PE + expiry + strike selection
        ↓
Bid/ask-aware backtest
        ↓
Walk-forward validation
        ↓
Shadow/paper signals
        ↓
Deterministic risk gate
        ↓
Manual promotion and Upstox execution
```

RD-Agent is deliberately outside the order path. It can propose factors/models in an isolated workspace, but it cannot place orders or promote a strategy by itself.

## Repository layout

```text
configs/                         Safe research/risk defaults
src/kalvex_pro/
  config.py                      TOML configuration and validation
  models.py                      Instruments, candles, quotes, signals, trades
  instruments.py                 Upstox master parser and dynamic F&O universe
  upstox.py                      Historical/expired/chain/Greeks REST client
  qlib_bridge.py                 Canonical CSV and Qlib workflow bridge
  backtest.py                    Conservative bid/ask long-options backtester
  rdagent.py                     Sandboxed Qlib/RD-Agent bootstrap metadata
  cli.py                         Local CLI
scripts/bootstrap_research.py    Optional shallow clone of upstream repos
 tests/                           Unit tests without broker credentials
```

## Quick start

Use Python 3.10+.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'

# Validate the defaults; this makes no network requests.
kalvex validate-config configs/intraday_long_options.toml

# Check whether optional Qlib is installed.
kalvex qlib-status
```

To install the optional research stack:

```bash
pip install -e '.[research]'
```

To download the upstream research repositories into `.vendor/` (ignored by Git):

```bash
python scripts/bootstrap_research.py
```

The upstream projects are not vendored into this repository:

- Qlib: https://github.com/microsoft/qlib
- RD-Agent: https://github.com/microsoft/RD-Agent

## Instrument universe

Download the current official NSE and BSE instrument masters, then run:

```bash
kalvex download-instruments --exchange both
kalvex universe data/raw/instruments/NSE.json.gz data/raw/instruments/BSE.json.gz --as-of 2026-01-01 --max-dte 30
```

The downloader uses the official Upstox instrument-file distribution. `universe` accepts either plain JSON or gzip-compressed JSON.

The selector includes:

- Requested index option aliases
- Both CE and PE contracts
- All `OPTSTK` records when `include_fno_stocks=true`
- Only contracts in the configured DTE window
- Only NSE/BSE records

Lot sizes, strikes, expiry dates, and instrument keys are read dynamically. They are not hard-coded.

## Upstox data requirements

Set the token only in the environment or a secret manager:

```bash
cp .env.example .env
export UPSTOX_ACCESS_TOKEN='...'
```

The data client currently supports:

- V3 historical candles
- Expired-instrument historical candles for F&O backtests
- Option chain snapshots
- Option Greeks

A live WebSocket adapter and broker execution service should be enabled only after data quality and shadow-mode tests pass. No order-placement endpoint is exposed in this first implementation.

## Backtest safety

The included backtester intentionally:

- Buys at ask plus slippage
- Exits at bid minus slippage
- Uses the option lot size
- Skips entries without an ask
- Supports stop loss, take profit, and time exit
- Tracks fees and drawdown
- Does not treat candle highs/lows as executable prices

For realistic options research, preserve historical contract identity and use expired contracts. Avoid using only the currently active contract chain because that creates survivorship and contract-selection bias.

## Current status and next build slice

Implemented now:

1. Clean Python project structure
2. Dynamic NSE/BSE index and F&O-stock option universe
3. Upstox historical, expired-candle, chain, and Greeks client
4. Canonical Qlib bridge
5. Conservative bid/ask backtest primitives
6. Research-only RD-Agent bootstrap and safety policy
7. TOML configuration and unit tests

Next implementation slice should add the Upstox instrument-master downloader, binary WebSocket feed decoder, canonical quote/candle storage, option-feature pipeline, walk-forward model runner, and shadow signal service. Live order placement remains disabled until those components are validated.
