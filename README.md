# regdrift

[![PyPI](https://img.shields.io/pypi/v/regdrift)](https://pypi.org/project/regdrift/)
[![Python versions](https://img.shields.io/pypi/pyversions/regdrift)](https://pypi.org/project/regdrift/)
[![CI](https://github.com/Pranav-s79/regdrift/actions/workflows/ci.yml/badge.svg)](https://github.com/Pranav-s79/regdrift/actions/workflows/ci.yml)
[![Action self-test](https://github.com/Pranav-s79/regdrift/actions/workflows/action-selftest.yml/badge.svg)](https://github.com/Pranav-s79/regdrift/actions/workflows/action-selftest.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

**regdrift is a compatibility gate for CMSIS-SVD register maps.** It compares
two silicon descriptions, classifies every detected change as `BREAKING`,
`WARNING`, or `SAFE`, and returns a CI-friendly verdict.

A moved register can leave a driver compiling cleanly while every write lands
at the wrong address. regdrift catches that change in the pull request, before
it becomes a logic-analyzer debugging session.

> **Status:** `0.1.0a2` is a public alpha, published on
> [PyPI](https://pypi.org/project/regdrift/). The implementation is
> exercised against 15 pinned vendor SVDs, but the explicit limitations in
> [RULES.md](RULES.md#what-regdrift-does-not-check-yet) still apply.

## Highlights

- Resolves `derivedFrom`, register-property inheritance, nested clusters,
  `dim` arrays, enumerated values, interrupts, and read/write side effects.
- Uses deterministic structural matching with conservative rename detection.
- Applies a published 22-rule contract: 15 `BREAKING`, 4 `WARNING`, and 3
  `SAFE` rules.
- Produces ranked text, schema-versioned JSON, or GitHub workflow annotations.
- Supports exact-path allowlisting, project-wide severity overrides, stdin for
  the baseline file, and configurable failure thresholds.
- Ships as both a Python CLI and a composite GitHub Action.
- Has unit, CLI, mutation, fuzz, golden, real-vendor corpus, and performance
  coverage on Python 3.11 and 3.12.

## Installation

Install the current alpha from [PyPI](https://pypi.org/project/regdrift/):

```sh
python -m pip install regdrift==0.1.0a2
```

or, as an isolated CLI tool:

```sh
pipx install regdrift==0.1.0a2
```

To install from source instead:

```sh
git clone https://github.com/Pranav-s79/regdrift.git
cd regdrift
python -m venv .venv
# POSIX: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install .
```

For development, install the editable package and validation tools instead:

```sh
python -m pip install -e ".[dev]"
python scripts/fetch_corpus.py
```

## Quick start with the synthetic data

The committed [`demo/`](demo/) folder contains two revisions of an imaginary
accelerator. The candidate moves a register, renames a field, renumbers an
interrupt, changes write semantics and a reset value, and adds a register.

```sh
regdrift check demo/chip_v1.svd demo/chip_v2.svd
```

```text
BREAKING (4)
  RD015  interrupt ACCEL.ACCEL_DONE renumbered 17 -> 18
  RD005  field ACCEL.CTRL.ENABLE renamed (was EN; exact structural match)
  RD001  register ACCEL.STATUS address moved 0x8 -> 0xC
  RD017  field ACCEL.STATUS.DONE write semantics changed oneToClear -> oneToSet (what writing a bit does is inverted or altered)

WARNING (1)
  RD010  register ACCEL.STATUS reset value changed 0x1 -> 0x0

1 safe (1 added) - use --all to list

4 breaking, 1 warning, 1 safe, 0 allowed
```

The command exits `1` because the candidate contains unallowed breaking
changes. Run it with `--all` to list the safe addition too.

## CLI

| Command | Purpose |
| --- | --- |
| `regdrift parse DEVICE.svd` | Validate and summarize a resolved SVD model. |
| `regdrift parse DEVICE.svd --json` | Emit the canonical model as JSON. |
| `regdrift diff OLD.svd NEW.svd` | List factual structural changes without policy. |
| `regdrift diff OLD.svd NEW.svd --format json` | Emit the raw change list as JSON. |
| `regdrift check OLD.svd NEW.svd` | Classify changes and enforce the compatibility gate. |

Useful gate options:

```sh
# Show SAFE findings instead of rolling them up.
regdrift check old.svd new.svd --all

# Fail on warnings as well as breaking changes.
regdrift check old.svd new.svd --fail-on warning

# Produce stable machine-readable output.
regdrift check old.svd new.svd --format json

# Emit GitHub workflow commands.
regdrift check old.svd new.svd --format github

# Read the baseline from stdin.
git show origin/main:device.svd | regdrift check - device.svd
```

`check` uses these exit codes:

| Code | Meaning |
| --- | --- |
| `0` | No unallowed finding meets the failure threshold. |
| `1` | At least one unallowed finding meets the failure threshold. |
| `2` | The SVD, configuration, path, or command input is invalid. |

## Rulebook and configuration

[RULES.md](RULES.md) is the normative compatibility contract. Every emitted
change must map to exactly one documented rule or classification fails
explicitly.

Create `.regdrift.toml` in the working directory to acknowledge intentional
breaks or adjust policy for a specific toolchain:

```toml
allow = [
  "RD001:UART0.CTRL", # this rule at this exact path
  "RD030",            # this rule at every path
]

[severity]
RD013 = "WARNING"    # enum removals do not break this project's generator
RD010 = "BREAKING"   # reset-value drift must fail this project
```

Command-line entries add to the file allowlist:

```sh
regdrift check old.svd new.svd --allow RD001:UART0.CTRL --allow RD030
```

Configuration is strict: unknown keys, unpublished rule IDs, malformed allow
entries, and invalid severities are tool errors rather than silent no-ops.
Allowlisting wins over severity overrides and is reported separately as
`ALLOWED`.

## GitHub Actions

The bundled action extracts the baseline SVD from the pull request's base ref,
runs the gate, writes a step summary, adds workflow annotations, and can update
a sticky pull-request comment.

```yaml
name: Register-map compatibility

on:
  pull_request:

permissions:
  contents: read
  pull-requests: write

jobs:
  regdrift:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: Pranav-s79/regdrift@v0.1.0a2
        with:
          svd-path: hardware/device.svd
          fail-on: breaking
```

The action installs the source at the selected action ref by default, so its
runtime and action definition stay in sync. Set the optional `version` input to
an exact published package version to install from PyPI instead. Disable the
sticky comment with `comment: "false"` if the workflow only has read access.

For a fully manual workflow, install the package and run:

```sh
regdrift check /tmp/base.svd hardware/device.svd --format github
```

## Output contracts

- Text output is optimized for review: breaking findings first, then warnings,
  allowed findings, and a safe-change rollup.
- JSON output includes `schema_version: 1`, device metadata, summary counts,
  the verdict, and every finding. See [docs/json-schema.md](docs/json-schema.md).
- GitHub output escapes untrusted paths and SVD-derived text and caps each
  annotation severity at nine entries to keep workflow output usable.

## Architecture

```text
SVD/XML -> canonical parser -> structural diff -> rule classification -> report -> exit code
```

Parsing, factual diffing, policy classification, rendering, and CLI
orchestration are separate modules. See [docs/architecture.md](docs/architecture.md)
for ownership boundaries and testing strategy.

## Data and verification

- [`demo/`](demo/) is committed, deterministic synthetic data. Regenerate it
  with `python scripts/make_demo.py`; CI verifies its generated content.
- `tests/corpus/` is a gitignored, pinned 15-file vendor corpus downloaded by
  `python scripts/fetch_corpus.py`.
- `tests/golden/` locks canonical parser output for selected corpus files.
- The mutation harness proves that every published rule fires against real
  vendor models.

Run the same checks enforced by CI:

```sh
ruff check .
mypy
pytest
```

Contributor setup and change requirements are documented in
[CONTRIBUTING.md](CONTRIBUTING.md).

## Project documentation

- [RULES.md](RULES.md) — severities, rationales, calibration, and limitations
- [docs/architecture.md](docs/architecture.md) — module boundaries and test strategy
- [docs/json-schema.md](docs/json-schema.md) — machine-readable output contract
- [CHANGELOG.md](CHANGELOG.md) — release history
- [docs/release-checklist.md](docs/release-checklist.md) — maintainer release runbook

## License

Apache-2.0. See [LICENSE](LICENSE).
