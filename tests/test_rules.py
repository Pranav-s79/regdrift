"""Classifier: every Change kind/attribute maps to the documented rule."""

import pytest

from regdrift.diff import Change
from regdrift.rules import classify_changes


def _one(change: Change, allow: list[str] | None = None) -> tuple[str, str]:
    findings = classify_changes([change], allow=allow)
    assert len(findings) == 1
    return findings[0].rule_id, findings[0].severity


@pytest.mark.parametrize(
    ("change", "rule_id", "severity"),
    [
        # moves
        (
            Change("moved", "register", "P.R", "address_offset", 0, 4),
            "RD001",
            "BREAKING",
        ),
        (
            Change("moved", "cluster", "P.C", "address_offset", 0, 4),
            "RD001",
            "BREAKING",
        ),
        (
            Change("moved", "peripheral", "P", "base_address", 0x40000000, 0x50000000),
            "RD006",
            "BREAKING",
        ),
        # removals
        (Change("removed", "register", "P.R"), "RD002", "BREAKING"),
        (Change("removed", "cluster", "P.C"), "RD002", "BREAKING"),
        (Change("removed", "peripheral", "P"), "RD007", "BREAKING"),
        (Change("removed", "field", "P.R.F"), "RD008", "BREAKING"),
        (Change("removed", "enum", "P.R.F.E"), "RD013", "BREAKING"),
        # bit layout (reported as one [msb:lsb] range change)
        (
            Change("modified", "field", "P.R.F", "bit_range", "[3:2]", "[5:4]"),
            "RD003",
            "BREAKING",
        ),
        # access capability
        (
            Change("modified", "register", "P.R", "access", "read-write", "read-only"),
            "RD004",
            "BREAKING",
        ),
        (
            Change("modified", "field", "P.R.F", "access", "read-write", "write-only"),
            "RD004",
            "BREAKING",
        ),
        (
            Change("modified", "register", "P.R", "access", "read-only", "write-only"),
            "RD004",
            "BREAKING",
        ),
        (
            Change("modified", "register", "P.R", "access", "read-only", "read-write"),
            "RD021",
            "SAFE",
        ),
        (
            Change("modified", "register", "P.R", "access", "write-only", "read-write"),
            "RD021",
            "SAFE",
        ),
        # renames
        (
            Change("renamed", "register", "P.R2", "name", "R", "R2", confidence=1.0),
            "RD005",
            "BREAKING",
        ),
        (
            Change("renamed", "field", "P.R.F2", "name", "F", "F2", confidence=0.8),
            "RD005",
            "BREAKING",
        ),
        # register attribute changes
        (Change("modified", "register", "P.R", "size", 32, 16), "RD009", "BREAKING"),
        (Change("modified", "register", "P.R", "reset_value", 0, 1), "RD010", "WARNING"),
        (Change("modified", "register", "P.R", "reset_mask", 0xFF, 0), "RD012", "WARNING"),
        (Change("modified", "register", "P.R", "protection", None, "s"), "RD014", "WARNING"),
        # enums
        (Change("modified", "enum", "P.R.F.E", "value", 0, 1), "RD011", "BREAKING"),
        (Change("modified", "enum", "P.R.F.E", "is_default", False, True), "RD022", "WARNING"),
        # additions
        (Change("added", "register", "P.R"), "RD020", "SAFE"),
        (Change("added", "field", "P.R.F"), "RD020", "SAFE"),
        (Change("added", "peripheral", "P2"), "RD020", "SAFE"),
        (Change("added", "enum", "P.R.F.E"), "RD020", "SAFE"),
        # descriptions
        (Change("modified", "register", "P.R", "description", "a", "b"), "RD030", "SAFE"),
        (Change("modified", "enum", "P.R.F.E", "description", "a", "b"), "RD030", "SAFE"),
    ],
)
def test_rule_mapping(change: Change, rule_id: str, severity: str) -> None:
    assert _one(change) == (rule_id, severity)


def test_allow_by_rule_and_path() -> None:
    change = Change("moved", "register", "UART0.CTRL", "address_offset", 0, 4)
    findings = classify_changes([change], allow=["RD001:UART0.CTRL"])
    assert (findings[0].rule_id, findings[0].severity, findings[0].allowed) == (
        "RD001",
        "BREAKING",
        True,
    )


def test_allow_whole_rule() -> None:
    change = Change("moved", "register", "UART0.CTRL", "address_offset", 0, 4)
    findings = classify_changes([change], allow=["RD001"])
    assert (findings[0].rule_id, findings[0].severity, findings[0].allowed) == (
        "RD001",
        "BREAKING",
        True,
    )


def test_allow_wrong_path_does_not_match() -> None:
    change = Change("moved", "register", "UART0.CTRL", "address_offset", 0, 4)
    findings = classify_changes([change], allow=["RD001:SPI0.CTRL"])
    assert (findings[0].rule_id, findings[0].severity, findings[0].allowed) == (
        "RD001",
        "BREAKING",
        False,
    )


def test_allow_wrong_rule_does_not_match() -> None:
    change = Change("moved", "register", "UART0.CTRL", "address_offset", 0, 4)
    assert _one(change, allow=["RD002:UART0.CTRL"]) == ("RD001", "BREAKING")


def test_messages_use_hex_for_addresses() -> None:
    change = Change("moved", "register", "P.R", "address_offset", 16, 32)
    finding = classify_changes([change])[0]
    assert "0x10" in finding.message
    assert "0x20" in finding.message
