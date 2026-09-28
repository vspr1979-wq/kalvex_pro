from datetime import date, datetime, timezone

from kalvex_pro.models import Candle, Instrument
from kalvex_pro.qlib_bridge import write_qlib_csv


def test_qlib_csv_contains_expiry_and_option_metadata(tmp_path):
    instrument = Instrument(
        instrument_key="NSE_FO|1",
        exchange="NSE",
        segment="NSE_FO",
        instrument_type="OPTIDX",
        underlying_key="NSE_INDEX|Nifty 50",
        underlying_symbol="Nifty 50",
        expiry=date(2026, 1, 8),
        strike_price=25000,
        option_type="CE",
        lot_size=75,
    )
    candles = [Candle(datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc), "NSE_FO|1", 100, 110, 90, 105, 1000, 200)]
    output = tmp_path / "options.csv"
    assert write_qlib_csv(candles, {instrument.instrument_key: instrument}, output) == 1
    content = output.read_text()
    assert "underlying_key" in content
    assert "2026-01-08" in content
    assert "CE" in content
