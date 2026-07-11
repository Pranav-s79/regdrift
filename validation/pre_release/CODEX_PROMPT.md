# Prompt for Codex

You are working inside the `regdrift` repository. A pre-release validation bundle has been added at `validation/pre_release/`.

Read `README.md`, `RULES.md`, `docs/architecture.md`, `docs/json-schema.md`, and `validation/pre_release/README.md` first.

Then execute:

```bash
python -m pip install -e ".[dev]"
python validation/pre_release/setup_cases.py
python validation/pre_release/run_cases.py
ruff check .
mypy
pytest
```

Review `validation/pre_release/reports/latest.md` and `latest.json`.

Your job is to evaluate Regdrift, not to force the suite green. Specifically:

1. Confirm identity comparisons produce no findings.
2. Confirm each controlled mutation emits its expected rule and severity.
3. Confirm the warning case exits 0 by default and exits 1 under `--fail-on warning`.
4. Confirm malformed XML exits 2 without an uncaught traceback.
5. Inspect the genuine SAME70 revision comparison manually and classify questionable findings as likely correct, false positive, false negative, vendor noise, or a documented unsupported construct.
6. Confirm repeated JSON runs are byte-for-byte deterministic.
7. Do not change production rules or severities merely to satisfy a failing case.
8. For any suspected Regdrift defect, preserve the smallest reproducer and explain the expected versus actual behavior.
9. Do not publish a package, create a tag, or push remotely.

At the end, report:

- Every command run and its result.
- Cases passed and failed.
- Unexpected and missing rule IDs.
- Parser crashes, false greens, false positives, or nondeterminism.
- Findings attributable to documented limitations.
- Whether the project appears ready for a public alpha.
