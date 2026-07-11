# Regdrift pre-release validation bundle

This directory builds and runs a reproducible set of real-vendor and controlled-mutation CMSIS-SVD comparisons before publishing Regdrift.

## What is included

- 5 identity comparisons on diverse and/or large devices.
- 1 genuine SAME70 revision comparison for human review.
- 9 controlled semantic mutations mapped to Regdrift rule IDs.
- 1 malformed-XML/tool-error case.
- Pinned source URLs, SHA-256 recording, readable case metadata, deterministic reruns, JSON output checks, and Markdown/JSON reports.

## Use

From the root of the Regdrift repository:

```bash
python -m pip install -e ".[dev]"
python validation/pre_release/setup_cases.py
python validation/pre_release/run_cases.py
```

The setup command downloads source SVDs from the pinned `cmsis-svd-data` commit and creates:

```text
validation/pre_release/cases/
├── 01_identity_arm_sample/
│   ├── old.svd
│   ├── new.svd
│   ├── case.json
│   └── case.yml
├── ...
└── 16_malformed_xml/
```

Reports are written to:

```text
validation/pre_release/reports/latest.json
validation/pre_release/reports/latest.md
```

## Important interpretation rule

Case `06_real_same70_revisions` is observational. Real vendor revisions may legitimately contain breaking changes, warnings, safe additions, unsupported constructs, or vendor-description noise. Review its output rather than forcing a preselected pass/fail result.

## Licensing

The upstream aggregation states that files under `data/` use vendor-specific licensing. Do not commit or redistribute downloaded SVD files until the applicable vendor/file notices have been reviewed. The setup script stores them under `_sources/` and the case directories; the repository `.gitignore` excludes those downloads and the generated `reports/`, so only the harness (scripts, case metadata, and the source lock file) is tracked.
