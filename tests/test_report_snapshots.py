"""Snapshot tests for the report renderers: text ranking, JSON contract, GitHub annotations.

These snapshots are normative: if the renderer differs only in spacing or
wording from what's asserted here, the renderer is wrong, not the test.
"""

import json
from pathlib import Path

from click.testing import CliRunner

from regdrift import __version__
from regdrift.cli import main

OLD_XML = """<?xml version="1.0"?>
<device>
  <name>MINICHIP</name>
  <peripherals>
    <peripheral>
      <name>UART0</name>
      <baseAddress>0x40000000</baseAddress>
      <registers>
        <register><name>CTRL</name><addressOffset>0x0</addressOffset></register>
        <register><name>DATA</name><addressOffset>0xC</addressOffset><resetValue>0x0</resetValue></register>
        <register><name>STATUS</name><addressOffset>0x8</addressOffset><description>Status</description></register>
      </registers>
    </peripheral>
    <peripheral>
      <name>SPI0</name>
      <baseAddress>0x50000000</baseAddress>
      <registers>
        <register><name>CR</name><addressOffset>0x0</addressOffset></register>
      </registers>
    </peripheral>
  </peripherals>
</device>
"""

NEW_XML = """<?xml version="1.0"?>
<device>
  <name>MINICHIP</name>
  <peripherals>
    <peripheral>
      <name>UART0</name>
      <baseAddress>0x40000000</baseAddress>
      <registers>
        <register><name>CTRL</name><addressOffset>0x4</addressOffset></register>
        <register>
          <name>DATA</name><addressOffset>0xC</addressOffset><resetValue>0x5</resetValue>
        </register>
        <register>
          <name>STATUS</name><addressOffset>0x8</addressOffset>
          <description>Status register</description>
        </register>
        <register><name>NEW</name><addressOffset>0x10</addressOffset></register>
      </registers>
    </peripheral>
  </peripherals>
</device>
"""

EXPECTED_TEXT = """BREAKING (1)
  RD007  peripheral SPI0 removed

WARNING (1)
  RD010  register UART0.DATA reset value changed 0x0 -> 0x5

ALLOWED (1)
  RD001  register UART0.CTRL address moved 0x0 -> 0x4

2 safe (1 added, 1 description-only) - use --all to list

1 breaking, 1 warning, 2 safe, 1 allowed"""

EXPECTED_TEXT_ALL = """BREAKING (1)
  RD007  peripheral SPI0 removed

WARNING (1)
  RD010  register UART0.DATA reset value changed 0x0 -> 0x5

ALLOWED (1)
  RD001  register UART0.CTRL address moved 0x0 -> 0x4

SAFE (2)
  RD030  register UART0.STATUS description changed
  RD020  register UART0.NEW added

1 breaking, 1 warning, 2 safe, 1 allowed"""


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    old = tmp_path / "old.svd"
    new = tmp_path / "new.svd"
    old.write_text(OLD_XML)
    new.write_text(NEW_XML)
    return old, new


def test_default_text_report(tmp_path: Path) -> None:
    old, new = _fixture(tmp_path)
    result = CliRunner().invoke(
        main, ["check", str(old), str(new), "--allow", "RD001:UART0.CTRL"]
    )
    assert result.output.rstrip("\n") == EXPECTED_TEXT
    assert result.exit_code == 1


def test_all_flag_lists_safe(tmp_path: Path) -> None:
    old, new = _fixture(tmp_path)
    result = CliRunner().invoke(
        main, ["check", str(old), str(new), "--allow", "RD001:UART0.CTRL", "--all"]
    )
    assert result.output.rstrip("\n") == EXPECTED_TEXT_ALL
    assert result.exit_code == 1


def test_json_format(tmp_path: Path) -> None:
    old, new = _fixture(tmp_path)
    result = CliRunner().invoke(
        main,
        ["check", str(old), str(new), "--allow", "RD001:UART0.CTRL", "--format", "json"],
    )
    assert result.exit_code == 1
    doc = json.loads(result.output)
    expected = {
        "schema_version": 1,
        "regdrift_version": __version__,
        "old": {"file": str(old), "device": "MINICHIP"},
        "new": {"file": str(new), "device": "MINICHIP"},
        "summary": {"breaking": 1, "warning": 1, "safe": 2, "allowed": 1},
        "passed": False,
        "findings": [
            {
                "rule": "RD001",
                "severity": "BREAKING",
                "allowed": True,
                "element": "register",
                "path": "UART0.CTRL",
                "kind": "moved",
                "attribute": "address_offset",
                "before": "0x0",
                "after": "0x4",
                "confidence": None,
                "message": "register UART0.CTRL address moved 0x0 -> 0x4",
            },
            {
                "rule": "RD010",
                "severity": "WARNING",
                "allowed": False,
                "element": "register",
                "path": "UART0.DATA",
                "kind": "modified",
                "attribute": "reset_value",
                "before": "0x0",
                "after": "0x5",
                "confidence": None,
                "message": "register UART0.DATA reset value changed 0x0 -> 0x5",
            },
            {
                "rule": "RD030",
                "severity": "SAFE",
                "allowed": False,
                "element": "register",
                "path": "UART0.STATUS",
                "kind": "modified",
                "attribute": "description",
                "before": "Status",
                "after": "Status register",
                "confidence": None,
                "message": "register UART0.STATUS description changed",
            },
            {
                "rule": "RD020",
                "severity": "SAFE",
                "allowed": False,
                "element": "register",
                "path": "UART0.NEW",
                "kind": "added",
                "attribute": None,
                "before": None,
                "after": None,
                "confidence": None,
                "message": "register UART0.NEW added",
            },
            {
                "rule": "RD007",
                "severity": "BREAKING",
                "allowed": False,
                "element": "peripheral",
                "path": "SPI0",
                "kind": "removed",
                "attribute": None,
                "before": None,
                "after": None,
                "confidence": None,
                "message": "peripheral SPI0 removed",
            },
        ],
    }
    assert doc == expected


def test_github_format(tmp_path: Path) -> None:
    old, new = _fixture(tmp_path)
    result = CliRunner().invoke(
        main,
        ["check", str(old), str(new), "--allow", "RD001:UART0.CTRL", "--format", "github"],
    )
    expected = (
        f"::error file={new},title=RD007 SPI0::peripheral SPI0 removed\n"
        f"::warning file={new},title=RD010 UART0.DATA::"
        "register UART0.DATA reset value changed 0x0 -> 0x5"
    )
    assert result.output.rstrip("\n") == expected


def test_github_format_overflow_caps_at_nine(tmp_path: Path) -> None:
    n_registers = 12
    regs_old = "\n".join(
        f'<register><name>R{i}</name><addressOffset>0x{i * 4:X}</addressOffset></register>'
        for i in range(n_registers)
    )
    old_xml = f"""<?xml version="1.0"?>
<device>
  <name>MINICHIP</name>
  <peripherals>
    <peripheral>
      <name>P</name>
      <baseAddress>0x40000000</baseAddress>
      <registers>
        {regs_old}
      </registers>
    </peripheral>
  </peripherals>
</device>
"""
    new_xml = """<?xml version="1.0"?>
<device>
  <name>MINICHIP</name>
  <peripherals>
    <peripheral>
      <name>P</name>
      <baseAddress>0x40000000</baseAddress>
      <registers>
      </registers>
    </peripheral>
  </peripherals>
</device>
"""
    old = tmp_path / "old.svd"
    new = tmp_path / "new.svd"
    old.write_text(old_xml)
    new.write_text(new_xml)
    result = CliRunner().invoke(main, ["check", str(old), str(new), "--format", "github"])
    lines = result.output.rstrip("\n").split("\n")
    error_lines = [line for line in lines if line.startswith("::error")]
    assert len(error_lines) == 10
    assert error_lines[-1] == (
        f"::error file={new},title=regdrift::and 3 more breaking findings - "
        "see the log or step summary"
    )


def test_enum_rollup_in_text(tmp_path: Path) -> None:
    old_xml = """<?xml version="1.0"?>
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
          <fields>
            <field>
              <name>MODE</name><bitOffset>0</bitOffset><bitWidth>2</bitWidth>
              <enumeratedValues>
                <enumeratedValue><name>SLOW</name><value>0</value></enumeratedValue>
                <enumeratedValue><name>FAST</name><value>1</value></enumeratedValue>
              </enumeratedValues>
            </field>
          </fields>
        </register>
      </registers>
    </peripheral>
  </peripherals>
</device>
"""
    new_xml = """<?xml version="1.0"?>
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
          <fields>
            <field>
              <name>MODE</name><bitOffset>0</bitOffset><bitWidth>2</bitWidth>
            </field>
          </fields>
        </register>
      </registers>
    </peripheral>
  </peripherals>
</device>
"""
    old = tmp_path / "old.svd"
    new = tmp_path / "new.svd"
    old.write_text(old_xml)
    new.write_text(new_xml)
    result = CliRunner().invoke(main, ["check", str(old), str(new)])
    assert "  RD013  field UART0.CTRL.MODE: 2 enum values removed (SLOW, FAST)" in result.output


def test_fail_on_warning_exits_one(tmp_path: Path) -> None:
    old_xml = OLD_XML
    new_xml = OLD_XML.replace(
        "<register><name>DATA</name><addressOffset>0xC</addressOffset><resetValue>0x0</resetValue></register>",
        "<register><name>DATA</name><addressOffset>0xC</addressOffset><resetValue>0x5</resetValue></register>",
    )
    old = tmp_path / "old.svd"
    new = tmp_path / "new.svd"
    old.write_text(old_xml)
    new.write_text(new_xml)
    result = CliRunner().invoke(main, ["check", str(old), str(new), "--fail-on", "warning"])
    assert result.exit_code == 1


def test_allowed_breaking_with_fail_on_warning_exits_zero(tmp_path: Path) -> None:
    old_xml = OLD_XML
    new_xml = OLD_XML.replace(
        '<register><name>CTRL</name><addressOffset>0x0</addressOffset></register>',
        '<register><name>CTRL</name><addressOffset>0x4</addressOffset></register>',
    )
    old = tmp_path / "old.svd"
    new = tmp_path / "new.svd"
    old.write_text(old_xml)
    new.write_text(new_xml)
    result = CliRunner().invoke(
        main,
        [
            "check",
            str(old),
            str(new),
            "--allow",
            "RD001:UART0.CTRL",
            "--allow",
            "RD007:SPI0",
            "--fail-on",
            "warning",
        ],
    )
    assert result.exit_code == 0


def test_stdin_old_file(tmp_path: Path) -> None:
    old, new = _fixture(tmp_path)
    result = CliRunner().invoke(
        main,
        ["check", "-", str(new), "--allow", "RD001:UART0.CTRL"],
        input=OLD_XML,
    )
    assert result.exit_code == 1
    assert "BREAKING" in result.output
