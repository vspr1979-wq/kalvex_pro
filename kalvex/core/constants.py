"""Application constants for the UI layout skeleton."""

from enum import Enum

APP_NAME = "Kalvex Pro"
APP_VERSION = "0.1.0-ui"

# Designed for a minimum display resolution of 1366x768.
WINDOW_MIN_WIDTH = 1280
WINDOW_MIN_HEIGHT = 720
WINDOW_DEFAULT_WIDTH = 1500
WINDOW_DEFAULT_HEIGHT = 860

NAV_WIDTH = 212
TOP_BAR_HEIGHT = 66


class BotMode(str, Enum):
    """Bot execution modes. Paper is the hard default; Auto is a later opt-in."""

    PAPER = "Paper"
    SEMI_AUTO = "Semi-auto"
    AUTO = "Auto"


# Auto mode stays locked until Paper mode has been used (and until the
# later live-trading opt-in phase). UI-only enforcement for now.
AUTO_MODE_LOCKED = True


class PageId(str, Enum):
    DASHBOARD = "dashboard"
    CHARTS = "charts"
    STRATEGIES = "strategies"
    ACTIVITY = "activity"  # Positions / Orders / Trades
    LOGS = "logs"
    SETTINGS = "settings"


PAGE_TITLES: dict[PageId, str] = {
    PageId.DASHBOARD: "Dashboard",
    PageId.CHARTS: "Charts",
    PageId.STRATEGIES: "Strategies",
    PageId.ACTIVITY: "Positions / Orders",
    PageId.LOGS: "Logs",
    PageId.SETTINGS: "Settings",
}

# v1 strategy set from the product spec — names only, no logic here.
STRATEGY_NAMES = (
    "Opening Range Breakout (index / liquid F&O)",
    "EMA Crossover + VWAP Filter",
    "Supertrend Trend-Follow",
    "RSI Mean-Reversion (cash / futures)",
)

# Nice-to-have later: Bollinger squeeze, MACD momentum,
# SMC (FVG/OB/BOS/CHoCH) as chart overlays + optional alert only.
