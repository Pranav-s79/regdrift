"""Register-properties inheritance cascade: device -> peripheral -> cluster -> register -> field."""

from conftest import MakeDevice

REG = """
<register>
  <name>R1</name>
  <addressOffset>0x0</addressOffset>
  {props}
  <fields>
    <field><name>F1</name><bitOffset>0</bitOffset><bitWidth>1</bitWidth>{field_props}</field>
  </fields>
</register>
"""


def _peripheral(reg_props: str = "", periph_props: str = "", field_props: str = "") -> str:
    return f"""
<peripheral>
  <name>P1</name>
  <baseAddress>0x40000000</baseAddress>
  {periph_props}
  <registers>
    {REG.format(props=reg_props, field_props=field_props)}
  </registers>
</peripheral>
"""


def test_spec_defaults_when_device_silent(make_device: MakeDevice) -> None:
    reg = make_device(_peripheral()).peripherals[0].children[0]
    assert reg.size == 32
    assert reg.access == "read-write"
    assert reg.reset_value == 0
    assert reg.reset_mask == 0xFFFFFFFF


def test_device_props_cascade_to_register(make_device: MakeDevice) -> None:
    dev = make_device(
        _peripheral(),
        device_props="<size>16</size><access>read-only</access>"
        "<resetValue>0xABCD</resetValue><resetMask>0xFFFF</resetMask>",
    )
    reg = dev.peripherals[0].children[0]
    assert reg.size == 16
    assert reg.access == "read-only"
    assert reg.reset_value == 0xABCD
    assert reg.reset_mask == 0xFFFF


def test_peripheral_overrides_device(make_device: MakeDevice) -> None:
    dev = make_device(
        _peripheral(periph_props="<size>8</size>"),
        device_props="<size>16</size>",
    )
    assert dev.peripherals[0].children[0].size == 8


def test_register_overrides_peripheral(make_device: MakeDevice) -> None:
    dev = make_device(
        _peripheral(reg_props="<size>64</size>", periph_props="<size>8</size>"),
        device_props="<size>16</size>",
    )
    assert dev.peripherals[0].children[0].size == 64


def test_access_cascades_into_field(make_device: MakeDevice) -> None:
    dev = make_device(_peripheral(periph_props="<access>read-only</access>"))
    reg = dev.peripherals[0].children[0]
    assert reg.fields[0].access == "read-only"


def test_field_access_override_wins(make_device: MakeDevice) -> None:
    dev = make_device(
        _peripheral(
            periph_props="<access>read-only</access>",
            field_props="<access>write-only</access>",
        )
    )
    assert dev.peripherals[0].children[0].fields[0].access == "write-only"


def test_cluster_props_cascade_to_children(make_device: MakeDevice) -> None:
    dev = make_device(
        """
<peripheral>
  <name>P1</name>
  <baseAddress>0x40000000</baseAddress>
  <registers>
    <cluster>
      <name>C1</name>
      <addressOffset>0x10</addressOffset>
      <size>8</size>
      <register><name>R1</name><addressOffset>0x0</addressOffset></register>
    </cluster>
  </registers>
</peripheral>
""",
        device_props="<size>32</size>",
    )
    cluster = dev.peripherals[0].children[0]
    assert cluster.kind == "cluster"
    assert cluster.children[0].size == 8
