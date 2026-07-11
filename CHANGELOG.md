# Changelog

All notable changes to regdrift are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[PEP 440](https://peps.python.org/pep-0440/) / semver intent.

## [0.1.0a3] - 2026-07-11

GitHub Marketplace metadata fix. This release contains no parser, diff,
CLI, rule, reporting, or compatibility-engine behavior changes.

### Fixed
- GitHub Marketplace metadata validation: shortened the root `action.yml`
  description to a single sentence so it satisfies the Marketplace
  description character limit.

### Added
- A test that locks the root `action.yml` Marketplace metadata: the
  description must be present, non-empty, and at most 125 characters, and
  the action name, branding icon, and branding color must stay valid.

## [0.1.0a2] - 2026-07-11

Post-publication documentation and repository polish. This release contains
no changes to parser, diff, classification, rule, or compatibility behavior.

### Changed
- README and PyPI wording now describe the package as a published public
  alpha instead of an unreleased one.
- PyPI installation (`python -m pip install regdrift==0.1.0a2` /
  `pipx install regdrift==0.1.0a2`) is the primary documented installation
  path; source and editable development installs follow it.
- The README GitHub Action example references `Pranav-s79/regdrift@v0.1.0a2`.
- README badges now include the PyPI version, PyPI-derived Python support,
  and the license, alongside the existing CI and Action self-test badges.
- The maintainer release runbook reflects post-first-publication releases
  (one-time PyPI trusted-publisher and environment setup are recorded as
  done).

### Removed
- Internal agent and maintainer files from the public repository: duplicated
  session-handoff skill definitions, the one-shot Codex validation prompt,
  and sprint-0 planning records (name check, scaffold verification log).
  Local `.claude/`, `.codex/`, and `.agents/` state is now gitignored.

## [0.1.0a1] - 2026-07-11

First public alpha.

### Added
- CMSIS-SVD parser producing a fully resolved canonical model:
  register-properties cascade, `derivedFrom` at every level (forward
  references, cycle detection), `dim` array expansion, nested clusters,
  peripheral interrupts, `modifiedWriteValues`/`readAction`.
- Structural diff with three-phase matching (exact name, moved
  detection, rename heuristic with stated confidence basis).
- Published rulebook (RULES.md): 22 rules across BREAKING/WARNING/SAFE,
  including an explicit "What regdrift does not check (yet)" section.
- `regdrift check` CI gate: exit codes 0/1/2, configurable `--fail-on`
  threshold, and stdin support for the base file.
- Allowlist (`.regdrift.toml` `allow` + `--allow`) and `[severity]`
  re-ranking; allowed findings never fail the gate.
- Output formats: severity-ranked text report (SAFE rolled up behind
  `--all`), versioned JSON (`schema_version: 1`, documented in
  docs/json-schema.md), GitHub workflow annotations (capped).
- Composite GitHub Action (`uses: Pranav-s79/regdrift@<tag>`) with
  sticky PR comment, step summary, and CI self-test; `demo/` folder
  with a deliberately breaking revision pair.
- Test suite: per-feature unit tests, 15-file real-vendor corpus with
  datasheet spot assertions, mutation harness with a rule-coverage
  gate, golden snapshots, byte-mutation fuzzing, perf floor.

### Changed
- Configuration validation fails explicitly on unknown keys, unpublished rule
  IDs, malformed allow entries, and invalid severities.
- The composite action installs its checked-out source by default and passes
  user-controlled inputs to shell steps through quoted environment variables.
- GitHub workflow annotations escape SVD-derived content and filesystem paths.
- Unreadable SVD files produce the documented parser/tool error instead of an
  uncaught operating-system exception.
