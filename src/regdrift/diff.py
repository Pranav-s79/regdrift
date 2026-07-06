"""Structural diff of two canonical Device models.

Matching runs level by level (peripherals, then registers/clusters, then
fields, then enumerated values) in three phases:

1. **exact name match** — same-named elements are paired and compared
   attribute by attribute; an address change on a name-matched element is a
   ``moved`` change.
2. **moved detection** — falls out of phase 1: a name present in both models
   at different offsets is reported as ``moved``, not removed+added.
3. **rename heuristic** — leftover old/new elements with identical offset and
   identical child structure are paired as ``renamed`` (with a confidence:
   1.0 when descriptions also match, else 0.8). Ambiguous candidates (several
   elements sharing one offset+structure) are left unpaired rather than
   guessed.

Everything else is ``removed`` (only in old) or ``added`` (only in new).
No severities here — that's the rulebook's job (sprint 3).
"""

from collections.abc import Sequence
from dataclasses import dataclass

from regdrift.model import (
    Cluster,
    Device,
    EnumeratedValue,
    Field,
    Peripheral,
    Register,
)

Value = str | int | float | bool | None


@dataclass
class Change:
    kind: str  # added | removed | moved | renamed | modified
    element: str  # peripheral | cluster | register | field | enum
    path: str  # dotted, e.g. UART.CTRL.EN (new name for renames)
    attribute: str | None = None  # which attribute changed, for moved/modified
    before: Value = None
    after: Value = None
    confidence: float | None = None  # rename heuristic confidence


_Item = Peripheral | Register | Cluster | Field


def diff_devices(old: Device, new: Device) -> list[Change]:
    """Compare two canonical devices, returning a flat, ordered change list."""
    changes: list[Change] = []
    _diff_level(
        old.peripherals,
        new.peripherals,
        parent_path="",
        changes=changes,
    )
    return changes


# ---------------------------------------------------------------------------
# Generic three-phase matcher
# ---------------------------------------------------------------------------


def _element_of(item: _Item) -> str:
    if isinstance(item, Peripheral):
        return "peripheral"
    if isinstance(item, Field):
        return "field"
    return item.kind  # "register" | "cluster"


def _offset_of(item: _Item) -> int:
    if isinstance(item, Peripheral):
        return item.base_address
    if isinstance(item, Field):
        return item.bit_offset
    return item.address_offset


def _signature(item: _Item) -> tuple[object, ...]:
    """Structure fingerprint used by the rename heuristic (names included)."""
    if isinstance(item, Register):
        fields = tuple((f.name, f.bit_offset, f.bit_width) for f in item.fields)
        return ("register", item.size, fields)
    if isinstance(item, Field):
        return ("field", item.bit_width, tuple(e.name for e in item.enumerated_values))
    # peripheral / cluster: recursive over children
    kind = "peripheral" if isinstance(item, Peripheral) else "cluster"
    return (kind, tuple((c.name, _offset_of(c), _signature(c)) for c in item.children))


def _diff_level(
    old_items: Sequence[_Item],
    new_items: Sequence[_Item],
    parent_path: str,
    changes: list[Change],
) -> None:
    old_by_name: dict[tuple[str, str], _Item] = {}
    for item in old_items:
        old_by_name.setdefault((_element_of(item), item.name), item)
    new_by_name: dict[tuple[str, str], _Item] = {}
    for item in new_items:
        new_by_name.setdefault((_element_of(item), item.name), item)

    unmatched_old: list[_Item] = []
    # Phase 1+2: exact name pairing (address diffs become "moved" in compare).
    for item in old_items:
        partner = new_by_name.get((_element_of(item), item.name))
        if partner is not None:
            _compare(item, partner, parent_path, changes)
        else:
            unmatched_old.append(item)
    unmatched_new: list[_Item] = [
        item for item in new_items if (_element_of(item), item.name) not in old_by_name
    ]

    # Phase 3: rename heuristic on the leftovers — identical offset and
    # structure, and unambiguous (exactly one candidate on each side).
    def keyed(items: list[_Item]) -> dict[tuple[object, ...], list[_Item]]:
        table: dict[tuple[object, ...], list[_Item]] = {}
        for item in items:
            key = (_element_of(item), _offset_of(item), _signature(item))
            table.setdefault(key, []).append(item)
        return table

    old_keyed = keyed(unmatched_old)
    new_keyed = keyed(unmatched_new)
    renamed_old: set[int] = set()
    renamed_new: set[int] = set()
    for key, old_group in old_keyed.items():
        new_group = new_keyed.get(key, [])
        if len(old_group) == 1 and len(new_group) == 1:
            o, n = old_group[0], new_group[0]
            confidence = 1.0 if o.description == n.description else 0.8
            path = _join(parent_path, n.name)
            changes.append(
                Change(
                    kind="renamed",
                    element=_element_of(n),
                    path=path,
                    attribute="name",
                    before=o.name,
                    after=n.name,
                    confidence=confidence,
                )
            )
            _compare(o, n, parent_path, changes)
            renamed_old.add(id(o))
            renamed_new.add(id(n))

    for item in unmatched_old:
        if id(item) not in renamed_old:
            changes.append(
                Change(
                    kind="removed", element=_element_of(item), path=_join(parent_path, item.name)
                )
            )
    for item in unmatched_new:
        if id(item) not in renamed_new:
            changes.append(
                Change(kind="added", element=_element_of(item), path=_join(parent_path, item.name))
            )


def _join(parent: str, name: str) -> str:
    return f"{parent}.{name}" if parent else name


# ---------------------------------------------------------------------------
# Pairwise comparison per element type
# ---------------------------------------------------------------------------


def _compare(old: _Item, new: _Item, parent_path: str, changes: list[Change]) -> None:
    path = _join(parent_path, new.name)
    element = _element_of(new)

    def modified(attribute: str, before: Value, after: Value, kind: str = "modified") -> None:
        changes.append(
            Change(
                kind=kind,
                element=element,
                path=path,
                attribute=attribute,
                before=before,
                after=after,
            )
        )

    if isinstance(old, Peripheral) and isinstance(new, Peripheral):
        if old.base_address != new.base_address:
            modified("base_address", old.base_address, new.base_address, kind="moved")
        if old.description != new.description:
            modified("description", old.description, new.description)
        _diff_level(old.children, new.children, path, changes)
        return

    if isinstance(old, Cluster) and isinstance(new, Cluster):
        if old.address_offset != new.address_offset:
            modified("address_offset", old.address_offset, new.address_offset, kind="moved")
        if old.description != new.description:
            modified("description", old.description, new.description)
        _diff_level(old.children, new.children, path, changes)
        return

    if isinstance(old, Register) and isinstance(new, Register):
        if old.address_offset != new.address_offset:
            modified("address_offset", old.address_offset, new.address_offset, kind="moved")
        for attr in ("size", "access", "reset_value", "reset_mask", "protection", "description"):
            if getattr(old, attr) != getattr(new, attr):
                modified(attr, getattr(old, attr), getattr(new, attr))
        _diff_level(old.fields, new.fields, path, changes)
        return

    if isinstance(old, Field) and isinstance(new, Field):
        for attr in ("bit_offset", "bit_width", "access", "description"):
            if getattr(old, attr) != getattr(new, attr):
                modified(attr, getattr(old, attr), getattr(new, attr))
        _diff_enums(old.enumerated_values, new.enumerated_values, path, changes)
        return

    raise TypeError(f"cannot compare {type(old).__name__} with {type(new).__name__}")


def _diff_enums(
    old_enums: list[EnumeratedValue],
    new_enums: list[EnumeratedValue],
    parent_path: str,
    changes: list[Change],
) -> None:
    old_by_name = {e.name: e for e in old_enums}
    new_by_name = {e.name: e for e in new_enums}
    for name, old_e in old_by_name.items():
        path = _join(parent_path, name)
        new_e = new_by_name.get(name)
        if new_e is None:
            changes.append(Change(kind="removed", element="enum", path=path))
            continue
        old_value = old_e.value if old_e.value is not None else old_e.raw_value
        new_value = new_e.value if new_e.value is not None else new_e.raw_value
        for attribute, before, after in (
            ("value", old_value, new_value),
            ("description", old_e.description, new_e.description),
            ("is_default", old_e.is_default, new_e.is_default),
            ("usage", old_e.usage, new_e.usage),
        ):
            if before != after:
                changes.append(
                    Change(
                        kind="modified",
                        element="enum",
                        path=path,
                        attribute=attribute,
                        before=before,
                        after=after,
                    )
                )
    for name in new_by_name:
        if name not in old_by_name:
            changes.append(Change(kind="added", element="enum", path=_join(parent_path, name)))
