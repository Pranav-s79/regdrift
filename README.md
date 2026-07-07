# regdrift

[![CI](https://github.com/Pranav-s79/regdrift/actions/workflows/ci.yml/badge.svg)](https://github.com/Pranav-s79/regdrift/actions/workflows/ci.yml)

Diff two CMSIS-SVD register map files and classify every change as
**BREAKING**, **WARNING**, or **SAFE** — like `buf breaking`, but for
hardware registers. Runs as a CLI and as a GitHub Action CI gate.

> Status: early scaffold (Sprint 0). Parser, diff engine, and rulebook land in
> the following sprints.

## Install

```sh
pip install regdrift
```

## Usage

```sh
regdrift --version
```

## Development

```sh
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"   # POSIX: .venv/bin/pip
python scripts/fetch_corpus.py          # pull vendor SVD test corpus
pytest
```

## License

Apache-2.0
