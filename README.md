# Kalvex Pro — UI Layout Skeleton

Windows 11 desktop trading workstation for **one adult retail trader**, **Upstox only**.

> **This repository currently contains an EMPTY UI LAYOUT only.**
> No broker connectivity, no order placement, no market data, no strategy logic.
> This is a specification/UI artifact — **not live trading advice**.
> **Paper trading is the default mode**; live auto-trading is a later opt-in phase.

## Run (Windows 11, Python 3.11+)

```powershell
py -3.11 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python main.py
```

Designed for a minimum resolution of **1366x768** (window min 1280x720, default 1500x860).

## Layout map

```
main.py                      entry point
kalvex/
  core/constants.py          app constants, bot modes, page ids, v1 strategy names
  app.py                     QApplication + dark theme
  ui/
    theme.py                 dark QSS (single source of colors)
    main_window.py           window shell + system tray + IST status clock
    top_bar.py               connection • funds • live P&L • bot state • mode • KILL SWITCH
    nav_sidebar.py           Dashboard | Charts | Strategies | Positions/Orders | Logs | Settings
    widgets.py               page header, metric card, placeholder panel, form rows, tables
    pages/
      dashboard_page.py      KPI cards, recent signals, session, guard rails
      charts_page.py         symbol/timeframe bar, chart placeholder, overlays, markers legend
      strategies_page.py     strategy table (on/off, mode, positions, P&L, start/stop/edit)
      activity_page.py       Positions | Orders | Trades tables (IST timestamps)
      logs_page.py           level/source filters + event table (no secrets in logs)
      settings_page.py       Broker | Risk | Strategies | Indicators | Session hours | UI
```

## What is intentionally empty / placeholder

- All data cells are `—`; tables are empty except clearly static sample rows (v1 strategy names).
- Chart canvas is a dashed placeholder for `lightweight-charts-python` (fallback `pyqtgraph`).
- Broker fields (OAuth, algo tags, static IP) are placeholders — **nothing is sent anywhere**.
- Bot mode selector: **Paper** default; **Semi-auto** selectable; **Auto is disabled/locked**
  until Paper mode has been used (and the later live opt-in phase).
- Kill switch and tray menu show confirmation dialogs only — they cancel nothing yet.

## Must be re-verified against CURRENT Upstox docs before coding (unknowns marked UNKNOWN)

- [ ] OAuth 2.0 flow: API key/secret/redirect URI, access + refresh token, scopes
- [ ] Token storage: Windows DPAPI (never plaintext) + refresh-on-expiry behaviour
- [ ] Whether a **static IP must be registered** for the order API (and for which segments)
- [ ] **algo_id / algo_name / strategy tag** requirements on orders (form, field names, registration)
- [ ] Current **order-rate limits** (e.g. 10 orders/sec baseline) and registered-algo product exceptions
- [ ] Order types actually allowed for algo/API: Limit, SL-L, GTT availability, raw MARKET — UNKNOWN until confirmed
- [ ] Whether **MCX/commodities** orders are accepted at all (out of scope for v1 otherwise)
- [ ] Websocket feed: authorize payload, protobuf schema, LTP/quote/depth, IV & Greeks availability
- [ ] Positions/orders/trades endpoints for state recovery after restart
- [ ] Sandbox / safe-testing facilities offered by Upstox (toggle behaviour)
- [ ] Index options order constraints: lot sizes, strike/exercise rules, freeze quantity limits

## Planned architecture (next phases — not in this build)

- UI thread (Qt) vs bot worker (QThread) vs websocket thread (QThread), signals/slots only.
- `PaperEngine` and `LiveBrokerAdapter` share one interface so strategies are mode-agnostic.
- SQLite tables: `settings`, `strategies`, `signals`, `orders`, `trades`, `positions`, `logs`, `bot_state`.
- Restart recovery from DB + broker positions — never duplicate orders.
- Risk: hard-coded ceilings + user settings; daily max loss → flatten + stop; kill switch = cancel + flatten + stop.
