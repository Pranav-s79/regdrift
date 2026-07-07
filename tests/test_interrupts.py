"""Interrupt modeling: parse, derivedFrom semantics, diff, and rules.

An IRQ renumber relocates the vector-table entry while old code still
compiles — the textbook silent break. Interrupts therefore must never be
invisible to the diff.
"""

from conftest import MakeDevice
from regdrift.diff import Change, diff_devices
from regdrift.rules import classify_changes

BASE_TIMER = """
<peripheral>
  <name>TIMER0</name>
  <baseAddress>0x40010000</baseAddress>
  <interrupt>
    <name>TIMER0</name>
    <value>{value}</value>
    <description>Timer 0 overflow</description>
  </interrupt>
  <registers>
    <register><name>CR</name><addressOffset>0x0</addressOffset></register>
  </registers>
</peripheral>
"""


def test_interrupts_parsed(make_device: MakeDevice) -> None:
    dev = make_device(BASE_TIMER.format(value="3"))
    timer = dev.peripherals[0]
    assert len(timer.interrupts) == 1
    irq = timer.interrupts[0]
    assert (irq.name, irq.value, irq.description) == ("TIMER0", 3, "Timer 0 overflow")


def test_derived_peripheral_with_own_interrupt_still_inherits_registers(
    make_device: MakeDevice,
) -> None:
    # The ARM_Sample pattern: TIMER1 derives from TIMER0, defines ONLY its
    # own interrupt — it must get its own IRQ *and* the base's registers.
    derived = """
<peripheral derivedFrom="TIMER0">
  <name>TIMER1</name>
  <baseAddress>0x40010100</baseAddress>
  <interrupt><name>TIMER1</name><value>4</value></interrupt>
</peripheral>
"""
    dev = make_device(BASE_TIMER.format(value="0") + derived)
    timer1 = dev.peripherals[1]
    assert [i.name for i in timer1.interrupts] == ["TIMER1"]
    assert timer1.interrupts[0].value == 4
    assert [r.name for r in timer1.children] == ["CR"]  # registers inherited


def test_derived_peripheral_without_interrupt_inherits_base_interrupt(
    make_device: MakeDevice,
) -> None:
    derived = """
<peripheral derivedFrom="TIMER0">
  <name>TIMER1</name>
  <baseAddress>0x40010100</baseAddress>
</peripheral>
"""
    dev = make_device(BASE_TIMER.format(value="0") + derived)
    timer1 = dev.peripherals[1]
    assert [i.name for i in timer1.interrupts] == ["TIMER0"]
    assert timer1.interrupts[0].value == 0


def test_interrupt_renumber_detected_and_breaking(make_device: MakeDevice) -> None:
    old = make_device(BASE_TIMER.format(value="3"))
    new = make_device(BASE_TIMER.format(value="7"))
    changes = diff_devices(old, new)
    assert changes == [
        Change(
            kind="modified",
            element="interrupt",
            path="TIMER0.TIMER0",
            attribute="value",
            before=3,
            after=7,
        )
    ]
    finding = classify_changes(changes)[0]
    assert (finding.rule_id, finding.severity) == ("RD015", "BREAKING")


def test_interrupt_removed_detected_and_breaking(make_device: MakeDevice) -> None:
    no_irq = """
<peripheral>
  <name>TIMER0</name>
  <baseAddress>0x40010000</baseAddress>
  <registers>
    <register><name>CR</name><addressOffset>0x0</addressOffset></register>
  </registers>
</peripheral>
"""
    old = make_device(BASE_TIMER.format(value="3"))
    new = make_device(no_irq)
    changes = diff_devices(old, new)
    assert [c.kind for c in changes] == ["removed"]
    finding = classify_changes(changes)[0]
    assert (finding.rule_id, finding.severity) == ("RD016", "BREAKING")


def test_interrupt_added_is_safe(make_device: MakeDevice) -> None:
    second = BASE_TIMER.format(value="3").replace(
        "</interrupt>",
        "</interrupt><interrupt><name>TIMER0_CAPTURE</name><value>9</value></interrupt>",
        1,
    )
    old = make_device(BASE_TIMER.format(value="3"))
    new = make_device(second)
    changes = diff_devices(old, new)
    assert [c.kind for c in changes] == ["added"]
    finding = classify_changes(changes)[0]
    assert (finding.rule_id, finding.severity) == ("RD020", "SAFE")


def test_interrupt_description_change_is_safe(make_device: MakeDevice) -> None:
    old = make_device(BASE_TIMER.format(value="3"))
    new = make_device(
        BASE_TIMER.format(value="3").replace("Timer 0 overflow", "Timer 0 overflow event")
    )
    changes = diff_devices(old, new)
    assert [c.attribute for c in changes] == ["description"]
    finding = classify_changes(changes)[0]
    assert (finding.rule_id, finding.severity) == ("RD030", "SAFE")


def test_dimmed_peripheral_instances_share_interrupts(make_device: MakeDevice) -> None:
    dimmed = """
<peripheral>
  <name>DMA%s</name>
  <dim>2</dim><dimIncrement>0x1000</dimIncrement>
  <baseAddress>0x40000000</baseAddress>
  <interrupt><name>DMA</name><value>11</value></interrupt>
  <registers>
    <register><name>CTRL</name><addressOffset>0x0</addressOffset></register>
  </registers>
</peripheral>
"""
    dev = make_device(dimmed)
    assert [p.interrupts[0].value for p in dev.peripherals] == [11, 11]
