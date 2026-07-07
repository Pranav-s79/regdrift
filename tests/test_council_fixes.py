"""Regression tests for the council-review correctness findings.

1. Enum diffing must key by (usage, name): read/write containers with
   same-named entries diff independently.
2. A derived field's own bit range (any style) wins over the base's style.
3. Omitted enum <usage> normalizes to the spec default read-write.
4. Unqualified derivedFrom resolves same-scope siblings before nested
   matches, and never crosses peripheral boundaries.
"""

import pytest

from conftest import MakeDevice
from regdrift.diff import diff_devices
from regdrift.model import Register
from regdrift.parse import SvdParseError


def _field_device(field_xml: str) -> str:
    return f"""
<peripheral>
  <name>P1</name>
  <baseAddress>0x40000000</baseAddress>
  <registers>
    <register>
      <name>CTRL</name>
      <addressOffset>0x0</addressOffset>
      <fields>
        {field_xml}
      </fields>
    </register>
  </registers>
</peripheral>
"""


_READ_WRITE_ENUMS = """
<field>
  <name>MODE</name><bitOffset>0</bitOffset><bitWidth>2</bitWidth>
  <enumeratedValues>
    <usage>read</usage>
    <enumeratedValue><name>RESET</name><value>{read_reset}</value></enumeratedValue>
  </enumeratedValues>
  <enumeratedValues>
    <usage>write</usage>
    <enumeratedValue><name>RESET</name><value>3</value></enumeratedValue>
  </enumeratedValues>
</field>
"""


def test_read_and_write_containers_diff_independently(make_device: MakeDevice) -> None:
    old = make_device(_field_device(_READ_WRITE_ENUMS.format(read_reset="0")))
    new = make_device(_field_device(_READ_WRITE_ENUMS.format(read_reset="1")))
    changes = diff_devices(old, new)
    assert len(changes) == 1
    assert changes[0].kind == "modified"
    assert changes[0].attribute == "value"
    assert (changes[0].before, changes[0].after) == (0, 1)


def test_removing_read_container_is_detected(make_device: MakeDevice) -> None:
    write_only = """
<field>
  <name>MODE</name><bitOffset>0</bitOffset><bitWidth>2</bitWidth>
  <enumeratedValues>
    <usage>write</usage>
    <enumeratedValue><name>RESET</name><value>3</value></enumeratedValue>
  </enumeratedValues>
</field>
"""
    old = make_device(_field_device(_READ_WRITE_ENUMS.format(read_reset="0")))
    new = make_device(_field_device(write_only))
    changes = diff_devices(old, new)
    assert [c.kind for c in changes] == ["removed"]
    assert changes[0].path == "P1.CTRL.MODE.RESET"


def test_derived_field_own_bitrange_wins(make_device: MakeDevice) -> None:
    xml = """
<field><name>BASEF</name><bitOffset>0</bitOffset><bitWidth>1</bitWidth></field>
<field derivedFrom="BASEF"><name>F2</name><bitRange>[11:8]</bitRange></field>
"""
    reg = make_device(_field_device(xml)).peripherals[0].children[0]
    assert isinstance(reg, Register)
    f2 = reg.fields[1]
    assert (f2.bit_offset, f2.bit_width) == (8, 4)


def test_derived_field_partial_redefinition_does_not_mix_styles(
    make_device: MakeDevice,
) -> None:
    # Derived defines only bitOffset: the base's lsb/msb must not leak in;
    # width falls back to the bitOffset-style default of 1.
    xml = """
<field><name>BASEF</name><lsb>0</lsb><msb>3</msb></field>
<field derivedFrom="BASEF"><name>F2</name><bitOffset>8</bitOffset></field>
"""
    reg = make_device(_field_device(xml)).peripherals[0].children[0]
    assert isinstance(reg, Register)
    f2 = reg.fields[1]
    assert (f2.bit_offset, f2.bit_width) == (8, 1)


def test_omitted_usage_normalizes_to_read_write(make_device: MakeDevice) -> None:
    explicit = """
<field>
  <name>MODE</name><bitOffset>0</bitOffset><bitWidth>1</bitWidth>
  <enumeratedValues>
    <usage>read-write</usage>
    <enumeratedValue><name>OFF</name><value>0</value></enumeratedValue>
  </enumeratedValues>
</field>
"""
    omitted = explicit.replace("<usage>read-write</usage>", "")
    old = make_device(_field_device(explicit))
    new = make_device(_field_device(omitted))
    assert diff_devices(old, new) == []


def test_sibling_wins_over_nested_cluster_match(make_device: MakeDevice) -> None:
    periph = """
<peripheral>
  <name>P1</name>
  <baseAddress>0x40000000</baseAddress>
  <registers>
    <cluster>
      <name>C</name>
      <addressOffset>0x100</addressOffset>
      <register><name>FOO</name><addressOffset>0x0</addressOffset><resetValue>0xDEAD</resetValue></register>
    </cluster>
    <register derivedFrom="FOO"><name>BAR</name><addressOffset>0x8</addressOffset></register>
    <register><name>FOO</name><addressOffset>0x4</addressOffset><resetValue>0x1</resetValue></register>
  </registers>
</peripheral>
"""
    dev = make_device(periph)
    bar = next(c for c in dev.peripherals[0].children if c.name == "BAR")
    assert isinstance(bar, Register)
    assert bar.reset_value == 0x1  # the same-scope sibling, not C.FOO


def test_unqualified_ref_does_not_cross_peripherals(make_device: MakeDevice) -> None:
    periphs = """
<peripheral>
  <name>P1</name>
  <baseAddress>0x40000000</baseAddress>
  <registers>
    <register><name>REMOTE</name><addressOffset>0x0</addressOffset></register>
  </registers>
</peripheral>
<peripheral>
  <name>P2</name>
  <baseAddress>0x40001000</baseAddress>
  <registers>
    <register derivedFrom="REMOTE"><name>LOCAL</name><addressOffset>0x0</addressOffset></register>
  </registers>
</peripheral>
"""
    with pytest.raises(SvdParseError, match="REMOTE"):
        make_device(periphs)


def test_dotted_ref_still_crosses_peripherals(make_device: MakeDevice) -> None:
    periphs = """
<peripheral>
  <name>P1</name>
  <baseAddress>0x40000000</baseAddress>
  <registers>
    <register><name>REMOTE</name><addressOffset>0x0</addressOffset><resetValue>0x7</resetValue></register>
  </registers>
</peripheral>
<peripheral>
  <name>P2</name>
  <baseAddress>0x40001000</baseAddress>
  <registers>
    <register derivedFrom="P1.REMOTE">
      <name>LOCAL</name><addressOffset>0x0</addressOffset>
    </register>
  </registers>
</peripheral>
"""
    dev = make_device(periphs)
    local = dev.peripherals[1].children[0]
    assert isinstance(local, Register)
    assert local.reset_value == 0x7
