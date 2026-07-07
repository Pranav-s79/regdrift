"""Mutation harness: scripted mutations on real vendor SVDs fire exact rules.

Each mutation deep-copies a parsed vendor model, applies one scripted edit,
and asserts that diff + classification produces the expected rule at the
expected path. Runs across three different vendors (Nordic, Raspberry Pi,
NXP) so vendor-specific structure (clusters, dim arrays, enum-heavy files)
flows through the whole pipeline. Together the mutations cover every rule
in RULES.md.
"""

import copy
import re
from collections.abc import Callable, Iterator
from functools import cache
from pathlib import Path

import pytest

from regdrift.diff import diff_devices
from regdrift.model import Cluster, Device, EnumeratedValue, Field, Register
from regdrift.parse import parse_svd
from regdrift.rules import classify_changes

CORPUS = Path(__file__).parent / "corpus"
FILES = ["nrf52.svd", "rp2040.svd", "MK64F12.svd"]

pytestmark = pytest.mark.skipif(
    not (CORPUS / FILES[0]).exists(), reason="corpus not fetched; run scripts/fetch_corpus.py"
)


@cache
def _parse(name: str) -> Device:
    return parse_svd(CORPUS / name)


# --- model walkers -----------------------------------------------------------


def _registers(dev: Device) -> Iterator[tuple[str, list[Register | Cluster], int, Register]]:
    """Yield (path, parent_list, index, register) for every register."""

    def walk(
        children: list[Register | Cluster], prefix: str
    ) -> Iterator[tuple[str, list[Register | Cluster], int, Register]]:
        for i, child in enumerate(children):
            path = f"{prefix}.{child.name}"
            if isinstance(child, Register):
                yield path, children, i, child
            else:
                yield from walk(child.children, path)

    for p in dev.peripherals:
        yield from walk(p.children, p.name)


def _first_reg_with_unique_fields(dev: Device) -> tuple[str, Register]:
    for path, _parent, _i, reg in _registers(dev):
        names = [f.name for f in reg.fields]
        if names and len(names) == len(set(names)):
            return path, reg
    raise AssertionError("no register with uniquely-named fields found")


def _first_reg_with_access(dev: Device, access: str) -> tuple[str, Register]:
    for path, _parent, _i, reg in _registers(dev):
        if reg.access == access:
            return path, reg
    raise AssertionError(f"no {access} register found")


def _first_unique_enum(dev: Device) -> tuple[str, Field, EnumeratedValue]:
    """A field whose enum names are unique, with an integer-valued entry."""
    for path, _parent, _i, reg in _registers(dev):
        for field in reg.fields:
            names = [e.name for e in field.enumerated_values]
            if not names or len(names) != len(set(names)):
                continue
            for enum in field.enumerated_values:
                if enum.value is not None:
                    return f"{path}.{field.name}", field, enum
    raise AssertionError("no field with unique integer enums found")


# --- mutations ----------------------------------------------------------------
# Each takes a mutable Device copy and returns (expected_rule_id, expected_path).

Mutation = Callable[[Device], tuple[str, str]]


def move_register(dev: Device) -> tuple[str, str]:
    path, reg = _first_reg_with_unique_fields(dev)
    reg.address_offset += 0x400
    return "RD001", path


def remove_register(dev: Device) -> tuple[str, str]:
    path, parent, i, _reg = next(_registers(dev))
    del parent[i]
    return "RD002", path


def shift_field(dev: Device) -> tuple[str, str]:
    path, reg = _first_reg_with_unique_fields(dev)
    field = reg.fields[0]
    field.bit_offset += 1
    return "RD003", f"{path}.{field.name}"


def widen_field(dev: Device) -> tuple[str, str]:
    path, reg = _first_reg_with_unique_fields(dev)
    field = reg.fields[0]
    field.bit_width += 1
    return "RD003", f"{path}.{field.name}"


def drop_write_access(dev: Device) -> tuple[str, str]:
    path, reg = _first_reg_with_access(dev, "read-write")
    reg.access = "read-only"
    return "RD004", path


def rename_register(dev: Device) -> tuple[str, str]:
    path, reg = _first_reg_with_unique_fields(dev)
    parent_path = path.rsplit(".", 1)[0]
    reg.name = "REGDRIFT_RENAMED"
    return "RD005", f"{parent_path}.REGDRIFT_RENAMED"


def move_peripheral(dev: Device) -> tuple[str, str]:
    p = dev.peripherals[0]
    p.base_address += 0x10000
    return "RD006", p.name


def remove_peripheral(dev: Device) -> tuple[str, str]:
    p = dev.peripherals.pop(0)
    return "RD007", p.name


def remove_field(dev: Device) -> tuple[str, str]:
    path, reg = _first_reg_with_unique_fields(dev)
    field = reg.fields.pop(0)
    return "RD008", f"{path}.{field.name}"


def change_register_size(dev: Device) -> tuple[str, str]:
    path, _parent, _i, reg = next(_registers(dev))
    reg.size = 16 if reg.size != 16 else 8
    return "RD009", path


def change_reset_value(dev: Device) -> tuple[str, str]:
    path, _parent, _i, reg = next(_registers(dev))
    reg.reset_value = (reg.reset_value or 0) ^ 0x1
    return "RD010", path


def change_enum_value(dev: Device) -> tuple[str, str]:
    field_path, _field, enum = _first_unique_enum(dev)
    assert enum.value is not None
    enum.value += 1
    return "RD011", f"{field_path}.{enum.name}"


def change_reset_mask(dev: Device) -> tuple[str, str]:
    path, _parent, _i, reg = next(_registers(dev))
    reg.reset_mask = (reg.reset_mask or 0) ^ 0xFF
    return "RD012", path


def remove_enum_value(dev: Device) -> tuple[str, str]:
    field_path, field, enum = _first_unique_enum(dev)
    field.enumerated_values.remove(enum)
    return "RD013", f"{field_path}.{enum.name}"


def set_protection(dev: Device) -> tuple[str, str]:
    path, _parent, _i, reg = next(_registers(dev))
    reg.protection = "s" if reg.protection != "s" else "n"
    return "RD014", path


def flip_write_semantics(dev: Device) -> tuple[str, str]:
    path, reg = _first_reg_with_unique_fields(dev)
    field = reg.fields[0]
    field.modified_write_values = (
        "oneToClear" if field.modified_write_values != "oneToClear" else "oneToSet"
    )
    return "RD017", f"{path}.{field.name}"


def add_read_side_effect(dev: Device) -> tuple[str, str]:
    path, reg = _first_reg_with_unique_fields(dev)
    field = reg.fields[0]
    field.read_action = "clear" if field.read_action != "clear" else "set"
    return "RD018", f"{path}.{field.name}"


def renumber_interrupt(dev: Device) -> tuple[str, str]:
    p = next(p for p in dev.peripherals if p.interrupts)
    irq = p.interrupts[0]
    irq.value += 100
    return "RD015", f"{p.name}.{irq.name}"


def remove_interrupt(dev: Device) -> tuple[str, str]:
    p = next(p for p in dev.peripherals if p.interrupts)
    irq = p.interrupts.pop(0)
    return "RD016", f"{p.name}.{irq.name}"


def add_register(dev: Device) -> tuple[str, str]:
    p = dev.peripherals[0]
    p.children.append(Register(name="REGDRIFT_NEW", address_offset=0xFFC, size=32))
    return "RD020", f"{p.name}.REGDRIFT_NEW"


def grant_write_access(dev: Device) -> tuple[str, str]:
    path, reg = _first_reg_with_access(dev, "read-only")
    reg.access = "read-write"
    return "RD021", path


def change_description(dev: Device) -> tuple[str, str]:
    path, _parent, _i, reg = next(_registers(dev))
    reg.description = (reg.description or "") + " (clarified)"
    return "RD030", path


MUTATIONS: dict[str, Mutation] = {
    "move_register": move_register,
    "remove_register": remove_register,
    "shift_field": shift_field,
    "widen_field": widen_field,
    "drop_write_access": drop_write_access,
    "rename_register": rename_register,
    "move_peripheral": move_peripheral,
    "remove_peripheral": remove_peripheral,
    "remove_field": remove_field,
    "change_register_size": change_register_size,
    "change_reset_value": change_reset_value,
    "change_enum_value": change_enum_value,
    "change_reset_mask": change_reset_mask,
    "remove_enum_value": remove_enum_value,
    "set_protection": set_protection,
    "flip_write_semantics": flip_write_semantics,
    "add_read_side_effect": add_read_side_effect,
    "renumber_interrupt": renumber_interrupt,
    "remove_interrupt": remove_interrupt,
    "add_register": add_register,
    "grant_write_access": grant_write_access,
    "change_description": change_description,
}


@pytest.mark.parametrize("mutation_name", sorted(MUTATIONS))
@pytest.mark.parametrize("svd_name", FILES)
def test_mutation_fires_exact_rule(svd_name: str, mutation_name: str) -> None:
    original = _parse(svd_name)
    mutated = copy.deepcopy(original)
    rule_id, path = MUTATIONS[mutation_name](mutated)
    findings = classify_changes(diff_devices(original, mutated))
    hits = [(f.rule_id, f.path) for f in findings]
    assert (rule_id, path) in hits, (
        f"{mutation_name} on {svd_name}: expected {rule_id} at {path}, got {hits[:10]}"
    )


def test_every_rule_has_mutation_coverage() -> None:
    """Coverage gate: every rule ID published in RULES.md fires in this harness."""
    rulebook = set(re.findall(r"RD\d{3}", (Path(__file__).parent.parent / "RULES.md").read_text()))
    assert rulebook, "RULES.md defines no rule IDs?"
    device = _parse(FILES[0])
    covered = set()
    for mutate in MUTATIONS.values():
        mutated = copy.deepcopy(device)
        rule_id, _path = mutate(mutated)
        covered.add(rule_id)
    missing = rulebook - covered
    assert not missing, f"rules without mutation coverage: {sorted(missing)}"
