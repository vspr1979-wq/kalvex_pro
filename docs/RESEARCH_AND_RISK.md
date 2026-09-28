# Research and risk contract

## Target

The target is intraday buying of NSE/BSE call and put options. The system must not write options, short options, carry positions overnight, or silently place an order because an LLM produced a candidate.

## Labels

A model should be evaluated against net option outcomes, not only underlying direction. Candidate labels include:

- Forward option mid/bid return after a fixed number of bars
- Net return after ask-side entry, bid-side exit, fees, and slippage
- Probability of reaching take profit before stop loss
- Maximum favorable and adverse excursion

## Candidate features

Features can combine underlying bars, contract metadata, and option-surface observations:

- Underlying returns, range, VWAP distance, realized volatility, volume
- Moneyness, delta, gamma, theta, vega, IV and IV change
- OI, OI change, volume/OI, spread and available depth
- Expiry, minutes to square-off, time of day, and regime

All feature timestamps must represent information available before the trade decision. The option chain and quote snapshots must be versioned so that later revisions cannot leak into an earlier decision.

## Validation gates

A strategy is not promoted because its in-sample return is high. It must pass:

1. Date-based walk-forward train/validation/test splits.
2. No random row split across the same trading day.
3. Exact historical contract and expiry reconstruction.
4. Ask-side entry and bid-side exit assumptions.
5. Costs, slippage, latency, lot sizes, and liquidity constraints.
6. Holdout performance across multiple volatility regimes.
7. Paper/shadow performance before any live order permission.
8. Reproducible dataset, code, model, and configuration hashes.

## Deterministic live controls

The risk gate must reject a signal if any of these are true:

- Feed is stale or disconnected.
- Contract is not in the approved universe.
- Spread or quote depth is outside the configured limit.
- Entry time is after the configured cutoff.
- Position or lot limit would be exceeded.
- Daily loss, consecutive-loss, or exposure limit is exceeded.
- The strategy version is not manually promoted.
- Broker account/order state cannot be reconciled.

A kill switch must be available independently of the model and RD-Agent.

## Upstream references

- Qlib: https://github.com/microsoft/qlib
- RD-Agent: https://github.com/microsoft/RD-Agent
- Upstox historical and expired-instrument APIs: https://upstox.com/developer/api-documentation/backtesting/
- Upstox option chain: https://upstox.com/developer/api-documentation/get-pc-option-chain/
