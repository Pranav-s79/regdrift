# Agent operating model

This document is the tool-neutral source of truth for coding agents working on
regdrift. `AGENTS.md` and `CLAUDE.md` are discovery adapters for their
respective tools and must not become separate policy manuals.

## Authoritative project sources

- [README.md](../README.md) defines the product purpose and user-facing
  workflow.
- [RULES.md](../RULES.md) is the normative compatibility-classification
  contract.
- [CONTRIBUTING.md](../CONTRIBUTING.md) defines contributor setup and required
  validation.
- [pyproject.toml](../pyproject.toml) defines supported Python versions,
  dependencies, linting, strict typing, and test configuration.
- Source code and tests are authoritative for implemented behavior. If they
  conflict with documentation, identify the mismatch rather than guessing.

## Project purpose

regdrift parses two CMSIS-SVD register maps, computes their structural
differences, and classifies each change as `BREAKING`, `WARNING`, or `SAFE`.
The CLI and CI gate must produce deterministic, reviewable results.

## Project map

| Path | Responsibility |
| --- | --- |
| `src/regdrift/model.py` | Typed canonical CMSIS-SVD model |
| `src/regdrift/parse.py` | XML parsing, `derivedFrom` resolution, inheritance, and array expansion |
| `src/regdrift/diff.py` | Structural matching and factual change detection |
| `src/regdrift/rules.py` | Exhaustive mapping from changes to rules and severities |
| `src/regdrift/config.py` | Strict `.regdrift.toml` allowlist and severity configuration |
| `src/regdrift/report.py` | Text, versioned JSON, and escaped GitHub annotation rendering |
| `src/regdrift/cli.py` | Click commands, orchestration, and exit codes |
| `demo/` | Committed deterministic synthetic SVD revision pair |
| `tests/` | Unit, CLI, fuzz, mutation, corpus, golden, and performance coverage |
| `tests/golden/` | Committed parser-output snapshots and hashes |
| `tests/corpus/` | Downloaded, gitignored vendor fixtures |
| `scripts/` | Synthetic-data generation, pinned corpus download, and intentional golden regeneration |
| `action.yml` | Composite GitHub Action gate |
| `.github/workflows/` | Python CI, action self-test, and trusted-publishing release automation |
| `docs/` | Shared guidance, decisions, and verification records |

## Architecture boundaries

The intended dependency flow is:

`SVD/XML -> parser -> canonical model -> structural diff -> rule classification -> report -> CLI`

- Keep `model.py` limited to canonical data structures.
- Keep parsing independent of compatibility policy.
- Keep diffing independent of rule IDs, allowlists, configuration, and CLI
  formatting.
- Keep rule classification exhaustive: every emitted change must map to a
  documented rule or fail explicitly.
- Keep configuration validation in `config.py`, rendering in `report.py`, and
  orchestration in `cli.py`.
- Preserve deterministic ordering and output consumed by tests, goldens, CI, or
  downstream tooling.

## Shared working behavior

### Think before coding

- State material assumptions and uncertainties before implementation.
- Surface competing interpretations and meaningful tradeoffs.
- Prefer the simpler valid approach and challenge unnecessary complexity.
- When required evidence is missing, request the smallest relevant input
  instead of inventing behavior.

### Keep solutions simple

- Implement only the requested behavior.
- Do not add speculative abstractions, configurability, or features.
- Use direct, explicit code and actionable errors.
- Do not swallow exceptions or introduce silent fallback behavior.

### Make surgical changes

- Touch only files and lines required by the task.
- Do not refactor, reformat, rename, or remove unrelated code.
- Match established repository style.
- Remove only imports, variables, or functions made obsolete by the current
  change. Report unrelated dead code rather than deleting it.
- Every changed line must trace to the requested outcome.

### Work toward verifiable outcomes

- Define success in observable terms before implementing multi-step changes.
- Add a regression test for a bug before or with its fix.
- Add focused valid, invalid, and edge-case coverage for changed critical
  behavior.
- Continue until relevant checks pass or report the exact blocker and evidence.

## Coding and testing expectations

- Support the Python versions declared in `pyproject.toml` and CI.
- Preserve strict mypy typing and the configured Ruff rules.
- Treat CLI behavior, exit codes, JSON shapes, canonical model fields, and
  published rule IDs as compatibility-sensitive.
- Do not invent CMSIS-SVD semantics, schemas, dependencies, versions, secrets,
  endpoints, or fixture data.
- Parser changes require targeted tests and corpus validation.
- Diff changes require matching, ambiguity, ordering, and nested-element tests
  where relevant.
- Rule changes require classification tests and mutation-harness coverage.
- Config and CLI changes require invalid-input, error-message, and exit-code
  coverage.
- Do not regenerate goldens merely to make tests pass. Review and explain the
  semantic parser-output change first.

Run the CI checks before handing off code changes:

```sh
ruff check .
mypy
pytest
```

Install development dependencies with `python -m pip install -e ".[dev]"`.
Corpus-dependent tests require `python scripts/fetch_corpus.py`.

## Security and permission boundaries

- Treat SVD, TOML, CLI, and downloaded corpus content as untrusted input.
- Do not evaluate input as code, invoke shells with input-derived commands, or
  enable unsafe XML features.
- Never commit secrets, credentials, private keys, local settings, logs, or
  generated corpus data.
- Validate targets before destructive filesystem or Git operations.
- Do not discard changes created by another contributor or agent.

Obtain explicit maintainer permission before:

- Changing, removing, reusing, or re-severitying a published rule ID.
- Adding or removing runtime dependencies.
- Weakening strict typing, linting, tests, or CI checks.
- Changing the pinned corpus source or commit.
- Accepting regenerated golden output.
- Introducing a breaking CLI, exit-code, JSON, configuration, or model change.
- Publishing, releasing, pushing, merging, changing repository settings, or
  communicating externally on the maintainer's behalf.

## Keeping instructions aligned

Update this file when project structure, architectural ownership, supported
tooling, validation commands, security boundaries, or compatibility-sensitive
interfaces change. Keep tool-specific behavior in the appropriate adapter or
settings directory. Mirror a skill or subagent definition only when both tools
need the workflow; otherwise keep it with its owning tool.
