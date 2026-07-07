"""Modified detection covers every attribute the spec lists."""

import pytest

from conftest import MakeDevice
from regdrift.diff import Change, diff_devices


def _device(make_device: MakeDevice, reg_props: str = "", field_props: str = "") -> str:
    return f"""
<peripheral>
  <name>UART0</name>
  <baseAddress>0x40000000</baseAddress>
  <registers>
    <register>
      <name>CTRL</name>
      <addressOffset>0x0</addressOffset>
      {reg_props}
      <fields>
        <field>
          <name>MODE</name>
          <bitOffset>2</bitOffset><bitWidth>2</bitWidth>
          {field_props}
        </field>
      </fields>
    </register>
  </registers>
</peripheral>
"""


@pytest.mark.parametrize(
    ("old_prop", "new_prop", "attribute", "before", "after"),
    [
        ("<size>32</size>", "<size>16</size>", "size", 32, 16),
        (
            "<access>read-write</access>",
            "<access>read-only</access>",
            "access",
            "read-write",
            "read-only",
        ),
        ("<resetValue>0x0</resetValue>", "<resetValue>0x5</resetValue>", "reset_value", 0, 5),
        (
            "<resetMask>0xFFFFFFFF</resetMask>",
            "<resetMask>0xFF</resetMask>",
            "reset_mask",
            0xFFFFFFFF,
            0xFF,
        ),
        (
            "<protection>n</protection>",
            "<protection>s</protection>",
            "protection",
            "n",
            "s",
        ),
        (
            "<description>old text</description>",
            "<description>new text</description>",
            "description",
            "old text",
            "new text",
        ),
    ],
)
def test_register_attribute_modified(
    make_device: MakeDevice,
    old_prop: str,
    new_prop: str,
    attribute: str,
    before: object,
    after: object,
) -> None:
    old = make_device(_device(make_device, reg_props=old_prop))
    new = make_device(_device(make_device, reg_props=new_prop))
    changes = diff_devices(old, new)
    reg_changes = [c for c in changes if c.path == "UART0.CTRL"]
    assert reg_changes == [
        Change(
            kind="modified",
            element="register",
            path="UART0.CTRL",
            attribute=attribute,
            before=before,  # type: ignore[arg-type]
            after=after,  # type: ignore[arg-type]
        )
    ]


def test_field_bit_position_modified(make_device: MakeDevice) -> None:
    old = make_device(_device(make_device))
    new_xml = _device(make_device).replace("<bitOffset>2</bitOffset>", "<bitOffset>4</bitOffset>")
    new = make_device(new_xml)
    assert diff_devices(old, new) == [
        Change(
            kind="modified",
            element="field",
            path="UART0.CTRL.MODE",
            attribute="bit_range",
            before="[3:2]",
            after="[5:4]",
        )
    ]


def test_field_bit_width_modified(make_device: MakeDevice) -> None:
    old = make_device(_device(make_device))
    new_xml = _device(make_device).replace("<bitWidth>2</bitWidth>", "<bitWidth>3</bitWidth>")
    new = make_device(new_xml)
    assert diff_devices(old, new) == [
        Change(
            kind="modified",
            element="field",
            path="UART0.CTRL.MODE",
            attribute="bit_range",
            before="[3:2]",
            after="[4:2]",
        )
    ]


def test_field_access_modified_via_cascade(make_device: MakeDevice) -> None:
    # Access changes at the register cascade down to the resolved field.
    old = make_device(_device(make_device, reg_props="<access>read-write</access>"))
    new = make_device(_device(make_device, reg_props="<access>read-only</access>"))
    changes = diff_devices(old, new)
    assert any(c.path == "UART0.CTRL" and c.attribute == "access" for c in changes)
    assert any(c.path == "UART0.CTRL.MODE" and c.attribute == "access" for c in changes)


_ENUMS = """
<enumeratedValues>
  <name>MODES</name>
  <enumeratedValue><name>SLOW</name><value>{slow}</value><description>{desc}</description></enumeratedValue>
  <enumeratedValue><name>FAST</name><value>1</value></enumeratedValue>
</enumeratedValues>
"""


def test_enum_value_modified(make_device: MakeDevice) -> None:
    old = make_device(_device(make_device, field_props=_ENUMS.format(slow="0", desc="d")))
    new = make_device(_device(make_device, field_props=_ENUMS.format(slow="2", desc="d")))
    assert diff_devices(old, new) == [
        Change(
            kind="modified",
            element="enum",
            path="UART0.CTRL.MODE.SLOW",
            attribute="value",
            before=0,
            after=2,
        )
    ]


def test_enum_description_modified(make_device: MakeDevice) -> None:
    old = make_device(_device(make_device, field_props=_ENUMS.format(slow="0", desc="old")))
    new = make_device(_device(make_device, field_props=_ENUMS.format(slow="0", desc="new")))
    assert diff_devices(old, new) == [
        Change(
            kind="modified",
            element="enum",
            path="UART0.CTRL.MODE.SLOW",
            attribute="description",
            before="old",
            after="new",
        )
    ]


def test_enum_added_and_removed(make_device: MakeDevice) -> None:
    only_slow = """
<enumeratedValues>
  <enumeratedValue><name>SLOW</name><value>0</value></enumeratedValue>
</enumeratedValues>
"""
    only_fast = """
<enumeratedValues>
  <enumeratedValue><name>FAST</name><value>1</value></enumeratedValue>
</enumeratedValues>
"""
    old = make_device(_device(make_device, field_props=only_slow))
    new = make_device(_device(make_device, field_props=only_fast))
    assert sorted((c.kind, c.path) for c in diff_devices(old, new)) == [
        ("added", "UART0.CTRL.MODE.FAST"),
        ("removed", "UART0.CTRL.MODE.SLOW"),
    ]


def test_peripheral_description_modified(make_device: MakeDevice) -> None:
    template = """
<peripheral>
  <name>UART0</name>
  <description>{desc}</description>
  <baseAddress>0x40000000</baseAddress>
  <registers>
    <register><name>CTRL</name><addressOffset>0x0</addressOffset></register>
  </registers>
</peripheral>
"""
    old = make_device(template.format(desc="Serial port"))
    new = make_device(template.format(desc="Serial port, now with FIFO"))
    assert diff_devices(old, new) == [
        Change(
            kind="modified",
            element="peripheral",
            path="UART0",
            attribute="description",
            before="Serial port",
            after="Serial port, now with FIFO",
        )
    ]
