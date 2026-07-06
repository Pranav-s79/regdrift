"""Command-line interface for regdrift."""

import json
import sys
from dataclasses import asdict
from pathlib import Path

import click

from regdrift import __version__
from regdrift.config import ConfigError, load_allowlist
from regdrift.diff import diff_devices
from regdrift.model import Cluster, Device, Register, device_to_dict
from regdrift.parse import SvdParseError, parse_svd
from regdrift.rules import ALLOWED, BREAKING, SAFE, WARNING, classify_changes


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="regdrift")
def main() -> None:
    """Diff CMSIS-SVD register maps and classify changes as BREAKING/WARNING/SAFE."""


@main.command()
@click.argument("svd_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--json", "as_json", is_flag=True, help="Dump the fully resolved model as JSON.")
def parse(svd_file: Path, as_json: bool) -> None:
    """Parse SVD_FILE into the fully resolved canonical model."""
    device = _load(svd_file)
    if as_json:
        click.echo(json.dumps(device_to_dict(device), indent=2))
        return
    n_registers = sum(_count_registers(p.children) for p in device.peripherals)
    click.echo(
        f"{device.name}: {len(device.peripherals)} peripherals, "
        f"{n_registers} registers (fully resolved)"
    )


@main.command()
@click.argument("old_svd", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("new_svd", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--json", "as_json", is_flag=True, help="Print the change list as JSON.")
def diff(old_svd: Path, new_svd: Path, as_json: bool) -> None:
    """List structural changes between OLD_SVD and NEW_SVD (no severities)."""
    changes = diff_devices(_load(old_svd), _load(new_svd))
    if as_json:
        click.echo(json.dumps([asdict(c) for c in changes], indent=2))
        return
    for c in changes:
        detail = ""
        if c.attribute is not None:
            detail = f" {c.attribute}: {c.before!r} -> {c.after!r}"
        click.echo(f"{c.kind:<9} {c.element:<10} {c.path}{detail}")
    click.echo(f"{len(changes)} change(s)")


@main.command()
@click.argument("old_svd", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("new_svd", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--allow",
    "allow_flags",
    multiple=True,
    metavar="RULE[:PATH]",
    help="Allow a finding (e.g. RD001:UART0.CTRL). Repeatable; adds to .regdrift.toml.",
)
@click.option(
    "--config",
    "config_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Allowlist config file [default: ./.regdrift.toml if present].",
)
def check(
    old_svd: Path, new_svd: Path, allow_flags: tuple[str, ...], config_path: Path | None
) -> None:
    """Gate OLD_SVD -> NEW_SVD: fail on unallowed BREAKING changes.

    \b
    Exit codes:
      0  no unallowed BREAKING findings
      1  at least one unallowed BREAKING finding
      2  tool error (unreadable file, malformed SVD, bad config)
    """
    try:
        allow = load_allowlist(config_path) + list(allow_flags)
        old = parse_svd(old_svd)
        new = parse_svd(new_svd)
    except (ConfigError, SvdParseError) as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(2)
    findings = classify_changes(diff_devices(old, new), allow=allow)
    for f in findings:
        click.echo(f"{f.severity:<9} {f.rule_id}  {f.message}")
    counts = {sev: 0 for sev in (BREAKING, WARNING, SAFE, ALLOWED)}
    for f in findings:
        counts[f.severity] += 1
    click.echo(
        f"{counts[BREAKING]} breaking, {counts[WARNING]} warning, "
        f"{counts[SAFE]} safe, {counts[ALLOWED]} allowed"
    )
    sys.exit(1 if counts[BREAKING] else 0)


def _load(svd_file: Path) -> Device:
    try:
        return parse_svd(svd_file)
    except SvdParseError as exc:
        raise click.ClickException(f"{svd_file}: {exc}") from exc


def _count_registers(children: list[Register | Cluster]) -> int:
    count = 0
    for child in children:
        if isinstance(child, Register):
            count += 1
        else:
            count += _count_registers(child.children)
    return count
