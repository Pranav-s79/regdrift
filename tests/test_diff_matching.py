"""Diff engine three-phase matching: name match, moved detection, rename heuristic."""

from conftest import MakeDevice
from regdrift.diff import Change, diff_devices


def _uart(registers: str, name: str = "UART0", base: str = "0x40000000") -> str:
    return f"""
<peripheral>
  <name>{name}</name>
  <baseAddress>{base}</baseAddress>
  <registers>
    {registers}
  </registers>
</peripheral>
"""


CTRL = """
<register>
  <name>CTRL</name>
  <addressOffset>{offset}</addressOffset>
  <fields>
    <field><name>EN</name><bitOffset>0</bitOffset><bitWidth>1</bitWidth></field>
  </fields>
</register>
"""


def test_identity_diff_is_empty(make_device: MakeDevice) -> None:
    dev = make_device(_uart(CTRL.format(offset="0x0")))
    assert diff_devices(dev, dev) == []


def test_added_register(make_device: MakeDevice) -> None:
    old = make_device(_uart(CTRL.format(offset="0x0")))
    new = make_device(
        _uart(
            CTRL.format(offset="0x0")
            + "<register><name>STATUS</name><addressOffset>0x4</addressOffset></register>"
        )
    )
    assert diff_devices(old, new) == [
        Change(kind="added", element="register", path="UART0.STATUS")
    ]


def test_removed_register(make_device: MakeDevice) -> None:
    old = make_device(
        _uart(
            CTRL.format(offset="0x0")
            + "<register><name>STATUS</name><addressOffset>0x4</addressOffset></register>"
        )
    )
    new = make_device(_uart(CTRL.format(offset="0x0")))
    assert diff_devices(old, new) == [
        Change(kind="removed", element="register", path="UART0.STATUS")
    ]


def test_moved_register(make_device: MakeDevice) -> None:
    old = make_device(_uart(CTRL.format(offset="0x0")))
    new = make_device(_uart(CTRL.format(offset="0x8")))
    assert diff_devices(old, new) == [
        Change(
            kind="moved",
            element="register",
            path="UART0.CTRL",
            attribute="address_offset",
            before=0x0,
            after=0x8,
        )
    ]


def test_renamed_register_full_confidence(make_device: MakeDevice) -> None:
    reg = """
<register>
  <name>{name}</name>
  <description>Control register</description>
  <addressOffset>0x0</addressOffset>
  <fields>
    <field><name>EN</name><bitOffset>0</bitOffset><bitWidth>1</bitWidth></field>
  </fields>
</register>
"""
    old = make_device(_uart(reg.format(name="CTRL")))
    new = make_device(_uart(reg.format(name="CONTROL")))
    changes = diff_devices(old, new)
    assert changes == [
        Change(
            kind="renamed",
            element="register",
            path="UART0.CONTROL",
            attribute="name",
            before="CTRL",
            after="CONTROL",
            confidence=1.0,
        )
    ]


def test_renamed_register_lower_confidence_when_description_differs(
    make_device: MakeDevice,
) -> None:
    reg = """
<register>
  <name>{name}</name>
  <description>{desc}</description>
  <addressOffset>0x0</addressOffset>
</register>
"""
    old = make_device(_uart(reg.format(name="CTRL", desc="old words")))
    new = make_device(_uart(reg.format(name="CONTROL", desc="new words")))
    changes = diff_devices(old, new)
    renames = [c for c in changes if c.kind == "renamed"]
    assert len(renames) == 1
    assert renames[0].confidence == 0.8
    # the description difference is still reported, under the new name
    assert any(
        c.kind == "modified" and c.attribute == "description" and c.path == "UART0.CONTROL"
        for c in changes
    )


def test_ambiguous_rename_falls_back_to_add_remove(make_device: MakeDevice) -> None:
    # Two identically-shaped old registers disappear, one new appears at a
    # different name: structure alone can't tell which one it was.
    def regs(names: list[str]) -> str:
        return "".join(
            f"<register><name>{n}</name><addressOffset>0x0</addressOffset></register>"
            for n in names
        )

    # Same offset+structure on both old registers (offset 0x0 each — SVD
    # allows overlapping registers) makes the rename candidates ambiguous.
    old = make_device(_uart(regs(["A", "B"])))
    new = make_device(_uart(regs(["C"])))
    kinds = sorted(c.kind for c in diff_devices(old, new))
    assert kinds == ["added", "removed", "removed"]


def test_rename_not_paired_when_offset_differs(make_device: MakeDevice) -> None:
    old = make_device(
        _uart("<register><name>A</name><addressOffset>0x0</addressOffset></register>")
    )
    new = make_device(
        _uart("<register><name>B</name><addressOffset>0x4</addressOffset></register>")
    )
    kinds = sorted(c.kind for c in diff_devices(old, new))
    assert kinds == ["added", "removed"]


def test_moved_peripheral(make_device: MakeDevice) -> None:
    old = make_device(_uart(CTRL.format(offset="0x0"), base="0x40000000"))
    new = make_device(_uart(CTRL.format(offset="0x0"), base="0x40010000"))
    assert diff_devices(old, new) == [
        Change(
            kind="moved",
            element="peripheral",
            path="UART0",
            attribute="base_address",
            before=0x40000000,
            after=0x40010000,
        )
    ]


def test_renamed_peripheral(make_device: MakeDevice) -> None:
    old = make_device(_uart(CTRL.format(offset="0x0"), name="UART0"))
    new = make_device(_uart(CTRL.format(offset="0x0"), name="USART0"))
    changes = diff_devices(old, new)
    assert changes == [
        Change(
            kind="renamed",
            element="peripheral",
            path="USART0",
            attribute="name",
            before="UART0",
            after="USART0",
            confidence=1.0,
        )
    ]


def test_added_and_removed_peripheral(make_device: MakeDevice) -> None:
    old = make_device(_uart(CTRL.format(offset="0x0"), name="UART0", base="0x40000000"))
    new = make_device(_uart(CTRL.format(offset="0x0"), name="SPI0", base="0x50000000"))
    kinds = sorted((c.kind, c.element, c.path) for c in diff_devices(old, new))
    assert kinds == [("added", "peripheral", "SPI0"), ("removed", "peripheral", "UART0")]


def test_cluster_moved_and_children_compared(make_device: MakeDevice) -> None:
    cluster = """
<cluster>
  <name>CH0</name>
  <addressOffset>{offset}</addressOffset>
  <register><name>CFG</name><addressOffset>0x0</addressOffset><resetValue>{reset}</resetValue></register>
</cluster>
"""
    old = make_device(_uart(cluster.format(offset="0x10", reset="0x0")))
    new = make_device(_uart(cluster.format(offset="0x20", reset="0x1")))
    changes = diff_devices(old, new)
    assert (
        Change(
            kind="moved",
            element="cluster",
            path="UART0.CH0",
            attribute="address_offset",
            before=0x10,
            after=0x20,
        )
        in changes
    )
    assert any(
        c.path == "UART0.CH0.CFG" and c.attribute == "reset_value" for c in changes
    )


def test_renamed_field(make_device: MakeDevice) -> None:
    reg = """
<register>
  <name>CTRL</name>
  <addressOffset>0x0</addressOffset>
  <fields>
    <field><name>{name}</name><bitOffset>3</bitOffset><bitWidth>1</bitWidth></field>
  </fields>
</register>
"""
    old = make_device(_uart(reg.format(name="EN")))
    new = make_device(_uart(reg.format(name="ENABLE")))
    changes = diff_devices(old, new)
    assert changes == [
        Change(
            kind="renamed",
            element="field",
            path="UART0.CTRL.ENABLE",
            attribute="name",
            before="EN",
            after="ENABLE",
            confidence=1.0,
        )
    ]


def test_register_and_cluster_with_same_name_not_confused(make_device: MakeDevice) -> None:
    old = make_device(
        _uart("<register><name>X</name><addressOffset>0x0</addressOffset></register>")
    )
    new = make_device(
        _uart(
            """
<cluster>
  <name>X</name>
  <addressOffset>0x0</addressOffset>
  <register><name>Y</name><addressOffset>0x0</addressOffset></register>
</cluster>
"""
        )
    )
    kinds = sorted((c.kind, c.element) for c in diff_devices(old, new))
    assert kinds == [("added", "cluster"), ("removed", "register")]
