# Contributing to regdrift

Thanks for your interest. regdrift is an alpha compatibility tool, so focused
issues and small, evidence-backed pull requests are especially valuable.

## Dev setup

```sh
git clone https://github.com/Pranav-s79/regdrift
cd regdrift
python -m venv .venv
python -m pip install -e ".[dev]"
python scripts/fetch_corpus.py           # real vendor SVD test corpus (~29 MB, gitignored)
```

## Before you push

All three must be green (CI enforces them on 3.11 and 3.12):

```sh
ruff check .
mypy
pytest
```

## Ground rules

- Runtime dependencies stay near zero (click only) — parsing is stdlib
  `xml.etree` on purpose.
- Every classification rule lives in [RULES.md](RULES.md) with an ID and a
  one-sentence rationale, and must be covered by the mutation harness
  (`tests/test_mutations.py`) — CI fails otherwise.
- New parser features need a targeted unit test **and** must keep the whole
  vendor corpus parsing clean (`tests/test_corpus.py`).

## Filing issues

A failing `.svd` snippet (or a pointer to a public vendor file) plus the
command you ran is the perfect bug report.
