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
    # Phase 1+2: exact name pairing (address diffs become "moved" in compare).
    # Names are usually unique per level, but real vendor files repeat names
    # (e.g. several RESERVED fields in one register), so same-named groups are
    # paired by exact offset first, then positionally.
    old_groups: dict[tuple[str, str], list[_Item]] = {}
    for item in old_items:
        old_groups.setdefault((_element_of(item), item.name), []).append(item)
    new_groups: dict[tuple[str, str], list[_Item]] = {}
    for item in new_items:
        new_groups.setdefault((_element_of(item), item.name), []).append(item)

    unmatched_old: list[_Item] = []
    unmatched_new: list[_Item] = []
    for key, old_group in old_groups.items():
        new_group = new_groups.get(key, [])
        pairs = _pair_same_name(old_group, new_group)
        for o, n in pairs:
            _compare(o, n, parent_path, changes)
        paired_old = {id(o) for o, _ in pairs}
        paired_new = {id(n) for _, n in pairs}
        unmatched_old.extend(o for o in old_group if id(o) not in paired_old)
        unmatched_new.extend(n for n in new_group if id(n) not in paired_new)
    for key, new_group in new_groups.items():
        if key not in old_groups:
            unmatched_new.extend(new_group)

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
    for sig_key, old_group in old_keyed.items():
        new_group = new_keyed.get(sig_key, [])
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


def _pair_same_name(
    old_group: list[_Item], new_group: list[_Item]
) -> list[tuple[_Item, _Item]]:
    """Pair same-named items: exact offset match first, then by position."""
    pairs: list[tuple[_Item, _Item]] = []
    new_free = list(new_group)
    old_free: list[_Item] = []
    for o in old_group:
        match = next((n for n in new_free if _offset_of(n) == _offset_of(o)), None)
        if match is not None:
            pairs.append((o, match))
            new_free.remove(match)
        else:
            old_free.append(o)
    pairs.extend(zip(old_free, new_free, strict=False))
    return pairs


def _pair_enum_group(
    old_group: list[EnumeratedValue], new_group: list[EnumeratedValue]
) -> tuple[
    list[tuple[EnumeratedValue, EnumeratedValue]],
    list[EnumeratedValue],
    list[EnumeratedValue],
]:
    """Pair same-keyed enum entries: equal (value, raw) first, then by position.

    Returns (pairs, removed_old_leftovers, added_new_leftovers).
    """
    pairs: list[tuple[EnumeratedValue, EnumeratedValue]] = []
    new_free = list(new_group)
    old_free: list[EnumeratedValue] = []
    for o in old_group:
        match = next(
            (n for n in new_free if n.value == o.value and n.raw_value == o.raw_value), None
        )
        if match is not None:
            pairs.append((o, match))
            new_free.remove(match)
        else:
            old_free.append(o)
    pairs.extend(zip(old_free, new_free, strict=False))
    removed = old_free[len(new_free):]
    added = new_free[len(old_free):]
    return pairs, removed, added


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
    # Keyed by (usage, name) with group-lists, mirroring _diff_level: a field
    # may carry separate read and write containers with same-named entries,
    # and a single container may legally repeat a name — neither may collapse
    # (a last-wins dict silently produced clean diffs on removals). Within a
    # same-key group, pair equal values first, then positionally.
    old_groups: dict[tuple[str | None, str], list[EnumeratedValue]] = {}
    for e in old_enums:
        old_groups.setdefault((e.usage, e.name), []).append(e)
    new_groups: dict[tuple[str | None, str], list[EnumeratedValue]] = {}
    for e in new_enums:
        new_groups.setdefault((e.usage, e.name), []).append(e)

    for key, old_group in old_groups.items():
        path = _join(parent_path, key[1])
        new_group = new_groups.get(key, [])
        pairs, removed, added = _pair_enum_group(old_group, new_group)
        for old_e, new_e in pairs:
            old_value = old_e.value if old_e.value is not None else old_e.raw_value
            new_value = new_e.value if new_e.value is not None else new_e.raw_value
            for attribute, before, after in (
                ("value", old_value, new_value),
                ("description", old_e.description, new_e.description),
                ("is_default", old_e.is_default, new_e.is_default),
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
        changes.extend(Change(kind="removed", element="enum", path=path) for _ in removed)
        changes.extend(Change(kind="added", element="enum", path=path) for _ in added)
    for key, new_group in new_groups.items():
        if key not in old_groups:
            path = _join(parent_path, key[1])
            changes.extend(Change(kind="added", element="enum", path=path) for _ in new_group)
