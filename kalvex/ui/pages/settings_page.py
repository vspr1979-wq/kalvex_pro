"""Settings page — Broker / Risk / Strategies / Indicators / Session hours / UI.

Layout only: fields are placeholders and nothing is persisted yet.
Anything marked UNKNOWN must be re-verified against current Upstox docs
before implementation (see README checklist).
"""

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

from kalvex.ui.widgets import (
    form_row,
    hint_label,
    page_header,
    section_block,
)


def _scrollable(content: QWidget) -> QWidget:
    """Wrap tab content in a scroll area so 768px-tall displays never clip."""
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(content)
    return scroll


class SettingsPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(12)

        root.addWidget(
            page_header(
                "Settings",
                "Broker, risk ceilings, strategies, indicators, session hours and UI. "
                "Hard-coded risk ceilings always cap the user settings below.",
            )
        )

        tabs = QTabWidget()
        tabs.addTab(_scrollable(self._broker_tab()), "Broker")
        tabs.addTab(_scrollable(self._risk_tab()), "Risk")
        tabs.addTab(_scrollable(self._strategies_tab()), "Strategies")
        tabs.addTab(_scrollable(self._indicators_tab()), "Indicators")
        tabs.addTab(_scrollable(self._session_tab()), "Session hours")
        tabs.addTab(_scrollable(self._ui_tab()), "UI")
        root.addWidget(tabs, stretch=1)

    # ------------------------------------------------------------------ #
    # Broker
    # ------------------------------------------------------------------ #
    def _broker_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(2)

        api_key = QLineEdit()
        api_key.setPlaceholderText("Upstox API key (stored via Windows DPAPI)")
        api_secret = QLineEdit()
        api_secret.setEchoMode(QLineEdit.EchoMode.Password)
        api_secret.setPlaceholderText("API secret (never logged, never plaintext at rest)")
        redirect = QLineEdit()
        redirect.setPlaceholderText("https://127.0.0.1:port/callback  (must match app registration)")

        lay.addWidget(
            section_block(
                "UPSTOX OAUTH 2.0",
                [
                    form_row("API key", api_key),
                    form_row("API secret", api_secret),
                    form_row("Redirect URI", redirect),
                    form_row(
                        "Token status",
                        QLineEdit("Not connected — / —"),
                        hint="Access / refresh / expiry — DPAPI-protected. Auto refresh on expiry (worker thread).",
                    ),
                ],
                note="Flow: authorization code → access + refresh token. Scopes per current Upstox docs. "
                "Tokens encrypted with Windows DPAPI — never plaintext on disk.",
            )
        )

        sandbox = QCheckBox("Sandbox / safe-testing toggle (blocks live order routing)")
        sandbox.setChecked(True)

        static_ip = QLineEdit()
        static_ip.setPlaceholderText("Registered static IP for order API, if required")

        algo_name = QLineEdit()
        algo_name.setPlaceholderText("e.g. KalvexPro_v1")
        algo_id = QLineEdit()
        algo_id.setPlaceholderText("Broker/exchange-assigned algo id — UNKNOWN, verify")

        lay.addWidget(
            section_block(
                "ORDER API CONSTRAINTS",
                [
                    form_row("Sandbox mode", sandbox),
                    form_row("Static IP registration", static_ip, hint="Required for order API only if current docs say so — verify."),
                    form_row("algo_name on orders", algo_name, hint="Attach if broker/exchange requires it — verify."),
                    form_row("algo_id / strategy tag", algo_id, hint="UNKNOWN until confirmed in current Upstox/algo-registration docs."),
                ],
                note="Rate limit: stay under 10 orders/second unless a registered algo product is used — "
                "verify the current number. v1 order types: Limit / SL-L preferred; GTT if available; "
                "raw MARKET only if currently allowed for algo/API — otherwise locked.",
            )
        )
        lay.addStretch(1)
        return w

    # ------------------------------------------------------------------ #
    # Risk
    # ------------------------------------------------------------------ #
    def _risk_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(2)

        risk_pct = QDoubleSpinBox()
        risk_pct.setRange(0.1, 5.0)
        risk_pct.setValue(1.0)
        risk_pct.setSuffix(" %")

        max_positions = QSpinBox()
        max_positions.setRange(1, 20)
        max_positions.setValue(3)

        max_lots = QSpinBox()
        max_lots.setRange(1, 50)
        max_lots.setValue(2)

        max_orders_min = QSpinBox()
        max_orders_min.setRange(1, 200)
        max_orders_min.setValue(20)

        daily_loss = QDoubleSpinBox()
        daily_loss.setRange(0, 1_000_000)
        daily_loss.setValue(5_000)
        daily_loss.setPrefix("₹ ")

        profit_stop = QDoubleSpinBox()
        profit_stop.setRange(0, 1_000_000)
        profit_stop.setValue(10_000)
        profit_stop.setPrefix("₹ ")

        profit_stop_on = QCheckBox("Enable daily profit stop (stop bot, keep positions)")
        profit_stop_on.setChecked(False)

        trail_after = QDoubleSpinBox()
        trail_after.setRange(0, 1_000_000)
        trail_after.setValue(500)
        trail_after.setPrefix("₹ ")

        square_off = QTimeEdit()
        square_off.setDisplayFormat("HH:mm")
        square_off.setTime(square_off.time().fromString("15:15", "HH:mm"))

        lay.addWidget(
            section_block(
                "PER-TRADE LIMITS",
                [
                    form_row("Max risk per trade", risk_pct, hint="Position size = capital × risk% ÷ (entry − SL), rounded to exchange lot size."),
                    form_row("Max open positions", max_positions),
                    form_row("Max lots per order", max_lots),
                    form_row("Max orders per minute", max_orders_min, hint="Self-throttle; also stay under the broker's per-second cap."),
                ],
            )
        )
        lay.addWidget(
            section_block(
                "DAILY LIMITS & EXITS",
                [
                    form_row("Daily max loss", daily_loss, hint="→ flatten paper/live positions and stop the bot."),
                    form_row("Daily profit stop", profit_stop),
                    form_row("", profit_stop_on),
                    form_row("Trailing SL starts after", trail_after, hint="Trailing SL only after a minimum profit."),
                    form_row("Square-off time (IST)", square_off, hint="Force flat before market close."),
                ],
            )
        )
        lay.addWidget(
            hint_label(
                "Kill switch (top bar + tray): cancel open orders → flatten → stop strategies. "
                "Hard-coded ceilings cannot be exceeded by user settings."
            )
        )
        lay.addStretch(1)
        return w

    # ------------------------------------------------------------------ #
    # Strategies
    # ------------------------------------------------------------------ #
    def _strategies_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(2)

        default_mode = QComboBox()
        default_mode.addItems(["Paper", "Semi-auto", "Auto (locked)"])

        lay.addWidget(
            section_block(
                "V1 STRATEGY SET",
                [
                    form_row("Default mode for new strategies", default_mode),
                    form_row("Opening Range Breakout", QCheckBox("Enabled (index / liquid F&O)")),
                    form_row("EMA Crossover + VWAP", QCheckBox("Enabled")),
                    form_row("Supertrend Trend-Follow", QCheckBox("Enabled")),
                    form_row("RSI Mean-Reversion", QCheckBox("Enabled (cash / futures only in v1)")),
                ],
                note="Nice-to-have later: Bollinger squeeze, MACD momentum. "
                "SMC FVG/OB/BOS/CHoCH: chart overlay + optional alert only.",
            )
        )

        options_on = QCheckBox("Enable index options buying (opt-in)")
        strike_picker = QComboBox()
        strike_picker.addItems(["ATM", "ATM + N strikes OTM"])
        otm_width = QSpinBox()
        otm_width.setRange(1, 10)
        otm_width.setValue(2)
        expiry = QComboBox()
        expiry.addItems(["Current expiry (default)", "Next expiry"])
        max_hold = QTimeEdit()
        max_hold.setDisplayFormat("HH:mm")
        max_hold.setTime(max_hold.time().fromString("00:45", "HH:mm"))

        lay.addWidget(
            section_block(
                "OPTIONS (V1, LIMITED)",
                [
                    form_row("", options_on, hint="Index options buying only. No multi-leg complexity in v1."),
                    form_row("Strike picker", strike_picker),
                    form_row("OTM width (strikes)", otm_width),
                    form_row("Expiry preference", expiry),
                    form_row("Max holding time", max_hold, hint="Theta-aware time exit is mandatory. "
                            "IV & Greeks shown only if the feed provides them — no invented pricing models."),
                ],
            )
        )
        lay.addStretch(1)
        return w

    # ------------------------------------------------------------------ #
    # Indicators
    # ------------------------------------------------------------------ #
    def _indicators_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(2)

        ema_fast = QSpinBox()
        ema_fast.setRange(2, 200)
        ema_fast.setValue(9)
        ema_slow = QSpinBox()
        ema_slow.setRange(2, 400)
        ema_slow.setValue(21)

        st_period = QSpinBox()
        st_period.setRange(2, 100)
        st_period.setValue(10)
        st_mult = QDoubleSpinBox()
        st_mult.setRange(0.5, 10.0)
        st_mult.setValue(3.0)
        st_mult.setSingleStep(0.1)

        rsi_period = QSpinBox()
        rsi_period.setRange(2, 100)
        rsi_period.setValue(14)
        rsi_ob = QSpinBox()
        rsi_ob.setRange(50, 100)
        rsi_ob.setValue(70)
        rsi_os = QSpinBox()
        rsi_os.setRange(0, 50)
        rsi_os.setValue(30)

        lay.addWidget(
            section_block(
                "INDICATORS (pandas-ta FIRST; TA-LIB OPTIONAL)",
                [
                    form_row("EMA enabled", QCheckBox("On"), hint="Crossover core."),
                    form_row("EMA fast / slow", ema_fast),
                    form_row("", ema_slow),
                    form_row("VWAP filter", QCheckBox("On (session VWAP)")),
                    form_row("Supertrend enabled", QCheckBox("On")),
                    form_row("Supertrend period / multiplier", st_period),
                    form_row("", st_mult),
                    form_row("RSI enabled", QCheckBox("On")),
                    form_row("RSI period", rsi_period),
                    form_row("RSI overbought / oversold", rsi_ob),
                    form_row("", rsi_os),
                    form_row("Bollinger squeeze (later)", QCheckBox("Off")),
                    form_row("MACD momentum (later)", QCheckBox("Off")),
                    form_row("SMC overlay (smartmoneyconcepts)", QCheckBox("Chart overlay / research only"),
                             hint="Never the only live strategy."),
                ],
            )
        )
        lay.addStretch(1)
        return w

    # ------------------------------------------------------------------ #
    # Session hours
    # ------------------------------------------------------------------ #
    def _session_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(2)

        start = QTimeEdit()
        start.setDisplayFormat("HH:mm")
        start.setTime(start.time().fromString("09:15", "HH:mm"))
        end = QTimeEdit()
        end.setDisplayFormat("HH:mm")
        end.setTime(end.time().fromString("15:30", "HH:mm"))
        square_off = QTimeEdit()
        square_off.setDisplayFormat("HH:mm")
        square_off.setTime(square_off.time().fromString("15:15", "HH:mm"))
        pre_start = QTimeEdit()
        pre_start.setDisplayFormat("HH:mm")
        pre_start.setTime(pre_start.time().fromString("09:00", "HH:mm"))

        unattended = QCheckBox("Allow unattended bot operation (only during session hours)")
        unattended.setChecked(True)

        lay.addWidget(
            section_block(
                "SESSION (IST)",
                [
                    form_row("Pre-market start (auth/warm-up)", pre_start),
                    form_row("Market open", start),
                    form_row("Market close", end),
                    form_row("Square-off time", square_off),
                    form_row("Unattended operation", unattended),
                ],
                note="All timestamps logged in IST. The bot never runs unattended outside session hours, "
                "and unattended operation requires Paper mode to have been used first.",
            )
        )
        lay.addStretch(1)
        return w

    # ------------------------------------------------------------------ #
    # UI
    # ------------------------------------------------------------------ #
    def _ui_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(2)

        theme_cb = QComboBox()
        theme_cb.addItems(["Dark (v1 only)"])
        default_tf = QComboBox()
        default_tf.addItems(["1m", "5m", "15m"])
        default_tf.setCurrentIndex(1)

        lay.addWidget(
            section_block(
                "APPEARANCE & BEHAVIOUR",
                [
                    form_row("Theme", theme_cb),
                    form_row("Windows toast on semi-auto signals", QCheckBox("On")),
                    form_row("Minimize to tray on close", QCheckBox("On")),
                    form_row("Confirm before kill switch", QCheckBox("On (recommended)")),
                    form_row("Default chart timeframe", default_tf),
                ],
            )
        )
        lay.addStretch(1)
        return w
