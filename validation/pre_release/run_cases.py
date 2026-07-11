#!/usr/bin/env python3
"""Run all generated Regdrift pre-release validation cases and write reports."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CASES_DIR = HERE / "cases"
REPORTS_DIR = HERE / "reports"


@dataclass
class CommandResult:
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float


def run(command: list[str], cwd: Path) -> CommandResult:
    started = time.perf_counter()
    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    return CommandResult(
        command=command,
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        duration_seconds=time.perf_counter() - started,
    )


def finding_rule(finding: dict[str, Any]) -> str | None:
    for key in ("rule_id", "rule", "id"):
        value = finding.get(key)
        if isinstance(value, str) and value.startswith("RD"):
            return value
    return None


def finding_severity(finding: dict[str, Any]) -> str | None:
    value = finding.get("severity")
    return value.upper() if isinstance(value, str) else None


def parse_check_json(text: str) -> dict[str, Any] | None:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def markdown_report(results: list[dict[str, Any]], version_text: str) -> str:
    strict_results = [result for result in results if result["strict"]]
    passed = sum(1 for result in strict_results if result["passed"])
    failed = len(strict_results) - passed
    lines = [
        "# Regdrift pre-release validation report",
        "",
        f"- Regdrift: `{version_text.strip() or 'unknown'}`",
        f"- Strict cases passed: **{passed}/{len(strict_results)}**",
        f"- Strict cases failed: **{failed}**",
        "",
        "| Case | Category | Expected exit | Actual exit | Rules | Deterministic | Result |",
        "|---|---|---:|---:|---|---|---|",
    ]
    for result in results:
        if result["expected_exit_code"] is None:
            expected = "observe"
        else:
            expected = str(result["expected_exit_code"])
        actual = str(result.get("actual_exit_code", "n/a"))
        rules = ", ".join(result.get("actual_rules", [])) or "none"
        verdict = "PASS" if result["passed"] else ("OBSERVE" if not result["strict"] else "FAIL")
        lines.append(
            f"| {result['case']} | {result['category']} | {expected} | {actual} | {rules} | "
            f"{'yes' if result.get('deterministic') else 'no'} | {verdict} |"
        )
    lines.extend(["", "## Details", ""])
    for result in results:
        lines.append(f"### {result['case']}")
        lines.append("")
        lines.append(f"- Passed: `{result['passed']}`")
        lines.append(f"- Expected rules: `{result.get('expected_rules', [])}`")
        lines.append(f"- Actual rules: `{result.get('actual_rules', [])}`")
        lines.append(f"- Expected severities: `{result.get('expected_severities', [])}`")
        lines.append(f"- Actual severities: `{result.get('actual_severities', [])}`")
        lines.append(f"- Duration: `{result.get('duration_seconds', 0):.3f}s`")
        for problem in result.get("problems", []):
            lines.append(f"- Problem: {problem}")
        notes = result.get("notes")
        if notes:
            lines.append(f"- Notes: {notes}")
        lines.append("")
    recommendation = "ready for alpha" if failed == 0 else "needs investigation before alpha"
    lines.extend(["## Recommendation", "", f"**{recommendation}**", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--regdrift", default="regdrift", help="Regdrift command, default: regdrift"
    )
    parser.add_argument(
        "--repo-root", type=Path, default=HERE.parent.parent, help="Regdrift repository root"
    )
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    base_command = shlex.split(args.regdrift, posix=os.name != "nt")
    if not base_command:
        print("error: empty --regdrift command", file=sys.stderr)
        return 2
    if not CASES_DIR.exists() or not any(CASES_DIR.glob("*/case.json")):
        print("error: cases have not been built; run setup_cases.py first", file=sys.stderr)
        return 2

    version = run(base_command + ["--version"], repo_root)
    version_text = version.stdout.strip() or version.stderr.strip()
    results: list[dict[str, Any]] = []

    for case_dir in sorted(path.parent for path in CASES_DIR.glob("*/case.json")):
        metadata = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
        old = case_dir / "old.svd"
        new = case_dir / "new.svd"
        commands: dict[str, CommandResult] = {}
        commands["parse_old"] = run(base_command + ["parse", str(old)], repo_root)
        commands["parse_new"] = run(base_command + ["parse", str(new)], repo_root)
        check_args = ["check", str(old), str(new)]
        commands["diff_json"] = run(
            base_command + ["diff", str(old), str(new), "--format", "json"], repo_root
        )
        commands["check_json_1"] = run(base_command + check_args + ["--format", "json"], repo_root)
        commands["check_json_2"] = run(base_command + check_args + ["--format", "json"], repo_root)
        commands["check_all"] = run(base_command + check_args + ["--all"], repo_root)
        commands["check_warning"] = run(
            base_command + check_args + ["--fail-on", "warning", "--format", "json"], repo_root
        )

        check = commands["check_json_1"]
        payload = parse_check_json(check.stdout)
        findings = payload.get("findings", []) if payload else []
        if not isinstance(findings, list):
            findings = []
        rules = sorted(
            {rule for item in findings if isinstance(item, dict) and (rule := finding_rule(item))}
        )
        severities = sorted(
            {
                severity
                for item in findings
                if isinstance(item, dict) and (severity := finding_severity(item))
            }
        )
        expected_exit = metadata.get("expected_exit_code")
        expected_rules = sorted(metadata.get("expected_rules", []))
        expected_severities = sorted(metadata.get("expected_severities", []))
        strict = bool(metadata.get("strict", True))
        deterministic = commands["check_json_1"].stdout == commands["check_json_2"].stdout
        problems: list[str] = []

        if strict and expected_exit is not None and check.exit_code != expected_exit:
            problems.append(f"expected exit {expected_exit}, got {check.exit_code}")
        if strict and expected_rules and not set(expected_rules).issubset(rules):
            problems.append(f"missing expected rules: {sorted(set(expected_rules) - set(rules))}")
        if strict and expected_severities and not set(expected_severities).issubset(severities):
            missing = sorted(set(expected_severities) - set(severities))
            problems.append(f"missing expected severities: {missing}")
        if strict and not deterministic:
            problems.append("JSON output changed between identical runs")
        if metadata["category"] == "identity" and (rules or check.exit_code != 0):
            problems.append("identity comparison produced findings or failed")
        is_malformed_case = case_dir.name.endswith("malformed_xml")
        if is_malformed_case and commands["parse_new"].exit_code != 2 and check.exit_code != 2:
            problems.append("malformed XML did not produce documented tool exit code 2")
        if case_dir.name.startswith("11_reset_value") and commands["check_warning"].exit_code != 1:
            problems.append("warning case did not fail under --fail-on warning")

        duration = sum(result.duration_seconds for result in commands.values())
        result_record: dict[str, Any] = {
            "case": case_dir.name,
            "category": metadata["category"],
            "strict": strict,
            "passed": not problems if strict else True,
            "expected_exit_code": expected_exit,
            "actual_exit_code": check.exit_code,
            "expected_rules": expected_rules,
            "actual_rules": rules,
            "expected_severities": expected_severities,
            "actual_severities": severities,
            "deterministic": deterministic,
            "duration_seconds": duration,
            "problems": problems,
            "notes": metadata.get("notes", ""),
            "commands": {
                name: {
                    "command": value.command,
                    "exit_code": value.exit_code,
                    "stdout": value.stdout,
                    "stderr": value.stderr,
                    "duration_seconds": value.duration_seconds,
                }
                for name, value in commands.items()
            },
        }
        results.append(result_record)
        status = "PASS" if result_record["passed"] else "FAIL"
        print(f"{status:4} {case_dir.name}: exit={check.exit_code} rules={rules}")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    strict_failures = [result for result in results if result["strict"] and not result["passed"]]
    report = {
        "schema_version": 1,
        "regdrift_version": version_text,
        "repo_root": str(repo_root),
        "strict_failures": len(strict_failures),
        "cases": results,
    }
    (REPORTS_DIR / "latest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (REPORTS_DIR / "latest.md").write_text(markdown_report(results, version_text), encoding="utf-8")
    print(f"\nReports written to {REPORTS_DIR}")
    return 1 if strict_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
