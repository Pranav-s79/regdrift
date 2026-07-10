"""Every parse error must carry an XPath-ish location pointing at the offending node."""

from pathlib import Path

import pytest

from conftest import MakeDevice
from regdrift.parse import SvdParseError, parse_svd, parse_svd_string


def _error(make_device: MakeDevice, peripherals: str) -> SvdParseError:
    with pytest.raises(SvdParseError) as excinfo:
        make_device(peripherals)
    return excinfo.value


def test_malformed_xml_reports_location() -> None:
    with pytest.raises(SvdParseError, match="malformed XML"):
        parse_svd_string("<device><name>X</name>")


def test_unreadable_file_is_wrapped_as_parse_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svd = tmp_path / "unreadable.svd"
    svd.write_text("<device/>")

    def fail_to_read(_path: str | Path) -> None:
        raise OSError("permission denied")

    monkeypatch.setattr("regdrift.parse.ET.parse", fail_to_read)
    with pytest.raises(SvdParseError, match="cannot read SVD") as excinfo:
        parse_svd(svd)
    assert excinfo.value.location == str(svd)


def test_wrong_root_element() -> None:
    err = pytest.raises(SvdParseError, parse_svd_string, "<gadget/>").value
    assert "expected <device>" in err.message
    assert err.location == "/"


def test_missing_base_address_names_peripheral(make_device: MakeDevice) -> None:
    err = _error(make_device, "<peripheral><name>UART0</name></peripheral>")
    assert "baseAddress" in err.message
    assert "peripheral[@name='UART0']" in err.location


def test_missing_address_offset_names_register(make_device: MakeDevice) -> None:
    err = _error(
        make_device,
        """
<peripheral>
  <name>UART0</name>
  <baseAddress>0x40000000</baseAddress>
  <registers><register><name>CTRL</name></register></registers>
</peripheral>
""",
    )
    assert "addressOffset" in err.message
    assert (
        err.location
        == "/device/peripherals/peripheral[@name='UART0']/registers/register[@name='CTRL']"
    )


def test_invalid_integer_reports_value_and_location(make_device: MakeDevice) -> None:
    err = _error(
        make_device,
        "<peripheral><name>P1</name><baseAddress>banana</baseAddress></peripheral>",
    )
    assert "banana" in err.message
    assert "peripheral[@name='P1']" in err.location


def test_bad_bit_range_names_field(make_device: MakeDevice) -> None:
    err = _error(
        make_device,
        """
<peripheral>
  <name>P1</name>
  <baseAddress>0x0</baseAddress>
  <registers>
    <register>
      <name>R1</name>
      <addressOffset>0x0</addressOffset>
      <fields><field><name>BROKEN</name><bitRange>7:4</bitRange></field></fields>
    </register>
  </registers>
</peripheral>
""",
    )
    assert "bitRange" in err.message
    assert "field[@name='BROKEN']" in err.location


def test_derive_error_points_at_derived_node(make_device: MakeDevice) -> None:
    err = _error(
        make_device,
        '<peripheral derivedFrom="GHOST"><name>A</name><baseAddress>0x0</baseAddress></peripheral>',
    )
    assert "peripheral[@name='A']" in err.location


def test_str_includes_location(make_device: MakeDevice) -> None:
    err = _error(make_device, "<peripheral><name>P1</name></peripheral>")
    assert str(err).startswith(err.location + ": ")
