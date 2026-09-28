# Upstream repositories

Kalvex Pro uses the upstream projects as optional research dependencies rather than copying their source into this repository.

```bash
python scripts/bootstrap_research.py
```

This creates ignored shallow clones:

- `.vendor/qlib`
- `.vendor/RD-Agent`

The current bootstrap URLs are:

- `https://github.com/microsoft/qlib.git`
- `https://github.com/microsoft/RD-Agent.git`

Qlib should be used with a custom option data handler. Its standard equity handlers are not sufficient for expiry, strike, Greeks, bid/ask, and option contract lifecycle. RD-Agent should be run in a sandbox with `KALVEX_LIVE_TRADING_ENABLED=false` and no Upstox order token.
