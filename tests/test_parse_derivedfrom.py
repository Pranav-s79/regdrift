"""derivedFrom resolution at peripheral, register, cluster, field, and enumeratedValues levels."""

import pytest

from conftest import MakeDevice
from regdrift.model import Register
from regdrift.parse import SvdParseError

BASE_UART = """
<peripheral>
  <name>UART0</name>
  <baseAddress>0x40000000</baseAddress>
  <description>Base UART</description>
  <registers>
    <register>
      <name>CTRL</name>
      <addressOffset>0x0</addressOffset>
      <resetValue>0x1</resetValue>
      <fields>
        <field><name>EN</name><bitOffset>0</bitOffset><bitWidth>1</bitWidth></field>
      </fields>
    </register>
  </registers>
</peripheral>
"""

DERIVED_UART = """
<peripheral derivedFrom="UART0">
  <name>UART1</name>
  <baseAddress>0x40001000</baseAddress>
</peripheral>
"""


def test_peripheral_derived_copies_registers(make_device: MakeDevice) -> None:
    dev = make_device(BASE_UART + DERIVED_UART)
    uart1 = dev.peripherals[1]
    assert uart1.name == "UART1"
    assert uart1.base_address == 0x40001000
    assert uart1.description == "Base UART"  # inherited
    reg = uart1.children[0]
    assert isinstance(reg, Register)
    assert reg.name == "CTRL"
    assert reg.reset_value == 0x1
    assert reg.fields[0].name == "EN"


def test_forward_reference(make_device: MakeDevice) -> None:
    # Derived peripheral appears in the file before its base.
    dev = make_device(DERIVED_UART + BASE_UART)
    uart1 = dev.peripherals[0]
    assert uart1.name == "UART1"
    assert uart1.children[0].name == "CTRL"


def test_chained_derivation(make_device: MakeDevice) -> None:
    uart2 = """
<peripheral derivedFrom="UART1">
  <name>UART2</name>
  <baseAddress>0x40002000</baseAddress>
</peripheral>
"""
    dev = make_device(uart2 + DERIVED_UART + BASE_UART)
    assert [p.name for p in dev.peripherals] == ["UART2", "UART1", "UART0"]
    assert dev.peripherals[0].children[0].name == "CTRL"


def test_derived_own_children_replace_base(make_device: MakeDevice) -> None:
    override = """
<peripheral derivedFrom="UART0">
  <name>UART1</name>
  <baseAddress>0x40001000</baseAddress>
  <registers>
    <register><name>STATUS</name><addressOffset>0x8</addressOffset></register>
  </registers>
</peripheral>
"""
    dev = make_device(BASE_UART + override)
    assert [r.name for r in dev.peripherals[1].children] == ["STATUS"]


def test_register_derived_within_peripheral(make_device: MakeDevice) -> None:
    periph = """
<peripheral>
  <name>P1</name>
  <baseAddress>0x40000000</baseAddress>
  <registers>
    <register>
      <name>CTRL</name>
      <addressOffset>0x0</addressOffset>
      <fields>
        <field><name>EN</name><bitOffset>0</bitOffset><bitWidth>1</bitWidth></field>
      </fields>
    </register>
    <register derivedFrom="CTRL">
      <name>CTRL_B</name>
      <addressOffset>0x4</addressOffset>
    </register>
  </registers>
</peripheral>
"""
    dev = make_device(periph)
    ctrl_b = dev.peripherals[0].children[1]
    assert isinstance(ctrl_b, Register)
    assert ctrl_b.address_offset == 0x4
    assert ctrl_b.fields[0].name == "EN"


def test_register_derived_dotted_across_peripherals(make_device: MakeDevice) -> None:
    other = """
<peripheral>
  <name>P2</name>
  <baseAddress>0x40002000</baseAddress>
  <registers>
    <register derivedFrom="UART0.CTRL">
      <name>MIRROR</name>
      <addressOffset>0x0</addressOffset>
    </register>
  </registers>
</peripheral>
"""
    dev = make_device(BASE_UART + other)
    mirror = dev.peripherals[1].children[0]
    assert isinstance(mirror, Register)
    assert mirror.fields[0].name == "EN"
    assert mirror.reset_value == 0x1  # inherited prop from base register


def test_field_derived(make_device: MakeDevice) -> None:
    periph = """
<peripheral>
  <name>P1</name>
  <baseAddress>0x40000000</baseAddress>
  <registers>
    <register>
      <name>CTRL</name>
      <addressOffset>0x0</addressOffset>
      <fields>
        <field>
          <name>EN</name><bitOffset>0</bitOffset><bitWidth>1</bitWidth>
          <enumeratedValues>
            <name>EN_VALS</name>
            <enumeratedValue><name>OFF</name><value>0</value></enumeratedValue>
            <enumeratedValue><name>ON</name><value>1</value></enumeratedValue>
          </enumeratedValues>
        </field>
        <field derivedFrom="EN"><name>EN2</name><bitOffset>4</bitOffset></field>
      </fields>
    </register>
  </registers>
</peripheral>
"""
    dev = make_device(periph)
    en2 = dev.peripherals[0].children[0].fields[1]
    assert en2.name == "EN2"
    assert en2.bit_offset == 4
    assert en2.bit_width == 1  # inherited
    assert [e.name for e in en2.enumerated_values] == ["OFF", "ON"]


def test_enumerated_values_derived(make_device: MakeDevice) -> None:
    periph = """
<peripheral>
  <name>P1</name>
  <baseAddress>0x40000000</baseAddress>
  <registers>
    <register>
      <name>CTRL</name>
      <addressOffset>0x0</addressOffset>
      <fields>
        <field>
          <name>EN</name><bitOffset>0</bitOffset><bitWidth>1</bitWidth>
          <enumeratedValues>
            <name>ONOFF</name>
            <enumeratedValue><name>OFF</name><value>0</value></enumeratedValue>
            <enumeratedValue><name>ON</name><value>1</value></enumeratedValue>
          </enumeratedValues>
        </field>
        <field>
          <name>EN2</name><bitOffset>1</bitOffset><bitWidth>1</bitWidth>
          <enumeratedValues derivedFrom="ONOFF"/>
        </field>
      </fields>
    </register>
  </registers>
</peripheral>
"""
    dev = make_device(periph)
    en2 = dev.peripherals[0].children[0].fields[1]
    assert [e.name for e in en2.enumerated_values] == ["OFF", "ON"]
    assert [e.value for e in en2.enumerated_values] == [0, 1]


def test_cluster_derived(make_device: MakeDevice) -> None:
    periph = """
<peripheral>
  <name>P1</name>
  <baseAddress>0x40000000</baseAddress>
  <registers>
    <cluster>
      <name>CH_A</name>
      <addressOffset>0x0</addressOffset>
      <register><name>CFG</name><addressOffset>0x0</addressOffset></register>
    </cluster>
    <cluster derivedFrom="CH_A">
      <name>CH_B</name>
      <addressOffset>0x100</addressOffset>
    </cluster>
  </registers>
</peripheral>
"""
    dev = make_device(periph)
    ch_b = dev.peripherals[0].children[1]
    assert ch_b.kind == "cluster"
    assert ch_b.address_offset == 0x100
    assert ch_b.children[0].name == "CFG"


def test_cycle_raises(make_device: MakeDevice) -> None:
    cyclic = """
<peripheral derivedFrom="B"><name>A</name><baseAddress>0x0</baseAddress></peripheral>
<peripheral derivedFrom="A"><name>B</name><baseAddress>0x1000</baseAddress></peripheral>
"""
    with pytest.raises(SvdParseError, match="cycle"):
        make_device(cyclic)


def test_missing_target_raises(make_device: MakeDevice) -> None:
    orphan = """
<peripheral derivedFrom="GHOST"><name>A</name><baseAddress>0x0</baseAddress></peripheral>
"""
    with pytest.raises(SvdParseError, match="GHOST"):
        make_device(orphan)
