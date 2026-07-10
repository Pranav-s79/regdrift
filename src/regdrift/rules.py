"""Classify diff Changes into rule findings, per RULES.md.

Every Change maps to exactly one rule (rule IDs and severities are the
published contract — see RULES.md). The allowlist turns matching findings
into severity ALLOWED, which never fails a check.
"""

from dataclasses import dataclass

from regdrift.diff import Change

BREAKING = "BREAKING"
WARNING = "WARNING"
SAFE = "SAFE"
ALLOWED = "ALLOWED"

RULE_IDS = frozenset(
    {
        "RD001",
        "RD002",
        "RD003",
        "RD004",
        "RD005",
        "RD006",
        "RD007",
        "RD008",
        "RD009",
        "RD010",
        "RD011",
        "RD012",
        "RD013",
        "RD014",
        "RD015",
        "RD016",
        "RD017",
        "RD018",
        "RD020",
        "RD021",
        "RD022",
        "RD030",
    }
)

# access string -> capability set (RULES.md "Notes")
_ACCESS_CAPS = {
    "read-only": frozenset({"read"}),
    "write-only": frozenset({"write"}),
    "writeOnce": frozenset({"write"}),
    "read-write": frozenset({"read", "write"}),
    "read-writeOnce": frozenset({"read", "write"}),
}


@dataclass
class Finding:
    rule_id: str
    severity: str  # BREAKING | WARNING | SAFE | ALLOWED
    path: str
    message: str
    change: Change
    allowed: bool = False


def classify_changes(
    changes: list[Change],
    allow: list[str] | None = None,
    severity_overrides: dict[str, str] | None = None,
) -> list[Finding]:
    """Classify every change.

    ``severity_overrides`` re-ranks whole rules (RDxxx -> severity); entries
    matching the allowlist become ALLOWED and win over any override.
    """
    allow_entries = [_parse_allow(entry) for entry in (allow or [])]
    findings = []
    for change in changes:
        finding = _classify(change)
        if severity_overrides and finding.rule_id in severity_overrides:
            finding.severity = severity_overrides[finding.rule_id]
        if any(_allows(rule, path, finding) for rule, path in allow_entries):
            finding.allowed = True
        findings.append(finding)
    return findings


def _parse_allow(entry: str) -> tuple[str, str | None]:
    rule, sep, path = entry.partition(":")
    rule = rule.strip()
    normalized_path = path.strip() if sep else None
    if rule not in RULE_IDS or (sep and not normalized_path):
        raise ValueError(f"invalid allow entry: {entry!r}")
    return rule, normalized_path


def _allows(rule: str, path: str | None, finding: Finding) -> bool:
    if rule != finding.rule_id:
        return False
    return path is None or path == finding.path


def _caps(access: object) -> frozenset[str]:
    return _ACCESS_CAPS.get(str(access), frozenset({"read", "write"}))


def _classify(c: Change) -> Finding:
    def finding(rule_id: str, severity: str, message: str) -> Finding:
        return Finding(rule_id=rule_id, severity=severity, path=c.path, message=message, change=c)

    if c.kind == "added":
        return finding("RD020", SAFE, f"{c.element} {c.path} added")

    if c.kind == "removed":
        if c.element == "peripheral":
            return finding("RD007", BREAKING, f"peripheral {c.path} removed")
        if c.element == "field":
            return finding("RD008", BREAKING, f"field {c.path} removed")
        if c.element == "enum":
            return finding(
                "RD013",
                BREAKING,
                f"enumerated value {c.path} removed (generated enum types lose the variant)",
            )
        if c.element == "interrupt":
            return finding("RD016", BREAKING, f"interrupt {c.path} removed")
        return finding("RD002", BREAKING, f"{c.element} {c.path} removed")

    if c.kind == "moved":
        if c.element == "peripheral":
            return finding(
                "RD006",
                BREAKING,
                f"peripheral {c.path} base address moved {_hex(c.before)} -> {_hex(c.after)}",
            )
        return finding(
            "RD001",
            BREAKING,
            f"{c.element} {c.path} address moved {_hex(c.before)} -> {_hex(c.after)}",
        )

    if c.kind == "renamed":
        basis = (
            "exact structural match"
            if c.confidence == 1.0
            else "heuristic match: descriptions differ"
        )
        return finding(
            "RD005",
            BREAKING,
            f"{c.element} {c.path} renamed (was {c.before}; {basis})",
        )

    # kind == "modified"
    if c.attribute == "description":
        return finding("RD030", SAFE, f"{c.element} {c.path} description changed")
    if c.element == "interrupt":
        return finding(
            "RD015",
            BREAKING,
            f"interrupt {c.path} renumbered {c.before} -> {c.after}",
        )
    if c.element == "enum":
        if c.attribute == "value":
            return finding(
                "RD011",
                BREAKING,
                f"enumerated value {c.path} changed {c.before!r} -> {c.after!r} "
                "(the same name now writes different bits)",
            )
        return finding(
            "RD022",
            WARNING,
            f"enumerated value {c.path} {c.attribute} changed {c.before!r} -> {c.after!r}",
        )
    if c.attribute == "bit_range":
        return finding(
            "RD003",
            BREAKING,
            f"field {c.path} bit range changed {c.before} -> {c.after}",
        )
    if c.attribute == "access":
        lost = _caps(c.before) - _caps(c.after)
        if lost:
            return finding(
                "RD004",
                BREAKING,
                f"{c.element} {c.path} access {c.before} -> {c.after} "
                f"loses {'/'.join(sorted(lost))} capability",
            )
        return finding(
            "RD021", SAFE, f"{c.element} {c.path} access {c.before} -> {c.after} (gain only)"
        )
    if c.attribute == "size":
        return finding(
            "RD009", BREAKING, f"register {c.path} size changed {c.before} -> {c.after}"
        )
    if c.attribute == "modified_write_values":
        return finding(
            "RD017",
            BREAKING,
            f"{c.element} {c.path} write semantics changed {c.before} -> {c.after} "
            "(what writing a bit does is inverted or altered)",
        )
    if c.attribute == "read_action":
        return finding(
            "RD018",
            BREAKING,
            f"{c.element} {c.path} read side effect changed "
            f"{c.before or 'none'} -> {c.after or 'none'}",
        )
    if c.attribute == "reset_value":
        return finding(
            "RD010",
            WARNING,
            f"register {c.path} reset value changed {_hex(c.before)} -> {_hex(c.after)}",
        )
    if c.attribute == "reset_mask":
        return finding(
            "RD012",
            WARNING,
            f"register {c.path} reset mask changed {_hex(c.before)} -> {_hex(c.after)}",
        )
    if c.attribute == "protection":
        return finding(
            "RD014", WARNING, f"{c.element} {c.path} protection changed {c.before} -> {c.after}"
        )
    raise ValueError(f"unclassified change: {c!r}")  # diff emitted an unknown attribute


def _hex(value: object) -> str:
    return f"0x{value:X}" if isinstance(value, int) else str(value)
