# Kalvex Pro — Ember Terminal

Windows 11 desktop algo-trading workstation for **one adult retail trader**,
**Upstox only**. Paper trading is the DEFAULT; live auto-trading is a later
opt-in behind hard risk limits.

> **This is a specification/tooling artifact — not live trading advice.**
> Production app: **no synthetic market data anywhere in the GUI** —
> quotes, instruments, chains and lot sizes all come from Upstox.
> The engine runs end-to-end in **Paper mode** on live quotes; a
> deterministic sim feed exists only as the `--selftest` harness.
> The live adapter implements only **verified** Upstox request shapes and
> refuses everything marked UNKNOWN.

## Run (Windows 11, Python 3.11+)

```powershell
py -3.11 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python main.py              # GUI — press START BOT (Paper)
.venv\Scripts\python main.py --selftest   # headless engine self-test
```

Designed for minimum 1366x768. The self-test clock is accelerated
(see Settings → UI → sim feed speed) so the decision loop is visible.

## What the bot does (fully automated, transparent)

```
tick → ANALYSE → DECIDE → SIZE → EXECUTE → MANAGE → REVIEW
        │          │        │        │          │        │
        │          │        │        │          │        └─ bounded self-tuning
        │          │        │        │          └─ SL/target/trailing/theta time
        │          │        │        └─ paper fill / semi confirm / live adapter
        │          │        └─ capital×risk%/(entry−SL), lots, margin, ceilings
        │          └─ 4 rule-based strategies, each with a reasoning chain
        └─ EMA/VWAP/Supertrend/RSI structure (narrated per closed bar)
```

Every step is written to the `decision_log` table with human-readable
reasoning ("thoughts") and streamed live into the UI **Decision Stream** and
**Bot Brain** pages. There is no black-box ML: signals are rule-based,
self-improvement only moves soft parameters inside hard-coded bands
(`TUNE_BANDS`), never risk ceilings, and a strategy with 5+ consecutive
losses is auto-disabled pending manual re-arm.

### v1 strategy set (exactly four)
| Key | Strategy | Notes |
|---|---|---|
| `orb` | Opening Range Breakout | index / liquid F&O; one-shot per direction per day |
| `ema_vwap` | EMA crossover + VWAP filter | SL = ATR multiple; RR target |
| `supertrend` | Supertrend trend-follow | flip entries, ATR anchor |
| `rsi_mr` | RSI mean-reversion | cash/futures only in v1 |

Nice-to-have later (overlay/alert only, never sole live entry): Bollinger
squeeze, MACD momentum, SMC FVG/OB/BOS/CHoCH (smartmoneyconcepts).

### Modes & execution target (real switching)

| Mode | Behaviour |
|------|-----------|
| **Paper** (default) | Simulated fills from live Upstox quotes. Always available. |
| **Semi-auto** | Signal + explicit confirm dialog before each order. |
| **Auto** | Unattended. Locked until Paper has been used AND the broker is connected; enabling live routing requires an additional explicit Yes. |

Orders route LIVE only when: mode ∈ {Semi-auto, Auto} **and** broker CONNECTED
**and** the live opt-in is on. Otherwise they stay paper. Hard risk ceilings
apply in every mode.

### Options (v1, opt-in — data from Upstox)

Underlyings: NIFTY · SENSEX · BANKNIFTY · FINNIFTY · MIDCAPNIFTY (resolved
against the Upstox instrument master — MIDCAPNIFTY trades as MIDCPNIFTY).
Strikes/lot sizes come from `GET /v2/option/contract` rows; nothing is
synthesised — if the chain cannot be fetched the trade is refused.
Index options **buying only**; strike picker ATM / ATM±N OTM, current expiry
first; qty from risk sizing rounded to exchange lot size; forced max holding
time (theta-aware time exit); IV & Greeks displayed only when the feed
provides them (`option_greeks` mode) — **no invented pricing models**.

### Risk (hard ceilings in `kalvex/core/risk.py` — UI cannot raise them)
per-trade ≤ 2% capital (user default 1%) · ≤ 6 open positions · ≤ 10 lots ·
orders ≤ 10/sec (Upstox verified) and ≤ user per-min cap · daily max loss →
flatten + stop · optional profit stop · trailing SL only after min profit ·
square-off 15:15 IST · **kill switch = cancel + flatten + stop**.

## Architecture

```
UI thread (PySide6)                      Bot thread (QThread)
┌──────────────────────────┐   signals   ┌────────────────────────────┐
│ TopBar · Nav · Pages     │◄───────────►│ BotWorker._cycle()         │
│  Dashboard (stream)      │             │  strategies → risk → broker│
│  Charts (QPainter candles│             │  manage → review loop      │
│  Bot Brain (pipeline)    │             └──────────┬─────────────────┘
│  Strategies/Activity/    │                        │ lock-guarded
│  Logs/Settings · Tray    │             ┌──────────▼─────────────────┐
└──────────┬───────────────┘             │ BrokerInterface            │
           │                             │  PaperEngine  (complete)   │
           │                             │  LiveBrokerAdapter (v2/v3) │
           │                             └──────────┬─────────────────┘
┌──────────▼───────────────────────────────────────▼─────────────────┐
│ FeedProvider: SimFeedProvider (deterministic) │ UpstoxFeedProvider  │
│ Database (SQLite/WAL): settings strategies signals orders trades    │
│ positions logs bot_state decision_log reviews                       │
└─────────────────────────────────────────────────────────────────────┘
```

* **PaperEngine and LiveBrokerAdapter share one interface** so strategies
  are mode-agnostic; Paper is complete and self-tested, Live only sends
  verified shapes.
* **Disconnects**: paper engine never disconnects; live websocket loop must
  reconnect with backoff (worker thread) and re-sync via positions/orders
  endpoints.
* **Token expiry**: Upstox access tokens expire **03:30 IST daily and there
  is no refresh token** (verified) — the app re-auths via the OAuth dialog
  and refuses to trade without a valid token.
* **Partial fills**: PaperEngine tracks `PARTIAL` status and avg fill price;
  position bookkeeping uses signed quantities.
* **Restart recovery**: state rebuilds from SQLite (`bot_state`, `positions`,
  open `orders`); orders carry a client tag (`KLV-…`) used as a dedupe key —
  a recovered order is re-adopted, never re-placed.

## SQLite schema (see `kalvex/core/db.py` for DDL)

`settings` · `strategies` · `signals` · `decision_log` · `orders` · `trades` ·
`positions` · `logs` · `bot_state` · `reviews` — all timestamps IST.

## Security plan

* Tokens encrypted with **Windows DPAPI** (`CryptProtectData`, per-user) —
  never plaintext on disk (`kalvex/core/security.py`).
* Secrets/tokens are **redacted** before any log write; logs never contain
  `client_secret`, `access_token`, or `Authorization` values.
* API secret lives only in the DPAPI store; the Settings field is a masked
  input.
* Kill switch, daily loss circuit and hard ceilings are engine-side, not
  UI-side.

## Instruments & market data (all from Upstox)

1. **Instrument master** — `GET https://assets.upstox.com/market-quote/instruments/exchange/complete.json`
   (public, gzip-aware), cached at `data/instrument_master.json`. Index keys,
   lot sizes, tick sizes, expiries and option rows are resolved from it.
2. **Quotes** — `GET /v2/market-quote/quotes?instrument_key=K1,K2` polled at
   1 Hz; 1-minute bars accumulated in-app. On API errors the feed reports
   `stale` — it never invents prices.
3. **Option contracts / chain** — `GET /v2/option/contract` and
   `GET /v2/option/chain?instrument_key=...&expiry_date=YYYY-MM-DD`.
4. **Websocket feed** — verified auth/sub/decode flow in
   `UpstoxWebsocketFeed`; requires the official `MarketDataFeed_pb2` proto
   compiled (`protobuf`); until then it raises rather than fake data.

Unresolved instruments show `UNKNOWN` and are blocked from trading.

## Broker connect / disconnect (verified OAuth flow)

The top-bar **BROKER** chip and **CONNECT/DISCONNECT** button (also on
Settings → Broker) drive a real session state machine
(`kalvex/core/session.py`):

1. **CONNECT** opens a dialog: API key / secret / redirect URI / algo name →
   `OPEN UPSTOX LOGIN IN BROWSER` (verified dialog URL) → paste the
   redirect URL (or just the `code`) → **CONNECT** exchanges it at the
   verified `POST /v2/login/authorization/token` endpoint.
2. The token is stored with **Windows DPAPI** and its expiry is computed
   from the verified rule: **03:30 IST the next day — no refresh token**,
   so re-login is a daily step. The chip shows
   `UPSTOX · CONNECTED · until …` (or `TOKEN EXPIRED` after cut-off).
3. **DISCONNECT** wipes the token — live routing becomes impossible until
   the next login. Paper trading keeps working either way.
4. On connect the app best-effort fetches funds to fill the FUNDS chip;
   failures are logged, never fatal.

States: `DISCONNECTED · CONNECTING · CONNECTED · EXPIRED · ERROR` —
all covered by the offline self-test (fake token exchanger, no network).

## Upstox verification status (docs checked Sept 2026)

VERIFIED — implemented as documented:
- [x] OAuth 2.0 authorization-code flow:
      `GET /v2/login/authorization/dialog` → `POST /v2/login/authorization/token`
      (code, client_id, client_secret, redirect_uri, grant_type=authorization_code)
- [x] **No refresh token** — access token expires 03:30 IST daily (plan daily re-auth;
      v3 `POST /v3/login/auth/token/request/{client_id}` exists for near-unattended flows)
- [x] Order rate limits: **10/sec, 500/min, 2000/30-min** for order APIs
      (50/sec only for SEBI-registered algos; registration required >10/sec)
- [x] **X-Algo-Name header** required on order placement (Algo ID stays in My Apps)
- [x] **Static IP registration** required for Place/Modify/Cancel/GTT/Exit-All
- [x] `PlaceOrderV3Request` fields (official SDK): quantity, product, validity,
      price, tag, instrument_token, order_type, transaction_type,
      disclosed_quantity, trigger_price, is_amo, slice + `algo_name` kwarg
- [x] Market data websocket: `WebsocketApi.get_market_data_feed_authorize('2.0')`
      → connect `authorized_redirect_uri` → JSON sub
      `{"guid":…, "method":"sub", "data":{"mode":"ltpc|quote|full|option_greeks",
      "instrumentKeys":[…]}}` → protobuf `FeedResponse` frames

UNKNOWN — do not code against until confirmed:
- [ ] Whether raw **MARKET** orders are permitted for algo/API accounts
      (the live adapter refuses MARKET; it sends LIMIT / SL / SL-M only)
- [ ] Product-code enum for your segments ("D"/"I" seen in SDK material)
- [ ] **GTT order request schema**
- [ ] MCX/commodities order support via API (out of scope for v1 regardless)
- [ ] Exact **MarketDataFeed .proto** version — download from Upstox docs and
      compile to `MarketDataFeed_pb2` (decoder raises until present)
- [ ] Exchange **lot sizes / strike steps** (placeholder config — verify
      against the current contract master before live)
- [ ] Live **margin percentages** (paper uses a configurable margin factor)
- [ ] WebSocket reconnect/heartbeat semantics and subscription quotas

## UI — "Ember Terminal"

Dark cockpit aesthetic (ink + ember accent, monospace numerals, hairline
panels). Top command strip: feed/funds/P&L chips, bot state, mode selector
(Paper default · Semi-auto · Auto locked until Paper used), START/STOP and
**KILL SWITCH**. Left rail: Dashboard · Charts · Bot Brain · Strategies ·
Positions/Orders · Logs · Settings. Tray: show/hide, start/stop, flatten all,
kill switch. All times IST.

## Tests

`python main.py --selftest` drives the full loop on synthetic data and
checks: journal completeness, signal generation, sizing math vs
capital×risk%/(entry−SL), 10/sec throttle, daily-loss flatten, kill switch,
restart dedupe, and bounded self-improvement (tune values stay inside
`TUNE_BANDS`; 5-loss auto-disable).
