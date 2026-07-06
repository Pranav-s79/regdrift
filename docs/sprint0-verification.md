# Sprint 0 verification (Task 5)

Run 2026-07-06 on Windows 11, Python 3.11.7, in a fresh `.venv`.

| Check | Result |
| --- | --- |
| `pip install -e ".[dev]"` | OK |
| `regdrift --version` | `regdrift, version 0.0.1` |
| `ruff check .` | All checks passed |
| `mypy` (strict) | no issues in 2 source files |
| `pytest` | 1 passed |
| `scripts/fetch_corpus.py` | 15/15 vendor SVDs fetched (~29 MiB), idempotent re-run hits cache |

Sprint 0 goal met: installable empty package, CI workflow in place,
real vendor SVD corpus fetchable with one command.
