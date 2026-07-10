"""modifiedWriteValues / readAction: write and read side-effect semantics.

The audit's F2 false green: a field flipping oneToClear -> oneToSet inverts
what writing 1 does, and a register gaining a read side effect breaks
polling code — neither may ever produce a clean diff.
"""

from conftest import MakeDevice
from regdrift.diff import diff_devices
from regdrift.model import Register
from regdrift.rules import classify_changes


def _device(field_props: str = "", reg_props: str = "") -> str:
    return f"""
<peripheral>
  <name>P1</name>
  <baseAddress>0x40000000</baseAddress>
  <registers>
    <register>
      <name>STATUS</name>
      <addressOffset>0x0</addressOffset>
      {reg_props}
      <fields>
        <field>
          <name>ERR</name><bitOffset>0</bitOffset><bitWidth>1</bitWidth>
          {field_props}
        </field>
      </fields>
    </register>
  </registers>
</peripheral>
"""


def test_defaults_parse(make_device: MakeDevice) -> None:
    reg = make_device(_device()).peripherals[0].children[0]
    assert isinstance(reg, Register)
    assert reg.modified_write_values == "modify"
    assert reg.read_action is None
    assert reg.fields[0].modified_write_values == "modify"
    assert reg.fields[0].read_action is None


def test_explicit_values_parse(make_device: MakeDevice) -> None:
    reg = make_device(
        _device(
            field_props="<modifiedWriteValues>oneToClear</modifiedWriteValues>"
            "<readAction>clear</readAction>"
        )
    ).peripherals[0].children[0]
    assert isinstance(reg, Register)
    assert reg.fields[0].modified_write_values == "oneToClear"
    assert reg.fields[0].read_action == "clear"


def test_explicit_modify_vs_omitted_is_clean(make_device: MakeDevice) -> None:
    old = make_device(_device(field_props="<modifiedWriteValues>modify</modifiedWriteValues>"))
    new = make_device(_device())
    assert diff_devices(old, new) == []


def test_w1c_to_w1s_flip_is_breaking(make_device: MakeDevice) -> None:
    old = make_device(_device(field_props="<modifiedWriteValues>oneToClear</modifiedWriteValues>"))
    new = make_device(_device(field_props="<modifiedWriteValues>oneToSet</modifiedWriteValues>"))
    changes = diff_devices(old, new)
    assert len(changes) == 1
    assert changes[0].attribute == "modified_write_values"
    finding = classify_changes(changes)[0]
    assert (finding.rule_id, finding.severity) == ("RD017", "BREAKING")


def test_gaining_w1c_from_plain_is_breaking(make_device: MakeDevice) -> None:
    old = make_device(_device())
    new = make_device(_device(field_props="<modifiedWriteValues>oneToClear</modifiedWriteValues>"))
    changes = diff_devices(old, new)
    finding = classify_changes(changes)[0]
    assert (finding.rule_id, finding.severity) == ("RD017", "BREAKING")
    assert finding.change.before == "modify"


def test_read_action_added_is_breaking(make_device: MakeDevice) -> None:
    old = make_device(_device())
    new = make_device(_device(field_props="<readAction>clear</readAction>"))
    changes = diff_devices(old, new)
    assert len(changes) == 1
    assert changes[0].attribute == "read_action"
    finding = classify_changes(changes)[0]
    assert (finding.rule_id, finding.severity) == ("RD018", "BREAKING")
    assert "none -> clear" in finding.message


def test_register_level_semantics_diffed(make_device: MakeDevice) -> None:
    old = make_device(_device(reg_props="<readAction>clear</readAction>"))
    new = make_device(_device())
    changes = [c for c in diff_devices(old, new) if c.path == "P1.STATUS"]
    assert len(changes) == 1
    assert changes[0].attribute == "read_action"
    finding = classify_changes(changes)[0]
    assert (finding.rule_id, finding.severity) == ("RD018", "BREAKING")
