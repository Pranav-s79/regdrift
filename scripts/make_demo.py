"""Regenerate demo/ (committed; test_demo.py enforces sync)."""

import sys
from pathlib import Path

V1 = """<?xml version="1.0" encoding="utf-8"?>
<device schemaVersion="1.1">
  <name>DEMOCHIP</name>
  <version>1.0</version>
  <description>Demo device for regdrift</description>
  <addressUnitBits>8</addressUnitBits>
  <width>32</width>
  <size>32</size>
  <access>read-write</access>
  <resetValue>0x0</resetValue>
  <resetMask>0xFFFFFFFF</resetMask>
  <peripherals>
    <peripheral>
      <name>ACCEL</name>
      <description>Matrix accelerator control block</description>
      <baseAddress>0x40040000</baseAddress>
      <interrupt>
        <name>ACCEL_DONE</name>
        <value>17</value>
      </interrupt>
      <registers>
        <register>
          <name>CTRL</name>
          <description>Control</description>
          <addressOffset>0x0</addressOffset>
          <fields>
            <field><name>EN</name><bitOffset>0</bitOffset><bitWidth>1</bitWidth></field>
            <field><name>MODE</name><bitOffset>1</bitOffset><bitWidth>2</bitWidth></field>
          </fields>
        </register>
        <register>
          <name>STATUS</name>
          <description>Status flags</description>
          <addressOffset>0x8</addressOffset>
          <resetValue>0x1</resetValue>
          <fields>
            <field>
              <name>DONE</name><bitOffset>0</bitOffset><bitWidth>1</bitWidth>
              <modifiedWriteValues>oneToClear</modifiedWriteValues>
            </field>
          </fields>
        </register>
      </registers>
    </peripheral>
  </peripherals>
</device>
"""

V2 = (
    V1.replace("<addressOffset>0x8</addressOffset>", "<addressOffset>0xC</addressOffset>")
    .replace("<name>EN</name>", "<name>ENABLE</name>")
    .replace(
        "<modifiedWriteValues>oneToClear</modifiedWriteValues>",
        "<modifiedWriteValues>oneToSet</modifiedWriteValues>",
    )
    .replace("<value>17</value>", "<value>18</value>")
    .replace("<resetValue>0x1</resetValue>", "<resetValue>0x0</resetValue>")
    .replace(
        "      </registers>",
        "        <register>\n"
        "          <name>RESULT</name>\n"
        "          <description>Result word</description>\n"
        "          <addressOffset>0x10</addressOffset>\n"
        "        </register>\n"
        "      </registers>",
    )
)

DEMO_README = """# regdrift demo

Two revisions of the same imaginary chip. `chip_v2.svd` sneaks in the
classic silent breaks: a moved register, a renamed field, a renumbered
interrupt, and a write-one-to-clear flag that became write-one-to-set.

```sh
regdrift check demo/chip_v1.svd demo/chip_v2.svd
```

Expected: exit code 1 with 4 breaking findings (RD001 moved register,
RD005 renamed field, RD015 renumbered interrupt, RD017 inverted write
semantics), 1 warning (RD010 reset value), 1 safe (RD020 added register).

Regenerate with `python scripts/make_demo.py` - `tests/test_demo.py`
fails CI if these files drift from the generator.
"""


def main() -> None:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent.parent / "demo"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "chip_v1.svd").write_text(V1, newline="\n")
    (out_dir / "chip_v2.svd").write_text(V2, newline="\n")
    (out_dir / "README.md").write_text(DEMO_README, newline="\n")


if __name__ == "__main__":
    main()
