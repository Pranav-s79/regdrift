"""Smoke test: the package installs and the CLI answers --version."""

from click.testing import CliRunner

from regdrift import __version__
from regdrift.cli import main


def test_version() -> None:
    result = CliRunner().invoke(main, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output
