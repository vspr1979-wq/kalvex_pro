from datetime import datetime, timezone

from kalvex_pro.feed import parse_feed_payload


def test_parse_upstox_option_feed():
    payload = {
        "feeds": {
            "NSE_FO|1": {
                "firstLevelWithGreeks": {
                    "ltpc": {"ltp": 100.5, "ltt": "1760000000000"},
                    "firstDepth": {"bidP": 100, "askP": 101, "bidQ": "75", "askQ": "150"},
                    "optionGreeks": {"iv": 0.2, "delta": 0.5, "theta": -2},
                    "eFeedDetails": {"vtt": "1000", "oi": 5000},
                }
            }
        }
    }
    quote = parse_feed_payload(payload, datetime(2026, 1, 1, tzinfo=timezone.utc))[0]
    assert quote.instrument_key == "NSE_FO|1"
    assert quote.bid == 100
    assert quote.ask == 101
    assert quote.open_interest == 5000
    assert quote.delta == 0.5


def test_parse_full_feed_market_ff():
    payload = {
        "feeds": {
            "NSE_FO|2": {
                "fullFeed": {
                    "marketFF": {
                        "ltpc": {"ltp": 50},
                        "marketLevel": {"bidAskQuote": [{"bidP": 49, "askP": 51}]},
                        "optionGreeks": {"delta": -0.4},
                    }
                }
            }
        }
    }
    quote = parse_feed_payload(payload)[0]
    assert quote.ltp == 50
    assert quote.bid == 49
    assert quote.ask == 51
    assert quote.delta == -0.4
