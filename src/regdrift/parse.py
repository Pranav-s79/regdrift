"""CMSIS-SVD parser producing the canonical resolved model.

Three stages:

1. **Raw parse** — the XML is lowered to ``_Node`` records (tag, simple
   text props, child nodes), each carrying an XPath-ish ``path`` that every
   error message reports.
2. **derivedFrom resolution** — resolution runs over the complete raw tree,
   so forward references (base defined later in the file) work by
   construction. A derived node first ensures its base is resolved (bases may
   themselves be derived), then inherits every prop it doesn't define itself;
   if the derived node defines any child elements, they replace the base's
   children wholesale.
3. **Canonical build** — applies the register-properties inheritance cascade
   (size/access/resetValue/resetMask/protection: device -> peripheral ->
   cluster -> register, with access continuing into fields) and expands
   dim/dimIncrement/dimIndex arrays, emitting :mod:`regdrift.model`
   dataclasses.

Per the CMSIS-SVD spec, unset device-level register properties default to
size=32, access=read-write, resetValue=0, resetMask=0xFFFFFFFF.
"""

from dataclasses import dataclass
from dataclasses import field as dc_field
from pathlib import Path
from xml.etree import ElementTree as ET

from regdrift.model import (
    Cluster,
    Device,
    DimInfo,
    EnumeratedValue,
    Field,
    Peripheral,
    Register,
)


class SvdParseError(Exception):
    """A parse or resolution failure, carrying an XPath-ish location."""

    def __init__(self, message: str, location: str) -> None:
        super().__init__(f"{location}: {message}")
        self.message = message
        self.location = location


# ---------------------------------------------------------------------------
# Stage 1: raw parse
# ---------------------------------------------------------------------------


@dataclass
class _Node:
    tag: str
    path: str
    props: dict[str, str] = dc_field(default_factory=dict)
    derived_from: str | None = None
    children: list["_Node"] = dc_field(default_factory=list, repr=False)
    parent: "_Node | None" = dc_field(default=None, repr=False, compare=False)


# Which child *element* tags each node kind owns (everything else with no
# sub-elements is treated as a simple text prop; unknown complex elements
# like <interrupt> or <addressBlock> are ignored).
_CHILD_TAGS: dict[str, frozenset[str]] = {
    "device": frozenset({"peripheral"}),
    "peripheral": frozenset({"register", "cluster"}),
    "cluster": frozenset({"register", "cluster"}),
    "register": frozenset({"field"}),
    "field": frozenset({"enumeratedValues"}),
    "enumeratedValues": frozenset({"enumeratedValue"}),
    "enumeratedValue": frozenset(),
}

# Transparent grouping wrappers, per parent tag.
_WRAPPERS: dict[str, frozenset[str]] = {
    "device": frozenset({"peripherals"}),
    "peripheral": frozenset({"registers"}),
    "register": frozenset({"fields"}),
}

# Field bit-range styles are mutually exclusive during derivedFrom merging.
_BIT_RANGE_KEYS = frozenset({"bitOffset", "bitWidth", "lsb", "msb", "bitRange"})


def _local(tag: str) -> str:
    """Strip any XML namespace prefix."""
    return tag.rpartition("}")[2]


def _raw_node(el: ET.Element, tag: str, parent_path: str, index: int) -> _Node:
    name_el = el.find("name")
    name = (name_el.text or "").strip() if name_el is not None else ""
    label = f"{tag}[@name='{name}']" if name else f"{tag}[{index}]"
    node = _Node(tag=tag, path=f"{parent_path}/{label}", derived_from=el.get("derivedFrom"))

    child_tags = _CHILD_TAGS[tag]
    wrappers = _WRAPPERS.get(tag, frozenset())
    count = 0

    def consume(container: ET.Element, container_path: str) -> None:
        nonlocal count
        for child in container:
            ctag = _local(child.tag)
            if ctag in child_tags:
                count += 1
                node.children.append(_raw_node(child, ctag, container_path, count))
            elif ctag in wrappers:
                consume(child, f"{container_path}/{ctag}")
            elif len(child) == 0:
                node.props[ctag] = (child.text or "").strip()
            # complex elements we don't model (interrupt, addressBlock, cpu,
            # writeConstraint, dimArrayIndex, ...) are skipped

    consume(el, node.path)
    return node


def _set_parents(node: _Node) -> None:
    for child in node.children:
        child.parent = node
        _set_parents(child)


# ---------------------------------------------------------------------------
# Stage 2: derivedFrom resolution
# ---------------------------------------------------------------------------


class _Resolver:
    def __init__(self, device: _Node) -> None:
        self._device = device
        self._resolving: set[int] = set()
        self._resolved: set[int] = set()

    def resolve_tree(self) -> None:
        for peripheral in self._device.children:
            self._ensure_resolved(peripheral)

    def _ensure_resolved(self, node: _Node) -> None:
        if id(node) in self._resolved:
            return
        if id(node) in self._resolving:
            raise SvdParseError(
                f"derivedFrom cycle involving '{node.props.get('name', '?')}'", node.path
            )
        self._resolving.add(id(node))
        try:
            if node.derived_from is not None:
                base = self._lookup(node.derived_from, node)
                self._ensure_resolved(base)
                if not node.children and base.children:
                    node.children = [
                        self._clone(c, node, base.path, node.path) for c in base.children
                    ]
                # The bit-range props form one exclusive group: a derived
                # field that defines its own range (in any of the three
                # styles) must not inherit pieces of the base's style, or
                # e.g. a base bitOffset would shadow a derived bitRange.
                skip: frozenset[str] = frozenset()
                if node.tag == "field" and _BIT_RANGE_KEYS & node.props.keys():
                    skip = _BIT_RANGE_KEYS
                for key, value in base.props.items():
                    if key not in skip:
                        node.props.setdefault(key, value)
                node.derived_from = None
            for child in node.children:
                self._ensure_resolved(child)
        finally:
            self._resolving.discard(id(node))
        self._resolved.add(id(node))

    def _clone(self, node: _Node, parent: _Node, old_prefix: str, new_prefix: str) -> _Node:
        new = _Node(
            tag=node.tag,
            path=node.path.replace(old_prefix, new_prefix, 1),
            props=dict(node.props),
            derived_from=node.derived_from,
            parent=parent,
        )
        new.children = [self._clone(c, new, old_prefix, new_prefix) for c in node.children]
        return new

    def _lookup(self, ref: str, node: _Node) -> _Node:
        if "." in ref:
            found = self._lookup_dotted(ref.split("."), node)
        else:
            found = self._lookup_scoped(ref, node)
        if found is None:
            raise SvdParseError(f"derivedFrom target '{ref}' not found", node.path)
        return found

    def _lookup_dotted(self, parts: list[str], node: _Node) -> _Node | None:
        # Try absolute (from the device root) first, then relative to each
        # enclosing scope from the innermost outward.
        starts: list[_Node] = [self._device]
        scope = node.parent
        while scope is not None:
            starts.insert(1, scope)  # keep device first, then innermost-out
            scope = scope.parent
        for start in starts:
            cur: _Node | None = start
            for part in parts:
                assert cur is not None
                cur = next((c for c in cur.children if c.props.get("name") == part), None)
                if cur is None:
                    break
            if cur is not None and cur is not node and cur.tag == node.tag:
                return cur
        return None

    def _lookup_scoped(self, ref: str, node: _Node) -> _Node | None:
        scope = node.parent
        while scope is not None:
            # unqualified refs never cross peripheral boundaries (the spec
            # reserves that for dotted names) — only peripherals themselves
            # resolve at device scope
            if scope.tag == "device" and node.tag != "peripheral":
                return None
            found = self._find_named(scope, node.tag, ref, node)
            if found is not None:
                return found
            scope = scope.parent
        return None

    def _find_named(self, scope: _Node, tag: str, ref: str, skip: _Node) -> _Node | None:
        # same-scope siblings win over matches buried in nested clusters
        for child in scope.children:
            if child is not skip and child.tag == tag and child.props.get("name") == ref:
                return child
        for child in scope.children:
            found = self._find_named(child, tag, ref, skip)
            if found is not None:
                return found
        return None


# ---------------------------------------------------------------------------
# Stage 3: canonical build (property cascade + dim expansion)
# ---------------------------------------------------------------------------


@dataclass
class _RegProps:
    """Register properties flowing down the inheritance cascade."""

    size: int
    access: str
    reset_value: int
    reset_mask: int
    protection: str | None


def _to_int(text: str, what: str, path: str) -> int:
    s = text.strip()
    try:
        if s[:2] in ("0x", "0X"):
            return int(s[2:], 16)
        if s[:2] in ("0b", "0B"):
            return int(s[2:], 2)
        if s[:1] == "#":
            return int(s[1:], 2)
        return int(s, 10)
    except (ValueError, IndexError):
        raise SvdParseError(f"invalid integer {text!r} for <{what}>", path) from None


def _req(props: dict[str, str], key: str, path: str) -> str:
    value = props.get(key, "")
    if not value:
        raise SvdParseError(f"missing required <{key}>", path)
    return value


def _overlay(inherited: _RegProps, props: dict[str, str], path: str) -> _RegProps:
    return _RegProps(
        size=_to_int(props["size"], "size", path) if "size" in props else inherited.size,
        access=props.get("access", inherited.access),
        reset_value=(
            _to_int(props["resetValue"], "resetValue", path)
            if "resetValue" in props
            else inherited.reset_value
        ),
        reset_mask=(
            _to_int(props["resetMask"], "resetMask", path)
            if "resetMask" in props
            else inherited.reset_mask
        ),
        protection=props.get("protection", inherited.protection),
    )


def _dim_indices(raw: str | None, dim: int, path: str) -> list[str]:
    if raw is None:
        return [str(i) for i in range(dim)]
    s = raw.strip()
    if "," in s:
        parts = [p.strip() for p in s.split(",")]
    elif "-" in s:
        lo, _, hi = s.partition("-")
        lo, hi = lo.strip(), hi.strip()
        if lo.isdigit() and hi.isdigit():
            parts = [str(i) for i in range(int(lo), int(hi) + 1)]
        elif len(lo) == 1 and len(hi) == 1 and lo.isalpha() and hi.isalpha():
            parts = [chr(c) for c in range(ord(lo), ord(hi) + 1)]
        else:
            raise SvdParseError(f"unsupported dimIndex {raw!r}", path)
    else:
        parts = [s]
    if len(parts) != dim:
        raise SvdParseError(f"dimIndex {raw!r} has {len(parts)} entries, expected dim={dim}", path)
    return parts


def _expand(node: _Node) -> list[tuple[str, int, DimInfo | None]]:
    """Yield (name, offset_delta, dim_info) for each expanded array instance.

    Elements without <dim> yield themselves once, unchanged.
    """
    props = node.props
    name = _req(props, "name", node.path)
    if "dim" not in props:
        return [(name, 0, None)]
    dim = _to_int(props["dim"], "dim", node.path)
    increment = _to_int(_req(props, "dimIncrement", node.path), "dimIncrement", node.path)
    indices = _dim_indices(props.get("dimIndex"), dim, node.path)
    template = name.replace("[%s]", "%s")
    out: list[tuple[str, int, DimInfo | None]] = []
    for i, index in enumerate(indices):
        expanded = template.replace("%s", index) if "%s" in template else f"{template}{index}"
        out.append((expanded, i * increment, DimInfo(count=dim, increment=increment, index=index)))
    return out


def _build_enums(field_node: _Node) -> list[EnumeratedValue]:
    enums: list[EnumeratedValue] = []
    for container in field_node.children:
        # spec default: an omitted <usage> means read-write; normalize so an
        # explicit-vs-omitted difference never diffs as a change
        usage = container.props.get("usage") or "read-write"
        for entry in container.children:
            props = entry.props
            raw_value = props.get("value") or None
            is_default = props.get("isDefault", "").strip().lower() in ("true", "1")
            value: int | None = None
            if raw_value is not None:
                value = _enum_int(raw_value)
            enums.append(
                EnumeratedValue(
                    name=_req(props, "name", entry.path),
                    value=value,
                    raw_value=raw_value,
                    description=props.get("description") or None,
                    is_default=is_default,
                    usage=usage,
                )
            )
    return enums


def _enum_int(raw: str) -> int | None:
    """Parse an enumeratedValue <value>; None for values with 'x' don't-cares."""
    s = raw.strip()
    bits: str | None = None
    if s[:2] in ("0b", "0B"):
        bits = s[2:]
    elif s[:1] == "#":
        bits = s[1:]
    try:
        if bits is not None:
            if "x" in bits.lower():
                return None
            return int(bits, 2)
        if s[:2] in ("0x", "0X"):
            return int(s[2:], 16)
        return int(s, 10)
    except ValueError:
        return None


def _bit_range(props: dict[str, str], path: str) -> tuple[int, int]:
    if "bitOffset" in props:
        offset = _to_int(props["bitOffset"], "bitOffset", path)
        width = _to_int(props["bitWidth"], "bitWidth", path) if "bitWidth" in props else 1
    elif "lsb" in props and "msb" in props:
        lsb = _to_int(props["lsb"], "lsb", path)
        msb = _to_int(props["msb"], "msb", path)
        offset, width = lsb, msb - lsb + 1
    elif "bitRange" in props:
        s = props["bitRange"].strip()
        if not (s.startswith("[") and s.endswith("]") and ":" in s):
            raise SvdParseError(f"malformed bitRange {props['bitRange']!r}", path)
        msb_s, _, lsb_s = s[1:-1].partition(":")
        msb = _to_int(msb_s, "bitRange msb", path)
        lsb = _to_int(lsb_s, "bitRange lsb", path)
        offset, width = lsb, msb - lsb + 1
    else:
        raise SvdParseError("field has no bit range (bitOffset/lsb+msb/bitRange)", path)
    if width < 1:
        raise SvdParseError(f"field has non-positive bit width {width}", path)
    return offset, width


def _build_fields(reg_node: _Node, reg_access: str) -> list[Field]:
    fields: list[Field] = []
    for fnode in reg_node.children:
        props = fnode.props
        bit_offset, bit_width = _bit_range(props, fnode.path)
        access = props.get("access", reg_access)
        for name, delta, dim_info in _expand(fnode):
            fields.append(
                Field(
                    name=name,
                    bit_offset=bit_offset + delta,
                    bit_width=bit_width,
                    access=access,
                    description=props.get("description") or None,
                    enumerated_values=_build_enums(fnode),
                    dim=dim_info,
                )
            )
    return fields


def _build_registers(node: _Node, inherited: _RegProps) -> list[Register]:
    props = node.props
    own = _overlay(inherited, props, node.path)
    offset = _to_int(_req(props, "addressOffset", node.path), "addressOffset", node.path)
    registers: list[Register] = []
    for name, delta, dim_info in _expand(node):
        registers.append(
            Register(
                name=name,
                address_offset=offset + delta,
                size=own.size,
                access=own.access,
                reset_value=own.reset_value,
                reset_mask=own.reset_mask,
                protection=own.protection,
                description=props.get("description") or None,
                fields=_build_fields(node, own.access),
                dim=dim_info,
            )
        )
    return registers


def _build_clusters(node: _Node, inherited: _RegProps) -> list[Cluster]:
    props = node.props
    own = _overlay(inherited, props, node.path)
    offset = _to_int(_req(props, "addressOffset", node.path), "addressOffset", node.path)
    clusters: list[Cluster] = []
    for name, delta, dim_info in _expand(node):
        clusters.append(
            Cluster(
                name=name,
                address_offset=offset + delta,
                description=props.get("description") or None,
                children=_build_children(node, own),
                dim=dim_info,
            )
        )
    return clusters


def _build_children(node: _Node, inherited: _RegProps) -> list[Register | Cluster]:
    children: list[Register | Cluster] = []
    for child in node.children:
        if child.tag == "register":
            children.extend(_build_registers(child, inherited))
        else:
            children.extend(_build_clusters(child, inherited))
    return children


def _build_peripherals(node: _Node, inherited: _RegProps) -> list[Peripheral]:
    props = node.props
    own = _overlay(inherited, props, node.path)
    base_address = _to_int(_req(props, "baseAddress", node.path), "baseAddress", node.path)
    peripherals: list[Peripheral] = []
    for name, delta, dim_info in _expand(node):
        peripherals.append(
            Peripheral(
                name=name,
                base_address=base_address + delta,
                description=props.get("description") or None,
                group_name=props.get("groupName") or None,
                children=_build_children(node, own),
                dim=dim_info,
            )
        )
    return peripherals


def _build_device(dev_node: _Node) -> Device:
    props = dev_node.props
    inherited = _RegProps(
        size=_to_int(props.get("size", "32"), "size", dev_node.path),
        access=props.get("access", "read-write"),
        reset_value=_to_int(props.get("resetValue", "0"), "resetValue", dev_node.path),
        reset_mask=_to_int(props.get("resetMask", "0xFFFFFFFF"), "resetMask", dev_node.path),
        protection=props.get("protection"),
    )
    peripherals: list[Peripheral] = []
    for pnode in dev_node.children:
        peripherals.extend(_build_peripherals(pnode, inherited))
    return Device(
        name=_req(props, "name", dev_node.path),
        version=props.get("version") or None,
        description=props.get("description") or None,
        address_unit_bits=(
            _to_int(props["addressUnitBits"], "addressUnitBits", dev_node.path)
            if "addressUnitBits" in props
            else None
        ),
        width=_to_int(props["width"], "width", dev_node.path) if "width" in props else None,
        peripherals=peripherals,
    )


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


def _parse_root(root: ET.Element) -> Device:
    if _local(root.tag) != "device":
        raise SvdParseError(f"root element is <{_local(root.tag)}>, expected <device>", "/")
    dev_node = _Node(tag="device", path="/device")
    count = 0
    for child in root:
        ctag = _local(child.tag)
        if ctag == "peripherals":
            for pel in child:
                if _local(pel.tag) == "peripheral":
                    count += 1
                    dev_node.children.append(
                        _raw_node(pel, "peripheral", "/device/peripherals", count)
                    )
        elif len(child) == 0:
            dev_node.props[ctag] = (child.text or "").strip()
        # cpu, vendorExtensions, ... are skipped
    _set_parents(dev_node)
    _Resolver(dev_node).resolve_tree()
    return _build_device(dev_node)


def parse_svd(path: str | Path) -> Device:
    """Parse an SVD file into the fully resolved canonical model."""
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        raise SvdParseError(f"malformed XML: {exc}", str(path)) from exc
    return _parse_root(tree.getroot())


def parse_svd_string(xml: str) -> Device:
    """Parse SVD XML from a string (mainly for tests)."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise SvdParseError(f"malformed XML: {exc}", "<string>") from exc
    return _parse_root(root)
