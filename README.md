# regdrift

[![CI](https://github.com/Pranav-s79/regdrift/actions/workflows/ci.yml/badge.svg)](https://github.com/Pranav-s79/regdrift/actions/workflows/ci.yml)

Silicon revisions move registers. Here's how that plays out: in week 3 the
vendor ships rev B of the SVD and one register nudges from offset 0x40 to
0x44 — your driver still compiles, CI stays green, and every write lands on
the wrong register. In week 6 someone finds it with a logic analyzer.
**regdrift is the CI gate that catches it in the pull request instead.**

Like `buf breaking`, but for hardware register maps: diff two CMSIS-SVD
files, classify every change as BREAKING / WARNING / SAFE against a
published rulebook, and fail the build on unallowed breakage.

## Install

```sh
pip install regdrift
```

```sh
pipx install regdrift
```

## 30 seconds

```sh
regdrift check old.svd new.svd                       # human report
regdrift check old.svd new.svd --format json          # for tooling
git show origin/main:chip.svd | regdrift check - chip.svd   # against the base branch
```

```
BREAKING (1)
  RD007  peripheral SPI0 removed

WARNING (1)
  RD010  register UART0.DATA reset value changed 0x0 -> 0x5

ALLOWED (1)
  RD001  register UART0.CTRL address moved 0x0 -> 0x4

2 safe (1 added, 1 description-only) - use --all to list
1 breaking, 1 warning, 2 safe, 1 allowed
```

Exit `0` = clean or allowed-only, `1` = unallowed breakage (`--fail-on
warning` tightens this), `2` = tool error.

## The rulebook

Every finding maps to one rule ID documented with a one-sentence rationale
in [RULES.md](RULES.md): 14 BREAKING, 4 WARNING, 3 SAFE. RULES.md also
lists what regdrift does **not** check yet — read it before trusting the
gate. Acknowledge an intentional break instead of disabling the gate:
`.regdrift.toml` takes `allow = ["RD001:UART0.CTRL"]` to suppress a specific
finding. A `[severity]` table re-ranks a whole rule (e.g. downgrade RD013
if your toolchain never generates enum types).

## In CI

```yaml
- uses: actions/checkout@v4
  with: { fetch-depth: 0 }
- run: pip install regdrift
- run: |
    git show "origin/${{ github.base_ref }}:chip.svd" > /tmp/base.svd
    regdrift check /tmp/base.svd chip.svd --format github
```

Or use the bundled action - same check, plus annotations and a sticky PR comment:

```yaml
- uses: actions/checkout@v4
  with: { fetch-depth: 0 }
- uses: Pranav-s79/regdrift@main
  with:
    svd-path: chip.svd
```

Pin `@main` to a release tag once v0.1.0-alpha ships. Requires `fetch-depth: 0` and, for the comment, `permissions: pull-requests: write`.

## Related tools

[svdtools](https://github.com/rust-embedded/svdtools) `htmlcompare` renders
human-readable comparisons of SVD files, and ARM's SVDConv validates single
files. regdrift does neither of those jobs — it is the CI gate: a
classified breaking-change verdict with exit codes, an allowlist, and a
rulebook you can argue with. Use them together.

## Status

Alpha. The parser resolves the full public cmsis-svd-data corpus (STM32,
nRF52, Kinetis, LPC, SAMD21, RP2040, ...), every rule is covered by a
mutation-test harness against real vendor files, and identity diffs are
empty corpus-wide. It has not yet survived contact with other people's
workflows — that is what this release is for. File issues generously.

## Development

```sh
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"   # POSIX: .venv/bin/pip
python scripts/fetch_corpus.py          # pull vendor SVD test corpus
pytest
```

## License

Apache-2.0
