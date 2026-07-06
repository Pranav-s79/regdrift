"""The `regdrift parse` command."""

import json
from pathlib import Path

from click.testing import CliRunner

from regdrift.cli import main

MINIMAL_SVD = """<?xml version="1.0"?>
<device>
  <name>MINICHIP</name>
  <peripherals>
    <peripheral>
      <name>UART0</name>
      <baseAddress>0x40000000</baseAddress>
      <registers>
        <register>
          <name>CTRL</name>
          <addressOffset>0x0</addressOffset>
          <resetValue>0x5</resetValue>
        </register>
      </registers>
    </peripheral>
  </peripherals>
</device>
"""


def _write_svd(tmp_path: Path, content: str = MINIMAL_SVD) -> Path:
    svd = tmp_path / "chip.svd"
    svd.write_text(content)
    return svd


def test_parse_summary(tmp_path: Path) -> None:
    result = CliRunner().invoke(main, ["parse", str(_write_svd(tmp_path))])
    assert result.exit_code == 0
    assert "MINICHIP: 1 peripherals, 1 registers" in result.output


def test_parse_json_dumps_resolved_model(tmp_path: Path) -> None:
    result = CliRunner().invoke(main, ["parse", str(_write_svd(tmp_path)), "--json"])
    assert result.exit_code == 0
    model = json.loads(result.output)
    assert model["name"] == "MINICHIP"
    reg = model["peripherals"][0]["children"][0]
    assert reg["kind"] == "register"
    assert reg["name"] == "CTRL"
    assert reg["reset_value"] == 5
    assert reg["size"] == 32  # spec default applied


def test_parse_missing_file_fails_cleanly() -> None:
    result = CliRunner().invoke(main, ["parse", "no_such.svd"])
    assert result.exit_code != 0
    assert "no_such.svd" in result.output


def test_parse_error_reports_location(tmp_path: Path) -> None:
    bad = MINIMAL_SVD.replace("<baseAddress>0x40000000</baseAddress>", "")
    result = CliRunner().invoke(main, ["parse", str(_write_svd(tmp_path, bad))])
    assert result.exit_code == 1
    assert "baseAddress" in result.output
    assert "peripheral[@name='UART0']" in result.output
