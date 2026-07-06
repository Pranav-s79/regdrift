"""Command-line interface for regdrift."""

import click

from regdrift import __version__


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="regdrift")
def main() -> None:
    """Diff CMSIS-SVD register maps and classify changes as BREAKING/WARNING/SAFE."""
