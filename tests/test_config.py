from pathlib import Path

from kalvex_pro.config import load_config


def test_default_config_is_long_options_shadow_mode():
    config = load_config(Path("configs/intraday_long_options.toml"))
    assert config.market.exchanges == ("NSE", "BSE")
    assert config.market.include_fno_stocks is True
    assert config.risk.long_options_only is True
    assert config.execution.mode == "shadow"
    assert config.execution.allow_order_placement is False


def test_live_mode_requires_explicit_permission(tmp_path):
    path = tmp_path / "bad.toml"
    path.write_text('[execution]\nmode = "live"\nallow_order_placement = false\n')
    try:
        load_config(path)
    except ValueError as exc:
        assert "allow_order_placement" in str(exc)
    else:
        raise AssertionError("unsafe live configuration was accepted")
