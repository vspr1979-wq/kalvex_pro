"""Settings — Broker / Risk / Strategies / Indicators / Session / UI.

Broker tab states VERIFIED facts (Sept 2026 docs) and explicit UNKNOWNs —
see README checklist before enabling live anything.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from kalvex.ui.widgets import form_row, page_header, section_block


def _scrollable(content: QWidget) -> QWidget:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(content)
    return scroll


class SettingsPage(QWidget):
    connect_requested = Signal()
    disconnect_requested = Signal()
    fetch_master_clicked = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 12)
        root.setSpacing(10)

        root.addWidget(page_header(
            "Settings",
            "Hard-coded risk ceilings always cap the values below."))

        tabs = QTabWidget()
        tabs.addTab(_scrollable(self._broker_tab()), "Broker")
        tabs.addTab(_scrollable(self._risk_tab()), "Risk")
        tabs.addTab(_scrollable(self._strategies_tab()), "Strategies")
        tabs.addTab(_scrollable(self._indicators_tab()), "Indicators")
        tabs.addTab(_scrollable(self._session_tab()), "Session hours")
        tabs.addTab(_scrollable(self._ui_tab()), "UI")
        root.addWidget(tabs, stretch=1)

    # ------------------------------------------------------------------ #
    # broker connection helpers
    # ------------------------------------------------------------------ #
    def _connection_row(self) -> QWidget:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.connect_btn = QPushButton("CONNECT / RE-LOGIN…")
        self.connect_btn.setObjectName("ember")
        self.connect_btn.clicked.connect(self.connect_requested.emit)
        self.disconnect_btn = QPushButton("DISCONNECT")
        self.disconnect_btn.setObjectName("ghost")
        self.disconnect_btn.clicked.connect(self.disconnect_requested.emit)
        lay.addWidget(self.connect_btn)
        lay.addWidget(self.disconnect_btn)
        lay.addStretch(1)
        return row

    def broker_config(self) -> dict:
        return {
            "client_id": self.api_key.text().strip(),
            "client_secret": self.api_secret.text().strip(),
            "redirect_uri": self.redirect.text().strip(),
            "algo_name": self.algo_name.text().strip(),
            "static_ip": self.static_ip.text().strip(),
        }

    def set_broker_fields(self, cfg: dict) -> None:
        self.api_key.setText(cfg.get("client_id", ""))
        self.api_secret.setText(cfg.get("client_secret", ""))
        self.redirect.setText(cfg.get("redirect_uri", ""))
        self.algo_name.setText(cfg.get("algo_name", ""))
        self.static_ip.setText(cfg.get("static_ip", ""))

    def _master_row(self) -> QWidget:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lay.addWidget(self.fetch_master_btn)
        lay.addStretch(1)
        return row

    def set_master_status(self, text: str) -> None:
        self.master_status.setText(text)

    def set_broker_status(self, describe: str, connected: bool) -> None:
        self.token_status.setText(describe)
        self.token_status.setStyleSheet(
            f"color: {'#35D0C8' if connected else '#E8EEF6'};")
        self.disconnect_btn.setEnabled(connected)

    # ------------------------------------------------------------------ #
    def _broker_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(2)

        self.api_key = QLineEdit()
        self.api_key.setPlaceholderText("client_id from Upstox Developer Apps")
        self.api_secret = QLineEdit()
        self.api_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_secret.setPlaceholderText("client_secret — DPAPI-encrypted, never logged")
        self.redirect = QLineEdit()
        self.redirect.setPlaceholderText("must EXACTLY match the registered redirect URI")
        self.algo_name = QLineEdit()
        self.algo_name.setPlaceholderText("e.g. KalvexPro_v1 (configured in My Apps)")
        self.static_ip = QLineEdit()
        self.static_ip.setPlaceholderText("registered primary/secondary IP")
        self.token_status = QLineEdit("DISCONNECTED")
        self.token_status.setReadOnly(True)

        lay.addWidget(section_block(
            "UPSTOX OAUTH 2.0 — VERIFIED FLOW",
            [
                form_row("API key (client_id)", self.api_key),
                form_row("API secret (client_secret)", self.api_secret),
                form_row("Redirect URI", self.redirect),
                form_row("Token status", self.token_status,
                         hint="VERIFIED: no refresh token exists — access token "
                              "expires 03:30 IST daily; re-auth is a daily "
                              "human step (or v3 auth/token/request flow)."),
                form_row("Connection", self._connection_row(),
                         hint="Opens the verified OAuth dialog "
                              "(api.upstox.com/v2/login/authorization/dialog). "
                              "Disconnect wipes the DPAPI token."),
            ],
            note="Token exchange: POST /v2/login/authorization/token "
                 "(grant_type=authorization_code). Store: Windows DPAPI.",
        ))

        self.fetch_master_btn = QPushButton("FETCH INSTRUMENT MASTER FROM UPSTOX")
        self.fetch_master_btn.clicked.connect(self.fetch_master_clicked.emit)
        self.master_status = QLineEdit("not loaded")
        self.master_status.setReadOnly(True)
        lay.addWidget(section_block(
            "INSTRUMENTS — LIVE FROM UPSTOX (verified endpoint)",
            [
                form_row("Instrument master", self._master_row()),
                form_row("Status", self.master_status,
                         hint="GET https://assets.upstox.com/market-quote/"
                              "instruments/exchange/complete.json — public, no "
                              "auth. Contains exchange keys, lot sizes, strikes. "
                              "Nothing is synthesised when the fetch fails."),
            ]))

        sandbox = QCheckBox("Sandbox toggle (official SDK: Configuration(sandbox=True))")
        sandbox.setChecked(True)

        lay.addWidget(section_block(
            "ORDER API CONSTRAINTS — VERIFIED",
            [
                form_row("algo_name on orders", self.algo_name,
                         hint="VERIFIED: orders must send X-Algo-Name header "
                              "(Algo ID stays in My Apps config)."),
                form_row("Static IP", self.static_ip,
                         hint="VERIFIED: Place/Modify/Cancel/GTT/Exit-All are "
                              "restricted to registered static IPs."),
                form_row("Sandbox mode", sandbox),
                form_row("Rate limits", QLineEdit("10/sec · 500/min · 2000/30min"),
                         hint="VERIFIED (order APIs). SEBI-registered algos: "
                              "50/sec after exchange registration. App "
                              "throttles at 10/sec regardless."),
                form_row("Order types", QLineEdit("LIMIT · SL · SL-M"),
                         hint="UNKNOWN whether raw MARKET is allowed for algo/"
                              "API — the live adapter refuses MARKET until "
                              "confirmed. GTT schema UNKNOWN."),
            ],
            note="MCX/commodities: out of scope for v1 (UNKNOWN whether API "
                 "accepts MCX orders).",
        ))
        lay.addStretch(1)
        return w

    # ------------------------------------------------------------------ #
    def _risk_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(2)

        def spin(lo, hi, val, suffix="", prefix="", dec=1):
            if dec == 1:
                s = QDoubleSpinBox()
                s.setRange(lo, hi)
                s.setValue(val)
                s.setSingleStep(0.1)
            else:
                s = QSpinBox()
                s.setRange(int(lo), int(hi))
                s.setValue(int(val))
            if suffix:
                s.setSuffix(suffix)
            if prefix:
                s.setPrefix(prefix)
            return s

        capital = spin(10_000, 100_000_000, 500_000, prefix="₹ ", dec=0)
        risk_pct = spin(0.1, 2.0, 1.0, suffix=" %",
                        )  # hard cap 2%
        max_pos = spin(1, 6, 3, dec=0)
        max_lots = spin(1, 10, 2, dec=0)
        max_om = spin(1, 60, 20, dec=0)
        daily_loss = spin(0, 1_000_000, 5000, prefix="₹ ", dec=0)
        profit_stop = spin(0, 1_000_000, 10000, prefix="₹ ", dec=0)
        trail_after = spin(0, 1_000_000, 500, prefix="₹ ", dec=0)
        margin_factor = spin(0.05, 1.0, 0.20, suffix=" × notional")
        square_off = QTimeEdit()
        square_off.setDisplayFormat("HH:mm")
        square_off.setTime(square_off.time().fromString("15:15", "HH:mm"))
        ps_on = QCheckBox("Enable daily profit stop")
        auto_tune = QCheckBox("Auto-apply self-improvement suggestions (within bands)")

        lay.addWidget(section_block(
            "CAPITAL & PER-TRADE",
            [
                form_row("Trading capital", capital),
                form_row("Max risk per trade", risk_pct,
                         hint="HARD CAP 2.0% — the editor cannot exceed it."),
                form_row("Margin factor (paper)", margin_factor,
                         hint="PLACEHOLDER — live margins must come from the "
                              "broker (UNKNOWN %)."),
            ]))
        lay.addWidget(section_block(
            "CEILINGS (HARD-CODED IN THE ENGINE)",
            [
                form_row("Max open positions", max_pos, hint="hard cap 6"),
                form_row("Max lots per order", max_lots, hint="hard cap 10"),
                form_row("Max orders per minute", max_om,
                         hint="hard cap 60/min AND ≤10/sec (broker)."),
                form_row("Daily max loss", daily_loss,
                         hint="→ flatten + stop bot (hard 5% of capital)."),
                form_row("Daily profit stop", profit_stop),
                form_row("", ps_on),
                form_row("Trailing SL arms after", trail_after),
                form_row("Square-off time (IST)", square_off),
                form_row("Self-improvement", auto_tune),
            ]))
        lay.addStretch(1)
        return w

    # ------------------------------------------------------------------ #
    def _strategies_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(2)
        lay.addWidget(section_block(
            "V1 STRATEGY SET (ONLY THESE)",
            [
                form_row("Opening Range Breakout", QCheckBox("Enabled (index / liquid F&O)")),
                form_row("EMA Crossover + VWAP", QCheckBox("Enabled")),
                form_row("Supertrend Trend-Follow", QCheckBox("Enabled")),
                form_row("RSI Mean-Reversion", QCheckBox("Enabled (cash / futures only)")),
            ],
            note="Per-strategy parameters live on the Strategies page "
                 "(editable within hard tune bands)."))
        self.options_enabled = QCheckBox("Enable index options buying (opt-in)")
        self.options_underlying = QComboBox()
        self.options_underlying.addItems(["NIFTY", "SENSEX", "BANKNIFTY",
                                          "FINNIFTY", "MIDCAPNIFTY"])
        self.options_otm_width = QSpinBox()
        self.options_otm_width.setRange(0, 10)
        self.options_otm_width.setValue(0)
        self.options_expiry = QComboBox()
        self.options_expiry.addItems(["current", "next"])
        hold = QSpinBox()
        hold.setRange(5, 240)
        hold.setValue(45)
        hold.setSuffix(" min")
        lay.addWidget(section_block(
            "OPTIONS (V1, LIMITED) — CONTRACTS FROM UPSTOX",
            [
                form_row("", self.options_enabled,
                         hint="Index options BUYING only. No multi-leg in v1."),
                form_row("Underlying index", self.options_underlying,
                         hint="NIFTY / SENSEX / BANKNIFTY / FINNIFTY / "
                              "MIDCAPNIFTY — resolved against the Upstox "
                              "instrument master (MIDCAPNIFTY trades as "
                              "MIDCPNIFTY on NSE)."),
                form_row("OTM width (strikes)", self.options_otm_width),
                form_row("Expiry", self.options_expiry,
                         hint="current / next expiry from Upstox contract rows."),
                form_row("Max holding time", hold,
                         hint="theta-aware time exit is mandatory; IV/Greeks "
                              "only if the feed provides them (no invented "
                              "pricing models)."),
            ]))

        self.live_enabled = QCheckBox(
            "Enable LIVE order routing (real orders via Upstox)")
        lay.addWidget(section_block(
            "EXECUTION",
            [
                form_row("", self.live_enabled,
                         hint="Off by default. Live routing also requires a "
                              "connected broker and switching the top-bar "
                              "mode to Semi-auto/Auto with explicit "
                              "confirmation. Hard risk ceilings always apply."),
            ]))
        lay.addStretch(1)
        return w

    # ------------------------------------------------------------------ #
    def _indicators_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(2)
        lay.addWidget(section_block(
            "INDICATORS (IN-HOUSE MATH; PANDAS-TA ADAPTER LATER)",
            [
                form_row("EMA", QCheckBox("On (fast/slow)"),
                         hint="defaults 9/21 — band-locked on Strategies page"),
                form_row("VWAP", QCheckBox("On (session-anchored)")),
                form_row("Supertrend", QCheckBox("On (ATR 10 x 3.0)")),
                form_row("RSI", QCheckBox("On (Wilder 14, 70/30)")),
                form_row("Bollinger squeeze (later)", QCheckBox("Off")),
                form_row("MACD (later)", QCheckBox("Off")),
                form_row("SMC overlay (later)", QCheckBox("Off"),
                         hint="smartmoneyconcepts = research overlay/alert "
                              "only, never sole live strategy."),
            ]))
        lay.addStretch(1)
        return w

    # ------------------------------------------------------------------ #
    def _session_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(2)

        def t(hhmm):
            e = QTimeEdit()
            e.setDisplayFormat("HH:mm")
            e.setTime(e.time().fromString(hhmm, "HH:mm"))
            return e

        lay.addWidget(section_block(
            "SESSION (IST)",
            [
                form_row("Pre-market warm-up", t("09:00")),
                form_row("Market open", t("09:15")),
                form_row("Market close", t("15:30")),
                form_row("Square-off", t("15:15")),
                form_row("Unattended operation",
                         QCheckBox("Only during session hours")),
            ],
            note="The bot never runs unattended outside session hours, and "
                 "unattended Auto requires Paper use first."))
        lay.addStretch(1)
        return w

    # ------------------------------------------------------------------ #
    def _ui_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(2)
        theme_cb = QComboBox()
        theme_cb.addItems(["Ember Terminal (dark)"])
        speed = QSpinBox()
        speed.setRange(1, 120)
        speed.setValue(5)
        speed.setSuffix("× realtime")
        lay.addWidget(section_block(
            "APPEARANCE & FEED",
            [
                form_row("Theme", theme_cb),
                form_row("Windows toast on signals", QCheckBox("On")),
                form_row("Minimize to tray on close", QCheckBox("On")),
                form_row("Confirm before kill switch", QCheckBox("On (recommended)")),
                form_row("Chart refresh", speed,
                         hint="UI redraw cadence (data cadence is the live "
                              "Upstox quote poll)."),
            ]))
        lay.addStretch(1)
        return w
