from datetime import date

from kalvex_pro.upstox import parse_candles


def test_parse_upstox_candles():
    payload = {
        "status": "success",
        "data": {
            "candles": [
                ["2026-01-01T09:15:00+05:30", 100, 105, 99, 103, 1000, 200],
            ]
        },
    }
    candles = parse_candles(payload, "NSE_FO|1")
    assert len(candles) == 1
    assert candles[0].close == 103
    assert candles[0].open_interest == 200
