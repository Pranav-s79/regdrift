"""Command-line interface for regdrift."""

import json
import sys
from dataclasses import asdict
from pathlib import Path

import click

from regdrift import __version__
from regdrift.config import ConfigError, load_config, validate_allow_entries
from regdrift.diff import diff_devices
from regdrift.model import Cluster, Device, Register, device_to_dict
from regdrift.parse import SvdParseError, parse_svd, parse_svd_string
from regdrift.report import ReportMeta, failed, render_github, render_json, render_text
from regdrift.rules import classify_changes


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
@click.option("--json", "as_json", is_flag=True, help="(deprecated) Same as --format json.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def diff(old_svd: Path, new_svd: Path, as_json: bool, output_format: str) -> None:
    """List structural changes between OLD_SVD and NEW_SVD (no severities)."""
    changes = diff_devices(_load(old_svd), _load(new_svd))
    if as_json or output_format == "json":
        click.echo(json.dumps([asdict(c) for c in changes], indent=2))
        return
    for c in changes:
        detail = ""
        if c.attribute is not None:
            detail = f" {c.attribute}: {c.before!r} -> {c.after!r}"
        click.echo(f"{c.kind:<9} {c.element:<10} {c.path}{detail}")
    click.echo(f"{len(changes)} change(s)")


@main.command()
@click.argument("old_svd")
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
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "github"]),
    default="text",
    help="Output format.",
)
@click.option("--all", "show_all", is_flag=True, help="List SAFE findings in the text report.")
@click.option(
    "--fail-on",
    type=click.Choice(["breaking", "warning"]),
    default="breaking",
    help="Severity threshold that fails the gate.",
)
def check(
    old_svd: str,
    new_svd: Path,
    allow_flags: tuple[str, ...],
    config_path: Path | None,
    output_format: str,
    show_all: bool,
    fail_on: str,
) -> None:
    """Gate OLD_SVD -> NEW_SVD: fail on unallowed BREAKING changes.

    OLD_SVD may be "-" to read from stdin.

    \b
    Exit codes:
      0  no unallowed findings at or above the --fail-on threshold
      1  at least one unallowed finding at or above the --fail-on threshold
      2  tool error (unreadable file, malformed SVD, bad config)
    """
    try:
        config = load_config(config_path)
        validate_allow_entries(allow_flags, "--allow")
        if old_svd == "-":
            old = parse_svd_string(sys.stdin.read())
        elif not Path(old_svd).exists():
            click.echo(f"error: {old_svd}: file not found", err=True)
            sys.exit(2)
        else:
            old = parse_svd(Path(old_svd))
        new = parse_svd(new_svd)
    except (ConfigError, SvdParseError) as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(2)
    findings = classify_changes(
        diff_devices(old, new),
        allow=config.allow + list(allow_flags),
        severity_overrides=config.severity_overrides,
    )
    meta = ReportMeta(
        old_file=str(old_svd),
        new_file=str(new_svd),
        old_device=old.name,
        new_device=new.name,
        fail_on=fail_on,
    )
    if output_format == "text":
        click.echo(render_text(findings, meta, show_all=show_all))
    elif output_format == "json":
        click.echo(render_json(findings, meta))
    else:
        rendered = render_github(findings, meta)
        if rendered:
            click.echo(rendered)
    sys.exit(1 if failed(findings, fail_on) else 0)


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
