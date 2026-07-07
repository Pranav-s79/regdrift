"""Render classified findings as text, JSON, or GitHub workflow annotations."""

import json
from dataclasses import dataclass

import click

from regdrift import __version__
from regdrift.rules import BREAKING, SAFE, WARNING, Finding

_HEX_ATTRS = frozenset({"address_offset", "base_address", "reset_value", "reset_mask"})
_GITHUB_LEVEL = {BREAKING: "error", WARNING: "warning"}
_MAX_ANNOTATIONS_PER_LEVEL = 9


@dataclass
class ReportMeta:
    old_file: str
    new_file: str
    old_device: str
    new_device: str
    fail_on: str  # "breaking" | "warning"


def failed(findings: list[Finding], fail_on: str) -> bool:
    for f in findings:
        if f.allowed:
            continue
        if f.severity == BREAKING or (fail_on == "warning" and f.severity == WARNING):
            return True
    return False


def summary_counts(findings: list[Finding]) -> dict[str, int]:
    counts = {"breaking": 0, "warning": 0, "safe": 0, "allowed": 0}
    for f in findings:
        if f.allowed:
            counts["allowed"] += 1
        else:
            counts[f.severity.lower()] += 1
    return counts


def _display_value(attribute: str | None, value: object) -> object:
    if attribute in _HEX_ATTRS and isinstance(value, int):
        return f"0x{value:X}"
    return value


def _enum_rollup_key(f: Finding) -> tuple[str, str, str] | None:
    if f.change.element == "enum" and f.change.kind in ("added", "removed"):
        parent = f.path.rsplit(".", 1)[0]
        return (f.rule_id, parent, f.change.kind)
    return None


def _rollup_lines(findings: list[Finding]) -> list[str]:
    groups: dict[tuple[str, str, str], list[Finding]] = {}
    order: list[tuple[str, str, str] | None] = []
    singles: list[Finding] = []
    for f in findings:
        key = _enum_rollup_key(f)
        if key is None:
            singles.append(f)
            order.append(None)
            continue
        if key not in groups:
            order.append(key)
        groups.setdefault(key, []).append(f)

    lines: list[str] = []
    single_iter = iter(singles)
    emitted_groups: set[tuple[str, str, str]] = set()
    for key in order:
        if key is None:
            f = next(single_iter)
            lines.append(f"  {f.rule_id}  {f.message}")
            continue
        if key in emitted_groups:
            continue
        emitted_groups.add(key)
        group = groups[key]
        rule_id, parent, kind = key
        if len(group) == 1:
            lines.append(f"  {rule_id}  {group[0].message}")
            continue
        names = [g.path.rsplit(".", 1)[-1] for g in group]
        n = len(names)
        shown = names[:5]
        names_str = ", ".join(shown)
        if n > 5:
            names_str += ", ..."
        lines.append(f"  {rule_id}  field {parent}: {n} enum values {kind} ({names_str})")
    return lines


def render_text(findings: list[Finding], meta: ReportMeta, show_all: bool = False) -> str:
    sections: list[str] = []

    def section(
        label: str, items: list[Finding], *, fg: str | None = None, bold: bool = False,
        dim: bool = False,
    ) -> None:
        if not items:
            return
        ordered = sorted(
            enumerate(items), key=lambda pair: (pair[1].path.split(".")[0], pair[0])
        )
        sorted_items = [f for _, f in ordered]
        header = click.style(f"{label} ({len(items)})", fg=fg, bold=bold, dim=dim)
        lines = [header, *_rollup_lines(sorted_items)]
        sections.append("\n".join(lines))

    breaking = [f for f in findings if not f.allowed and f.severity == BREAKING]
    warning = [f for f in findings if not f.allowed and f.severity == WARNING]
    safe = [f for f in findings if not f.allowed and f.severity == SAFE]
    allowed = [f for f in findings if f.allowed]

    section("BREAKING", breaking, fg="red", bold=True)
    section("WARNING", warning, fg="yellow")
    section("ALLOWED", allowed, fg="cyan")

    if show_all:
        section("SAFE", safe, dim=True)
    elif safe:
        added = sum(1 for f in safe if f.change.kind == "added")
        desc = sum(1 for f in safe if f.change.attribute == "description")
        other = len(safe) - added - desc
        parts = []
        if added:
            parts.append(f"{added} added")
        if desc:
            parts.append(f"{desc} description-only")
        if other:
            parts.append(f"{other} other")
        sections.append(f"{len(safe)} safe ({', '.join(parts)}) - use --all to list")

    counts = summary_counts(findings)
    sections.append(
        f"{counts['breaking']} breaking, {counts['warning']} warning, "
        f"{counts['safe']} safe, {counts['allowed']} allowed"
    )
    return "\n\n".join(sections)


def render_json(findings: list[Finding], meta: ReportMeta) -> str:
    document = {
        "schema_version": 1,
        "regdrift_version": __version__,
        "old": {"file": meta.old_file, "device": meta.old_device},
        "new": {"file": meta.new_file, "device": meta.new_device},
        "summary": summary_counts(findings),
        "passed": not failed(findings, meta.fail_on),
        "findings": [
            {
                "rule": f.rule_id,
                "severity": f.severity,
                "allowed": f.allowed,
                "element": f.change.element,
                "path": f.path,
                "kind": f.change.kind,
                "attribute": f.change.attribute,
                "before": _display_value(f.change.attribute, f.change.before),
                "after": _display_value(f.change.attribute, f.change.after),
                "confidence": f.change.confidence,
                "message": f.message,
            }
            for f in findings
        ],
    }
    return json.dumps(document, indent=2)


def render_github(findings: list[Finding], meta: ReportMeta) -> str:
    lines: list[str] = []
    for severity, level in (("BREAKING", "error"), ("WARNING", "warning")):
        items = [f for f in findings if not f.allowed and f.severity == severity]
        shown = items[:_MAX_ANNOTATIONS_PER_LEVEL]
        for f in shown:
            lines.append(
                f"::{level} file={meta.new_file},title={f.rule_id} {f.path}::{f.message}"
            )
        overflow = len(items) - len(shown)
        if overflow > 0:
            noun = "breaking" if level == "error" else "warning"
            lines.append(
                f"::{level} file={meta.new_file},title=regdrift::"
                f"and {overflow} more {noun} findings - see the log or step summary"
            )
    return "\n".join(lines)
