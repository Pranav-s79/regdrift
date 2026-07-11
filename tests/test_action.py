"""Safety, installation, and base-resolution contracts for the composite GitHub Action.

The static tests read action.yml directly. The behavioral tests execute the
"Extract base SVD" shell block against a throwaway git repository (paths with
spaces and parentheses included) the same way the composite runner would:
quoted env vars in, $GITHUB_OUTPUT and $RUNNER_TEMP/base.svd out.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from regdrift.cli import main

ACTION = Path(__file__).parent.parent / "action.yml"
DEMO = Path(__file__).parent.parent / "demo"
SVD_REL = "hardware dir/device (v1).svd"

requires_git_bash = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None,
    reason="behavioral action tests need bash and git (CI always has both)",
)


def _shell_blocks(action: str) -> list[str]:
    lines = action.splitlines()
    blocks: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.strip() != "run: |":
            index += 1
            continue
        indentation = len(line) - len(line.lstrip())
        index += 1
        block: list[str] = []
        while index < len(lines):
            candidate = lines[index]
            candidate_indentation = len(candidate) - len(candidate.lstrip())
            if candidate.strip() and candidate_indentation <= indentation:
                break
            block.append(candidate)
            index += 1
        blocks.append("\n".join(block))
    return blocks


def _extract_base_block() -> str:
    blocks = [b for b in _shell_blocks(ACTION.read_text()) if "git show" in b]
    assert len(blocks) == 1, "expected exactly one Extract base SVD shell block"
    return blocks[0]


# GitHub Marketplace rejects actions whose description exceeds this limit.
MARKETPLACE_DESCRIPTION_LIMIT = 125
MARKETPLACE_BRANDING_COLORS = {
    "white",
    "yellow",
    "blue",
    "green",
    "orange",
    "red",
    "purple",
    "gray-dark",
}


def _metadata_value(action: str, pattern: str) -> str:
    match = re.search(pattern, action, flags=re.MULTILINE)
    assert match is not None, f"action.yml is missing {pattern!r}"
    return match.group(1)


def test_action_marketplace_metadata_is_valid() -> None:
    action = ACTION.read_text()
    name = _metadata_value(action, r'^name: "(.*)"$')
    description = _metadata_value(action, r'^description: "(.*)"$')
    icon = _metadata_value(action, r'^  icon: "(.*)"$')
    color = _metadata_value(action, r'^  color: "(.*)"$')
    assert name == "regdrift check"
    assert description.strip(), "Marketplace requires a non-empty description"
    assert len(description) <= MARKETPLACE_DESCRIPTION_LIMIT, len(description)
    assert icon == "cpu"
    assert color in MARKETPLACE_BRANDING_COLORS


def test_action_does_not_interpolate_inputs_into_shell_code() -> None:
    action = ACTION.read_text()
    shell_code = "\n".join(_shell_blocks(action))
    assert "${{" not in shell_code


def test_action_installs_its_checked_out_source_by_default() -> None:
    action = ACTION.read_text()
    version_input = action.split("  version:", 1)[1].split("runs:", 1)[0]
    assert 'default: "source"' in version_input
    assert "pip install \"$GITHUB_ACTION_PATH\"" in action


def test_action_verifies_base_ref_before_reading_the_file() -> None:
    block = _extract_base_block()
    assert "git rev-parse --verify" in block
    assert block.index("git rev-parse --verify") < block.index("git show")


# ---------------------------------------------------------------------------
# Behavioral tests for the Extract base SVD step
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def action_repo(tmp_path: Path) -> Path:
    """A git repo whose HEAD commits demo/chip_v1.svd at a path with spaces."""
    repo = tmp_path / "work repo"
    repo.mkdir()
    _git(repo, "init", "--quiet")
    svd = repo / SVD_REL
    svd.parent.mkdir(parents=True)
    svd.write_text((DEMO / "chip_v1.svd").read_text(), encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "--quiet", "-m", "base")
    return repo


def _run_extract(
    repo: Path,
    tmp_path: Path,
    *,
    base_ref: str,
    event_base_ref: str = "",
    svd_path: str = SVD_REL,
) -> tuple[subprocess.CompletedProcess[str], Path, dict[str, str]]:
    runner_temp = tmp_path / "runner temp"
    runner_temp.mkdir(exist_ok=True)
    output_file = tmp_path / "github_output"
    output_file.write_text("", encoding="utf-8")
    env = {
        **os.environ,
        "REGDRIFT_BASE_REF": base_ref,
        "REGDRIFT_EVENT_BASE_REF": event_base_ref,
        "REGDRIFT_SVD_PATH": svd_path,
        "RUNNER_TEMP": str(runner_temp).replace("\\", "/"),
        "GITHUB_OUTPUT": str(output_file).replace("\\", "/"),
    }
    proc = subprocess.run(
        ["bash", "-o", "pipefail", "-ec", _extract_base_block()],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
    )
    outputs = dict(
        line.split("=", 1)
        for line in output_file.read_text(encoding="utf-8").splitlines()
        if "=" in line
    )
    return proc, runner_temp / "base.svd", outputs


@requires_git_bash
def test_extract_valid_ref_with_existing_base_svd(action_repo: Path, tmp_path: Path) -> None:
    proc, base_svd, outputs = _run_extract(action_repo, tmp_path, base_ref="HEAD")
    assert proc.returncode == 0, proc.stderr
    assert outputs.get("found") == "true"
    assert base_svd.read_text(encoding="utf-8") == (DEMO / "chip_v1.svd").read_text()


@requires_git_bash
def test_extract_valid_ref_with_missing_base_svd_skips_cleanly(
    action_repo: Path, tmp_path: Path
) -> None:
    proc, _, outputs = _run_extract(
        action_repo, tmp_path, base_ref="HEAD", svd_path="hardware dir/new device.svd"
    )
    assert proc.returncode == 0, proc.stderr
    assert outputs.get("found") == "false"


@requires_git_bash
def test_extract_invalid_base_ref_fails_instead_of_passing(
    action_repo: Path, tmp_path: Path
) -> None:
    proc, base_svd, outputs = _run_extract(
        action_repo, tmp_path, base_ref="origin/does-not-exist"
    )
    assert proc.returncode != 0
    assert "found" not in outputs
    assert "unresolvable base ref" in proc.stderr
    assert not base_svd.exists() or not base_svd.read_text(encoding="utf-8")


@requires_git_bash
def test_extract_unfetched_pr_base_branch_fails_instead_of_passing(
    action_repo: Path, tmp_path: Path
) -> None:
    # A pull_request event on a shallow checkout: base-ref empty, the event's
    # base branch was never fetched. This must be an error, not a clean skip.
    proc, _, outputs = _run_extract(
        action_repo, tmp_path, base_ref="", event_base_ref="main-not-fetched"
    )
    assert proc.returncode != 0
    assert "found" not in outputs


@requires_git_bash
def test_gate_passes_identity_comparison_against_extracted_base(
    action_repo: Path, tmp_path: Path
) -> None:
    proc, base_svd, _ = _run_extract(action_repo, tmp_path, base_ref="HEAD")
    assert proc.returncode == 0, proc.stderr
    result = CliRunner().invoke(main, ["check", str(base_svd), str(action_repo / SVD_REL)])
    assert result.exit_code == 0, result.output


@requires_git_bash
def test_gate_fails_breaking_comparison_against_extracted_base(
    action_repo: Path, tmp_path: Path
) -> None:
    proc, base_svd, _ = _run_extract(action_repo, tmp_path, base_ref="HEAD")
    assert proc.returncode == 0, proc.stderr
    working_svd = action_repo / SVD_REL
    working_svd.write_text((DEMO / "chip_v2.svd").read_text(), encoding="utf-8")
    result = CliRunner().invoke(main, ["check", str(base_svd), str(working_svd)])
    assert result.exit_code == 1, result.output
