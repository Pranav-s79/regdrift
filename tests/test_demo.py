"""demo/ must stay in sync with scripts/make_demo.py and show a breaking check."""

import subprocess
import sys
from pathlib import Path

from click.testing import CliRunner

from regdrift.cli import main

REPO_ROOT = Path(__file__).parent.parent
DEMO_DIR = REPO_ROOT / "demo"


def test_demo_files_match_generator(tmp_path: Path) -> None:
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "make_demo.py"), str(tmp_path)],
        check=True,
    )
    for name in ("chip_v1.svd", "chip_v2.svd", "README.md"):
        generated = (tmp_path / name).read_bytes()
        committed = (DEMO_DIR / name).read_bytes()
        assert generated == committed, f"demo/{name} is out of sync with make_demo.py"


def test_demo_check_exits_one() -> None:
    result = CliRunner().invoke(
        main, ["check", str(DEMO_DIR / "chip_v1.svd"), str(DEMO_DIR / "chip_v2.svd")]
    )
    assert result.exit_code == 1


def test_demo_check_contains_expected_rules() -> None:
    result = CliRunner().invoke(
        main, ["check", str(DEMO_DIR / "chip_v1.svd"), str(DEMO_DIR / "chip_v2.svd")]
    )
    for rule in ("RD001", "RD005", "RD015", "RD017"):
        assert rule in result.output
    assert "4 breaking, 1 warning, 1 safe, 0 allowed" in result.output
