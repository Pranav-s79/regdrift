# Changelog

All notable changes to regdrift are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[PEP 440](https://peps.python.org/pep-0440/) / semver intent.

## [0.1.0a1] - unreleased

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
- `regdrift check` CI gate: exit codes 0/1/2, `--fail-on
  {breaking,warning}`, stdin support for the base file.
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
