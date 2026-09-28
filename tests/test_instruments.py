from datetime import date
import json

from kalvex_pro.instruments import OptionsUniverse, UniverseRequest, canonical_index_alias, load_instrument_master, summarize


def test_index_aliases_are_normalized():
    assert canonical_index_alias("Nifty 50") == "NIFTY"
    assert canonical_index_alias("NIFTY BANK") == "BANKNIFTY"
    assert canonical_index_alias("Nifty Fin Service") == "FINNIFTY"
    assert canonical_index_alias("Nifty Midcap Select") == "MIDCAPNIFTY"


def test_universe_includes_requested_indices_and_all_fno_stocks(tmp_path):
    records = [
        {
            "instrument_key": "NSE_FO|1",
            "exchange": "NSE",
            "segment": "NSE_FO",
            "instrument_type": "OPTIDX",
            "trading_symbol": "NIFTY 50 25000 CE",
            "underlying_symbol": "Nifty 50",
            "expiry": "2099-01-01",
            "strike_price": 25000,
            "option_type": "CE",
            "lot_size": 75,
        },
        {
            "instrument_key": "BSE_FO|2",
            "exchange": "BSE",
            "segment": "BSE_FO",
            "instrument_type": "OPTIDX",
            "trading_symbol": "SENSEX 80000 PE",
            "underlying_symbol": "SENSEX",
            "expiry": "2099-01-01",
            "strike_price": 80000,
            "option_type": "PE",
            "lot_size": 20,
        },
        {
            "instrument_key": "NSE_FO|3",
            "exchange": "NSE",
            "segment": "NSE_FO",
            "instrument_type": "OPTSTK",
            "trading_symbol": "RELIANCE PE",
            "underlying_symbol": "RELIANCE",
            "underlying_key": "NSE_EQ|INE002A01018",
            "expiry": "2099-01-01",
            "strike_price": 1200,
            "option_type": "PE",
            "lot_size": 250,
        },
    ]
    path = tmp_path / "instruments.json"
    path.write_text(json.dumps(records))
    instruments = load_instrument_master(path)
    selected = OptionsUniverse(instruments).select(
        UniverseRequest(index_aliases=("NIFTY", "SENSEX"), as_of=date(2098, 12, 15))
    )
    assert {item.instrument_key for item in selected} == {"NSE_FO|1", "BSE_FO|2", "NSE_FO|3"}
    assert summarize(selected)["NSE:index:CE"] == 1
