"""Canonical, fully resolved model of a CMSIS-SVD device.

Instances of these classes are what the parser produces *after* resolving
derivedFrom references, applying the register-properties inheritance cascade
(device -> peripheral -> cluster -> register -> field), and expanding
dim/dimIncrement/dimIndex arrays. Nothing downstream (diff, rules) should
ever need to look at SVD XML semantics again.

Offsets stay relative, as in the SVD source: a register's absolute address is
peripheral.base_address + (enclosing cluster offsets) + register.address_offset.
"""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class DimInfo:
    """Provenance for an element produced by dim array expansion.

    ``index`` is the dimIndex substring substituted into *this* instance's
    name; ``count``/``increment`` describe the array it came from.
    """

    count: int
    increment: int
    index: str


@dataclass
class EnumeratedValue:
    name: str
    value: int | None = None  # None for isDefault entries or wildcard values
    raw_value: str | None = None  # original text, preserves don't-care 'x' bits
    description: str | None = None
    is_default: bool = False
    usage: str | None = None  # read / write / read-write, from the container


@dataclass
class Field:
    name: str
    bit_offset: int
    bit_width: int
    access: str | None = None  # resolved: own value or inherited from register
    description: str | None = None
    modified_write_values: str = "modify"  # spec default; e.g. oneToClear, oneToSet
    read_action: str | None = None  # None = reads have no side effect
    enumerated_values: list[EnumeratedValue] = field(default_factory=list)
    dim: DimInfo | None = None


@dataclass
class Register:
    name: str
    address_offset: int
    size: int
    access: str | None = None
    reset_value: int | None = None
    reset_mask: int | None = None
    protection: str | None = None
    description: str | None = None
    modified_write_values: str = "modify"  # spec default; e.g. oneToClear, oneToSet
    read_action: str | None = None  # None = reads have no side effect
    fields: list[Field] = field(default_factory=list)
    dim: DimInfo | None = None
    kind: str = "register"  # discriminator for Register | Cluster in JSON


@dataclass
class Cluster:
    name: str
    address_offset: int
    description: str | None = None
    children: list["Register | Cluster"] = field(default_factory=list)
    dim: DimInfo | None = None
    kind: str = "cluster"


@dataclass
class Interrupt:
    """An interrupt line a peripheral raises; value is the NVIC/vector number."""

    name: str
    value: int
    description: str | None = None


@dataclass
class Peripheral:
    name: str
    base_address: int
    description: str | None = None
    group_name: str | None = None
    children: list[Register | Cluster] = field(default_factory=list)
    interrupts: list[Interrupt] = field(default_factory=list)
    dim: DimInfo | None = None


@dataclass
class Device:
    name: str
    version: str | None = None
    description: str | None = None
    address_unit_bits: int | None = None
    width: int | None = None
    peripherals: list[Peripheral] = field(default_factory=list)


def device_to_dict(device: Device) -> dict[str, Any]:
    """Serialize a Device to plain dicts/lists (JSON-ready, stable key order)."""
    return asdict(device)
