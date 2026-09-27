"""Settings — Broker / Risk / Strategies / Indicators / Session / UI.

Broker tab states VERIFIED facts (Sept 2026 docs) and explicit UNKNOWNs —
see README checklist before enabling live anything.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QLineEdit,
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
    def _broker_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(2)

        api_key = QLineEdit()
        api_key.setPlaceholderText("client_id from Upstox Developer Apps")
        api_secret = QLineEdit()
        api_secret.setEchoMode(QLineEdit.EchoMode.Password)
        api_secret.setPlaceholderText("client_secret — DPAPI-encrypted, never logged")
        redirect = QLineEdit()
        redirect.setPlaceholderText("must EXACTLY match the registered redirect URI")
        algo_name = QLineEdit()
        algo_name.setPlaceholderText="e.g. KalvexPro_v1 (configured in My Apps)"
        static_ip = QLineEdit()
        static_ip.setPlaceholderText("registered primary/secondary IP")

        lay.addWidget(section_block(
            "UPSTOX OAUTH 2.0 — VERIFIED FLOW",
            [
                form_row("API key (client_id)", api_key),
                form_row("API secret (client_secret)", api_secret),
                form_row("Redirect URI", redirect),
                form_row("Token status", QLineEdit("Not connected"),
                         hint="VERIFIED: no refresh token exists — access token "
                              "expires 03:30 IST daily; re-auth is a daily "
                              "human step (or v3 auth/token/request flow)."),
                form_row("Login", QLineEdit("— opens OAuth dialog —"),
                         hint="api.upstox.com/v2/login/authorization/dialog"),
            ],
            note="Token exchange: POST /v2/login/authorization/token "
                 "(grant_type=authorization_code). Store: Windows DPAPI.",
        ))

        sandbox = QCheckBox("Sandbox toggle (official SDK: Configuration(sandbox=True))")
        sandbox.setChecked(True)

        lay.addWidget(section_block(
            "ORDER API CONSTRAINTS — VERIFIED",
            [
                form_row("algo_name on orders", algo_name,
                         hint="VERIFIED: orders must send X-Algo-Name header "
                              "(Algo ID stays in My Apps config)."),
                form_row("Static IP", static_ip,
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
        options_on = QCheckBox("Enable index options buying (opt-in)")
        width = QSpinBox()
        width.setRange(0, 10)
        width.setValue(0)
        hold = QSpinBox()
        hold.setRange(5, 240)
        hold.setValue(45)
        hold.setSuffix(" min")
        lay.addWidget(section_block(
            "OPTIONS (V1, LIMITED)",
            [
                form_row("", options_on,
                         hint="Index options BUYING only. No multi-leg in v1."),
                form_row("Strike picker", QComboBox(),  # populated in code
                         hint="ATM / ATM ± N strikes OTM, current expiry first."),
                form_row("OTM width (strikes)", width),
                form_row("Max holding time", hold,
                         hint="theta-aware time exit is mandatory; IV/Greeks "
                              "only if the feed provides them (no invented "
                              "pricing models)."),
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
            "APPEARANCE & DEMO FEED",
            [
                form_row("Theme", theme_cb),
                form_row("Windows toast on signals", QCheckBox("On")),
                form_row("Minimize to tray on close", QCheckBox("On")),
                form_row("Confirm before kill switch", QCheckBox("On (recommended)")),
                form_row("Sim feed speed", speed,
                         hint="SIMULATED feed clock multiplier for demos/self-tests."),
            ]))
        lay.addStretch(1)
        return w
