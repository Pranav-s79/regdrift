"""dim/dimIncrement/dimIndex array expansion, including derived+dimmed and nested clusters."""

import pytest

from conftest import MakeDevice
from regdrift.model import Cluster, Register
from regdrift.parse import SvdParseError


def _periph(registers: str) -> str:
    return f"""
<peripheral>
  <name>P1</name>
  <baseAddress>0x40000000</baseAddress>
  <registers>
    {registers}
  </registers>
</peripheral>
"""


def test_register_array_expansion(make_device: MakeDevice) -> None:
    dev = make_device(
        _periph(
            """
<register>
  <name>CH%s</name>
  <dim>4</dim><dimIncrement>4</dimIncrement>
  <addressOffset>0x10</addressOffset>
</register>
"""
        )
    )
    regs = dev.peripherals[0].children
    assert [r.name for r in regs] == ["CH0", "CH1", "CH2", "CH3"]
    assert [r.address_offset for r in regs] == [0x10, 0x14, 0x18, 0x1C]
    assert regs[0].dim is not None
    assert regs[0].dim.count == 4
    assert regs[0].dim.increment == 4
    assert regs[2].dim is not None
    assert regs[2].dim.index == "2"


def test_bracket_array_form(make_device: MakeDevice) -> None:
    dev = make_device(
        _periph(
            """
<register>
  <name>CH[%s]</name>
  <dim>2</dim><dimIncrement>4</dimIncrement>
  <addressOffset>0x0</addressOffset>
</register>
"""
        )
    )
    assert [r.name for r in dev.peripherals[0].children] == ["CH0", "CH1"]


def test_dim_index_numeric_range(make_device: MakeDevice) -> None:
    dev = make_device(
        _periph(
            """
<register>
  <name>CH%s</name>
  <dim>4</dim><dimIncrement>4</dimIncrement><dimIndex>3-6</dimIndex>
  <addressOffset>0x0</addressOffset>
</register>
"""
        )
    )
    assert [r.name for r in dev.peripherals[0].children] == ["CH3", "CH4", "CH5", "CH6"]


def test_dim_index_comma_list(make_device: MakeDevice) -> None:
    dev = make_device(
        _periph(
            """
<register>
  <name>CH_%s</name>
  <dim>3</dim><dimIncrement>4</dimIncrement><dimIndex>A,B,C</dimIndex>
  <addressOffset>0x0</addressOffset>
</register>
"""
        )
    )
    assert [r.name for r in dev.peripherals[0].children] == ["CH_A", "CH_B", "CH_C"]


def test_dim_index_letter_range(make_device: MakeDevice) -> None:
    dev = make_device(
        _periph(
            """
<register>
  <name>CH%s</name>
  <dim>3</dim><dimIncrement>4</dimIncrement><dimIndex>A-C</dimIndex>
  <addressOffset>0x0</addressOffset>
</register>
"""
        )
    )
    assert [r.name for r in dev.peripherals[0].children] == ["CHA", "CHB", "CHC"]


def test_dim_index_count_mismatch_raises(make_device: MakeDevice) -> None:
    with pytest.raises(SvdParseError, match="dimIndex"):
        make_device(
            _periph(
                """
<register>
  <name>CH%s</name>
  <dim>4</dim><dimIncrement>4</dimIncrement><dimIndex>A,B</dimIndex>
  <addressOffset>0x0</addressOffset>
</register>
"""
            )
        )


def test_cluster_dim_expansion(make_device: MakeDevice) -> None:
    dev = make_device(
        _periph(
            """
<cluster>
  <name>CH%s</name>
  <dim>2</dim><dimIncrement>0x10</dimIncrement>
  <addressOffset>0x20</addressOffset>
  <register><name>CFG</name><addressOffset>0x0</addressOffset></register>
</cluster>
"""
        )
    )
    clusters = dev.peripherals[0].children
    assert [c.name for c in clusters] == ["CH0", "CH1"]
    assert [c.address_offset for c in clusters] == [0x20, 0x30]
    assert all(isinstance(c, Cluster) and c.children[0].name == "CFG" for c in clusters)


def test_nested_clusters(make_device: MakeDevice) -> None:
    dev = make_device(
        _periph(
            """
<cluster>
  <name>OUTER</name>
  <addressOffset>0x100</addressOffset>
  <cluster>
    <name>INNER</name>
    <addressOffset>0x8</addressOffset>
    <register><name>DATA</name><addressOffset>0x4</addressOffset></register>
  </cluster>
</cluster>
"""
        )
    )
    outer = dev.peripherals[0].children[0]
    assert isinstance(outer, Cluster)
    inner = outer.children[0]
    assert isinstance(inner, Cluster)
    assert inner.address_offset == 0x8
    reg = inner.children[0]
    assert isinstance(reg, Register)
    assert reg.address_offset == 0x4


def test_field_dim_expansion(make_device: MakeDevice) -> None:
    dev = make_device(
        _periph(
            """
<register>
  <name>IRQ</name>
  <addressOffset>0x0</addressOffset>
  <fields>
    <field>
      <name>BIT%s</name>
      <dim>2</dim><dimIncrement>1</dimIncrement>
      <bitOffset>4</bitOffset><bitWidth>1</bitWidth>
    </field>
  </fields>
</register>
"""
        )
    )
    reg = dev.peripherals[0].children[0]
    assert isinstance(reg, Register)
    assert [(f.name, f.bit_offset) for f in reg.fields] == [("BIT0", 4), ("BIT1", 5)]


def test_derived_and_dimmed(make_device: MakeDevice) -> None:
    dev = make_device(
        _periph(
            """
<register>
  <name>TEMPLATE</name>
  <addressOffset>0x0</addressOffset>
  <fields>
    <field><name>EN</name><bitOffset>0</bitOffset><bitWidth>1</bitWidth></field>
  </fields>
</register>
<register derivedFrom="TEMPLATE">
  <name>CH%s</name>
  <dim>2</dim><dimIncrement>4</dimIncrement>
  <addressOffset>0x100</addressOffset>
</register>
"""
        )
    )
    regs = dev.peripherals[0].children
    assert [r.name for r in regs] == ["TEMPLATE", "CH0", "CH1"]
    ch1 = regs[2]
    assert isinstance(ch1, Register)
    assert ch1.address_offset == 0x104
    assert ch1.fields[0].name == "EN"  # fields came from the base


def test_peripheral_dim_expansion(make_device: MakeDevice) -> None:
    dev = make_device(
        """
<peripheral>
  <name>DMA%s</name>
  <dim>2</dim><dimIncrement>0x1000</dimIncrement>
  <baseAddress>0x40000000</baseAddress>
  <registers>
    <register><name>CTRL</name><addressOffset>0x0</addressOffset></register>
  </registers>
</peripheral>
"""
    )
    assert [p.name for p in dev.peripherals] == ["DMA0", "DMA1"]
    assert [p.base_address for p in dev.peripherals] == [0x40000000, 0x40001000]
