"""Loading .regdrift.toml: allowlist, severity overrides, validation."""

from pathlib import Path

import pytest

from regdrift.config import ConfigError, load_config


def test_load_allow_entries(tmp_path: Path) -> None:
    cfg = tmp_path / ".regdrift.toml"
    cfg.write_text('allow = ["RD001:UART0.CTRL", "RD030"]\n')
    assert load_config(cfg).allow == ["RD001:UART0.CTRL", "RD030"]


def test_missing_default_config_is_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    config = load_config(None)
    assert config.allow == []
    assert config.severity_overrides == {}


def test_default_config_picked_up_from_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".regdrift.toml").write_text('allow = ["RD010"]\n')
    monkeypatch.chdir(tmp_path)
    assert load_config(None).allow == ["RD010"]


def test_missing_explicit_config_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="cannot read"):
        load_config(tmp_path / "nope.toml")


def test_invalid_toml_raises(tmp_path: Path) -> None:
    cfg = tmp_path / ".regdrift.toml"
    cfg.write_text("allow = [unclosed\n")
    with pytest.raises(ConfigError, match="invalid TOML"):
        load_config(cfg)


def test_allow_must_be_string_list(tmp_path: Path) -> None:
    cfg = tmp_path / ".regdrift.toml"
    cfg.write_text("allow = 3\n")
    with pytest.raises(ConfigError, match="list of strings"):
        load_config(cfg)


def test_severity_overrides_parsed(tmp_path: Path) -> None:
    cfg = tmp_path / ".regdrift.toml"
    cfg.write_text('[severity]\nRD013 = "SAFE"\nRD010 = "BREAKING"\n')
    assert load_config(cfg).severity_overrides == {"RD013": "SAFE", "RD010": "BREAKING"}


def test_invalid_severity_value_raises(tmp_path: Path) -> None:
    cfg = tmp_path / ".regdrift.toml"
    cfg.write_text('[severity]\nRD013 = "IGNORE"\n')
    with pytest.raises(ConfigError, match="must be one of"):
        load_config(cfg)


def test_invalid_rule_id_raises(tmp_path: Path) -> None:
    cfg = tmp_path / ".regdrift.toml"
    cfg.write_text('[severity]\nNOTARULE = "SAFE"\n')
    with pytest.raises(ConfigError, match="invalid rule ID"):
        load_config(cfg)
