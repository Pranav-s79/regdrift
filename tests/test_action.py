"""Static safety and installation contracts for the composite GitHub Action."""

from pathlib import Path

ACTION = Path(__file__).parent.parent / "action.yml"


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


def test_action_does_not_interpolate_inputs_into_shell_code() -> None:
    action = ACTION.read_text()
    shell_code = "\n".join(_shell_blocks(action))
    assert "${{" not in shell_code


def test_action_installs_its_checked_out_source_by_default() -> None:
    action = ACTION.read_text()
    version_input = action.split("  version:", 1)[1].split("runs:", 1)[0]
    assert 'default: "source"' in version_input
    assert "pip install \"$GITHUB_ACTION_PATH\"" in action
