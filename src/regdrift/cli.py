"""Command-line interface for regdrift."""

import json
from dataclasses import asdict
from pathlib import Path

import click

from regdrift import __version__
from regdrift.diff import diff_devices
from regdrift.model import Cluster, Device, Register, device_to_dict
from regdrift.parse import SvdParseError, parse_svd


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
