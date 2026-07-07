"""The `regdrift check` command: report and exit-code contract."""

from pathlib import Path

from click.testing import CliRunner

from regdrift.cli import main

SVD = """<?xml version="1.0"?>
<device>
  <name>MINICHIP</name>
  <peripherals>
    <peripheral>
      <name>UART0</name>
      <baseAddress>0x40000000</baseAddress>
      <registers>
        <register>
          <name>CTRL</name>
          <addressOffset>{ctrl_offset}</addressOffset>
          <resetValue>{ctrl_reset}</resetValue>
        </register>
        <register>
          <name>STATUS</name>
          <addressOffset>0x8</addressOffset>
          <description>{status_desc}</description>
        </register>
      </registers>
    </peripheral>
  </peripherals>
</device>
"""


def _write(
    path: Path,
    ctrl_offset: str = "0x0",
    ctrl_reset: str = "0x0",
    status_desc: str = "Status",
) -> Path:
    path.write_text(
        SVD.format(ctrl_offset=ctrl_offset, ctrl_reset=ctrl_reset, status_desc=status_desc)
    )
    return path


def test_no_changes_exits_zero(tmp_path: Path) -> None:
    old = _write(tmp_path / "old.svd")
    new = _write(tmp_path / "new.svd")
    result = CliRunner().invoke(main, ["check", str(old), str(new)])
    assert result.exit_code == 0
    assert "0 breaking, 0 warning, 0 safe, 0 allowed" in result.output


def test_breaking_change_exits_one(tmp_path: Path) -> None:
    old = _write(tmp_path / "old.svd")
    new = _write(tmp_path / "new.svd", ctrl_offset="0x4")
    result = CliRunner().invoke(main, ["check", str(old), str(new)])
    assert result.exit_code == 1
    assert "BREAKING" in result.output
    assert "RD001" in result.output
    assert "1 breaking" in result.output


def test_warning_only_exits_zero(tmp_path: Path) -> None:
    old = _write(tmp_path / "old.svd")
    new = _write(tmp_path / "new.svd", ctrl_reset="0x5")
    result = CliRunner().invoke(main, ["check", str(old), str(new)])
    assert result.exit_code == 0
    assert "RD010" in result.output
    assert "1 warning" in result.output


def test_allow_flag_downgrades_to_allowed(tmp_path: Path) -> None:
    old = _write(tmp_path / "old.svd")
    new = _write(tmp_path / "new.svd", ctrl_offset="0x4")
    result = CliRunner().invoke(
        main, ["check", str(old), str(new), "--allow", "RD001:UART0.CTRL"]
    )
    assert result.exit_code == 0
    assert "ALLOWED" in result.output
    assert "0 breaking" in result.output
    assert "1 allowed" in result.output


def test_allowlist_from_config_file(tmp_path: Path, monkeypatch: object) -> None:
    old = _write(tmp_path / "old.svd")
    new = _write(tmp_path / "new.svd", ctrl_offset="0x4")
    cfg = tmp_path / ".regdrift.toml"
    cfg.write_text('allow = ["RD001:UART0.CTRL"]\n')
    result = CliRunner().invoke(
        main, ["check", str(old), str(new), "--config", str(cfg)]
    )
    assert result.exit_code == 0
    assert "ALLOWED" in result.output


def test_malformed_svd_exits_two(tmp_path: Path) -> None:
    old = _write(tmp_path / "old.svd")
    bad = tmp_path / "bad.svd"
    bad.write_text("<device><name>X</name>")
    result = CliRunner().invoke(main, ["check", str(old), str(bad)])
    assert result.exit_code == 2
    assert "error:" in result.output


def test_bad_config_exits_two(tmp_path: Path) -> None:
    old = _write(tmp_path / "old.svd")
    new = _write(tmp_path / "new.svd")
    cfg = tmp_path / "broken.toml"
    cfg.write_text("allow = [")
    result = CliRunner().invoke(main, ["check", str(old), str(new), "--config", str(cfg)])
    assert result.exit_code == 2


def test_severity_override_downgrades_breaking(tmp_path: Path) -> None:
    old = _write(tmp_path / "old.svd")
    new = _write(tmp_path / "new.svd", ctrl_offset="0x4")
    cfg = tmp_path / ".regdrift.toml"
    cfg.write_text('[severity]\nRD001 = "WARNING"\n')
    result = CliRunner().invoke(main, ["check", str(old), str(new), "--config", str(cfg)])
    assert result.exit_code == 0
    assert "WARNING" in result.output
    assert "0 breaking, 1 warning" in result.output


def test_severity_override_upgrades_warning(tmp_path: Path) -> None:
    old = _write(tmp_path / "old.svd")
    new = _write(tmp_path / "new.svd", ctrl_reset="0x5")
    cfg = tmp_path / ".regdrift.toml"
    cfg.write_text('[severity]\nRD010 = "BREAKING"\n')
    result = CliRunner().invoke(main, ["check", str(old), str(new), "--config", str(cfg)])
    assert result.exit_code == 1
    assert "1 breaking" in result.output


def test_allow_wins_over_severity_override(tmp_path: Path) -> None:
    old = _write(tmp_path / "old.svd")
    new = _write(tmp_path / "new.svd", ctrl_offset="0x4")
    cfg = tmp_path / ".regdrift.toml"
    cfg.write_text('allow = ["RD001:UART0.CTRL"]\n[severity]\nRD001 = "BREAKING"\n')
    result = CliRunner().invoke(main, ["check", str(old), str(new), "--config", str(cfg)])
    assert result.exit_code == 0
    assert "ALLOWED" in result.output


def test_safe_changes_reported_but_pass(tmp_path: Path) -> None:
    old = _write(tmp_path / "old.svd")
    new = _write(tmp_path / "new.svd", status_desc="Status register, clarified")
    result = CliRunner().invoke(main, ["check", str(old), str(new)])
    assert result.exit_code == 0
    assert "1 safe" in result.output


def test_safe_changes_listed_with_all_flag(tmp_path: Path) -> None:
    old = _write(tmp_path / "old.svd")
    new = _write(tmp_path / "new.svd", status_desc="Status register, clarified")
    result = CliRunner().invoke(main, ["check", str(old), str(new), "--all"])
    assert result.exit_code == 0
    assert "RD030" in result.output
    assert "1 safe" in result.output
