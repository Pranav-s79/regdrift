"""The `regdrift diff` command."""

import json
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
          <addressOffset>{offset}</addressOffset>
        </register>
      </registers>
    </peripheral>
  </peripherals>
</device>
"""


def _pair(tmp_path: Path, old_offset: str, new_offset: str) -> tuple[Path, Path]:
    old = tmp_path / "old.svd"
    new = tmp_path / "new.svd"
    old.write_text(SVD.format(offset=old_offset))
    new.write_text(SVD.format(offset=new_offset))
    return old, new


def test_diff_human_output(tmp_path: Path) -> None:
    old, new = _pair(tmp_path, "0x0", "0x8")
    result = CliRunner().invoke(main, ["diff", str(old), str(new)])
    assert result.exit_code == 0
    assert "moved" in result.output
    assert "UART0.CTRL" in result.output
    assert "1 change(s)" in result.output


def test_diff_json_output(tmp_path: Path) -> None:
    old, new = _pair(tmp_path, "0x0", "0x8")
    result = CliRunner().invoke(main, ["diff", str(old), str(new), "--json"])
    assert result.exit_code == 0
    changes = json.loads(result.output)
    assert changes == [
        {
            "kind": "moved",
            "element": "register",
            "path": "UART0.CTRL",
            "attribute": "address_offset",
            "before": 0,
            "after": 8,
            "confidence": None,
        }
    ]


def test_diff_identical_files_empty(tmp_path: Path) -> None:
    old, new = _pair(tmp_path, "0x0", "0x0")
    result = CliRunner().invoke(main, ["diff", str(old), str(new), "--json"])
    assert result.exit_code == 0
    assert json.loads(result.output) == []


def test_diff_bad_file_fails_with_location(tmp_path: Path) -> None:
    old = tmp_path / "old.svd"
    old.write_text(SVD.format(offset="0x0"))
    bad = tmp_path / "bad.svd"
    bad.write_text("<device><name>X</name><peripherals><peripheral/></peripherals></device>")
    result = CliRunner().invoke(main, ["diff", str(old), str(bad)])
    assert result.exit_code == 1
    assert "peripheral" in result.output
