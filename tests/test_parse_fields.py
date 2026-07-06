"""Field bit-range forms and enumerated values."""

import pytest

from conftest import MakeDevice
from regdrift.model import Register
from regdrift.parse import SvdParseError


def _device_with_field(field_xml: str, make_device: MakeDevice) -> Register:
    dev = make_device(
        f"""
<peripheral>
  <name>P1</name>
  <baseAddress>0x40000000</baseAddress>
  <registers>
    <register>
      <name>R1</name>
      <addressOffset>0x0</addressOffset>
      <fields>
        {field_xml}
      </fields>
    </register>
  </registers>
</peripheral>
"""
    )
    reg = dev.peripherals[0].children[0]
    assert isinstance(reg, Register)
    return reg


def test_bit_offset_width(make_device: MakeDevice) -> None:
    reg = _device_with_field(
        "<field><name>F</name><bitOffset>3</bitOffset><bitWidth>5</bitWidth></field>",
        make_device,
    )
    assert (reg.fields[0].bit_offset, reg.fields[0].bit_width) == (3, 5)


def test_bit_width_defaults_to_one(make_device: MakeDevice) -> None:
    reg = _device_with_field(
        "<field><name>F</name><bitOffset>7</bitOffset></field>", make_device
    )
    assert (reg.fields[0].bit_offset, reg.fields[0].bit_width) == (7, 1)


def test_lsb_msb(make_device: MakeDevice) -> None:
    reg = _device_with_field(
        "<field><name>F</name><lsb>4</lsb><msb>7</msb></field>", make_device
    )
    assert (reg.fields[0].bit_offset, reg.fields[0].bit_width) == (4, 4)


def test_bit_range(make_device: MakeDevice) -> None:
    reg = _device_with_field(
        "<field><name>F</name><bitRange>[7:4]</bitRange></field>", make_device
    )
    assert (reg.fields[0].bit_offset, reg.fields[0].bit_width) == (4, 4)


def test_missing_bit_range_raises(make_device: MakeDevice) -> None:
    with pytest.raises(SvdParseError, match="bit range"):
        _device_with_field("<field><name>F</name></field>", make_device)


def test_enumerated_values(make_device: MakeDevice) -> None:
    reg = _device_with_field(
        """
<field>
  <name>MODE</name><bitOffset>0</bitOffset><bitWidth>2</bitWidth>
  <enumeratedValues>
    <name>MODES</name>
    <usage>read-write</usage>
    <enumeratedValue>
      <name>OFF</name><value>0</value><description>Disabled</description>
    </enumeratedValue>
    <enumeratedValue><name>HEX</name><value>0x2</value></enumeratedValue>
    <enumeratedValue><name>BIN</name><value>0b11</value></enumeratedValue>
    <enumeratedValue><name>OTHER</name><isDefault>true</isDefault></enumeratedValue>
  </enumeratedValues>
</field>
""",
        make_device,
    )
    enums = reg.fields[0].enumerated_values
    assert [e.name for e in enums] == ["OFF", "HEX", "BIN", "OTHER"]
    assert [e.value for e in enums] == [0, 2, 3, None]
    assert enums[0].description == "Disabled"
    assert enums[3].is_default is True
    assert all(e.usage == "read-write" for e in enums)


def test_enum_wildcard_value_kept_raw(make_device: MakeDevice) -> None:
    reg = _device_with_field(
        """
<field>
  <name>MODE</name><bitOffset>0</bitOffset><bitWidth>4</bitWidth>
  <enumeratedValues>
    <enumeratedValue><name>ANY_HIGH</name><value>#1xxx</value></enumeratedValue>
  </enumeratedValues>
</field>
""",
        make_device,
    )
    enum = reg.fields[0].enumerated_values[0]
    assert enum.value is None
    assert enum.raw_value == "#1xxx"


def test_hash_binary_value(make_device: MakeDevice) -> None:
    reg = _device_with_field(
        """
<field>
  <name>MODE</name><bitOffset>0</bitOffset><bitWidth>3</bitWidth>
  <enumeratedValues>
    <enumeratedValue><name>FIVE</name><value>#101</value></enumeratedValue>
  </enumeratedValues>
</field>
""",
        make_device,
    )
    assert reg.fields[0].enumerated_values[0].value == 5
