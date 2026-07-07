"""Regression tests for the adversarial-audit findings (F1, F3).

F1: duplicate same-named entries within ONE enumeratedValues container must
    not collapse (last-wins dict produced a clean diff on entry removal).
F3: relative dotted derivedFrom refs must prefer the innermost enclosing
    scope (nearest-wins), matching the resolver's documented intent.
"""

from conftest import MakeDevice
from regdrift.diff import diff_devices
from regdrift.model import Register


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


_DUP_ENUMS = """
<field>
  <name>MODE</name><bitOffset>0</bitOffset><bitWidth>2</bitWidth>
  <enumeratedValues>
    {entries}
  </enumeratedValues>
</field>
"""

_DUP0 = "<enumeratedValue><name>DUP</name><value>0</value></enumeratedValue>"
_DUP1 = "<enumeratedValue><name>DUP</name><value>1</value></enumeratedValue>"


def test_duplicate_entries_in_one_container_removal_detected(
    make_device: MakeDevice,
) -> None:
    old = make_device(_field_device(_DUP_ENUMS.format(entries=_DUP0 + _DUP1)))
    new = make_device(_field_device(_DUP_ENUMS.format(entries=_DUP1)))
    changes = diff_devices(old, new)
    assert [c.kind for c in changes] == ["removed"]
    assert changes[0].path == "P1.CTRL.MODE.DUP"


def test_duplicate_entries_addition_detected(make_device: MakeDevice) -> None:
    old = make_device(_field_device(_DUP_ENUMS.format(entries=_DUP1)))
    new = make_device(_field_device(_DUP_ENUMS.format(entries=_DUP0 + _DUP1)))
    changes = diff_devices(old, new)
    assert [c.kind for c in changes] == ["added"]


def test_duplicate_entries_reorder_is_clean(make_device: MakeDevice) -> None:
    old = make_device(_field_device(_DUP_ENUMS.format(entries=_DUP0 + _DUP1)))
    new = make_device(_field_device(_DUP_ENUMS.format(entries=_DUP1 + _DUP0)))
    assert diff_devices(old, new) == []


def test_dotted_relative_ref_prefers_innermost_scope(make_device: MakeDevice) -> None:
    # Both the peripheral and the enclosing cluster contain a C.R; the
    # derived register sits inside OUTERC, so OUTERC's C.R (0x22) must win.
    periph = """
<peripheral>
  <name>P1</name>
  <baseAddress>0x40000000</baseAddress>
  <registers>
    <cluster>
      <name>C</name>
      <addressOffset>0x0</addressOffset>
      <register><name>R</name><addressOffset>0x0</addressOffset><resetValue>0x11</resetValue></register>
    </cluster>
    <cluster>
      <name>OUTERC</name>
      <addressOffset>0x100</addressOffset>
      <cluster>
        <name>C</name>
        <addressOffset>0x0</addressOffset>
        <register><name>R</name><addressOffset>0x0</addressOffset><resetValue>0x22</resetValue></register>
      </cluster>
      <register derivedFrom="C.R">
        <name>DR</name><addressOffset>0x40</addressOffset>
      </register>
    </cluster>
  </registers>
</peripheral>
"""
    dev = make_device(periph)
    outerc = next(c for c in dev.peripherals[0].children if c.name == "OUTERC")
    assert not isinstance(outerc, Register)
    dr = next(c for c in outerc.children if c.name == "DR")
    assert isinstance(dr, Register)
    assert dr.reset_value == 0x22  # innermost scope wins, not P1.C.R's 0x11
