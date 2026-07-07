"""Loading the .regdrift.toml allowlist."""

from pathlib import Path

import pytest

from regdrift.config import ConfigError, load_allowlist


def test_load_allow_entries(tmp_path: Path) -> None:
    cfg = tmp_path / ".regdrift.toml"
    cfg.write_text('allow = ["RD001:UART0.CTRL", "RD030"]\n')
    assert load_allowlist(cfg) == ["RD001:UART0.CTRL", "RD030"]


def test_missing_default_config_is_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert load_allowlist(None) == []


def test_default_config_picked_up_from_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".regdrift.toml").write_text('allow = ["RD010"]\n')
    monkeypatch.chdir(tmp_path)
    assert load_allowlist(None) == ["RD010"]


def test_missing_explicit_config_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="cannot read"):
        load_allowlist(tmp_path / "nope.toml")


def test_invalid_toml_raises(tmp_path: Path) -> None:
    cfg = tmp_path / ".regdrift.toml"
    cfg.write_text("allow = [unclosed\n")
    with pytest.raises(ConfigError, match="invalid TOML"):
        load_allowlist(cfg)


def test_allow_must_be_string_list(tmp_path: Path) -> None:
    cfg = tmp_path / ".regdrift.toml"
    cfg.write_text("allow = 3\n")
    with pytest.raises(ConfigError, match="list of strings"):
        load_allowlist(cfg)
