from datetime import datetime, timedelta, timezone

from kalvex_pro.backtest import BacktestSettings, LongOptionsBacktester
from kalvex_pro.models import LongOptionSignal, OptionQuote


def t(minutes: int) -> datetime:
    return datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc) + timedelta(minutes=minutes)


def test_backtest_buys_ask_and_exits_bid_with_costs():
    quotes = [
        OptionQuote(t(0), "NSE_FO|1", 100, bid=99, ask=101),
        OptionQuote(t(5), "NSE_FO|1", 120, bid=119, ask=121),
        OptionQuote(t(10), "NSE_FO|1", 125, bid=124, ask=126),
    ]
    signal = LongOptionSignal(t(0), "NSE_FO|1", expected_return=0.2, confidence=0.8, holding_minutes=10, take_profit_fraction=0.1)
    result = LongOptionsBacktester(BacktestSettings(slippage_bps=0, fee_fraction_of_premium=0)).run(
        [signal], quotes, {"NSE_FO|1": 50}
    )
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.entry_price == 101
    assert trade.exit_price == 119
    assert trade.quantity == 50
    assert trade.net_pnl == 900
    assert trade.exit_reason == "take_profit"


def test_backtest_skips_signal_without_ask():
    quote = OptionQuote(t(0), "NSE_FO|1", 100, bid=99, ask=None)
    signal = LongOptionSignal(t(0), "NSE_FO|1", 0.1, 0.7, 10)
    result = LongOptionsBacktester().run([signal], [quote], {"NSE_FO|1": 50})
    assert result.trades == ()
