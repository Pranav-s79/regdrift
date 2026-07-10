# regdrift JSON output schema

`regdrift check OLD NEW --format json` emits one JSON document on stdout.
`schema_version` is bumped whenever a key is renamed, removed, or changes
meaning; additions of new keys are not breaking. Current version: **1**.

| Key | Type | Meaning |
| --- | --- | --- |
| `schema_version` | int | Always `1` for this document shape. |
| `regdrift_version` | string | The regdrift release that produced the document. |
| `old.file` / `new.file` | string | The CLI path labels (`-` for stdin); filesystem paths use the platform's native separators. |
| `old.device` / `new.device` | string | The `<name>` of each parsed device. |
| `summary.breaking` / `.warning` / `.safe` | int | Counts of unallowed findings per classified severity. |
| `summary.allowed` | int | Findings suppressed by the allowlist (any severity). |
| `passed` | bool | `false` iff the run exits 1 under the given `--fail-on`. |
| `findings[]` | array | Every finding, in diff emission order (allowed ones included). |
| `findings[].rule` | string | Rule ID, e.g. `RD001` — see RULES.md. |
| `findings[].severity` | string | Classified severity (`BREAKING`/`WARNING`/`SAFE`) — never `ALLOWED`; check `allowed` instead. |
| `findings[].allowed` | bool | `true` when suppressed by `.regdrift.toml` or `--allow`. |
| `findings[].element` | string | `peripheral`, `cluster`, `register`, `field`, `enum`, or `interrupt`. |
| `findings[].path` | string | Dotted element path, e.g. `UART0.CTRL.EN`. |
| `findings[].kind` | string | `added`, `removed`, `moved`, `renamed`, or `modified`. |
| `findings[].attribute` | string\|null | Which attribute changed (`null` for added/removed). |
| `findings[].before` / `.after` | string\|int\|bool\|null | Old/new value. Addresses, reset values, and masks are canonical hex **strings** (`"0x40010800"`) so 64-bit values survive JavaScript consumers. |
| `findings[].confidence` | float\|null | Rename-heuristic confidence (`1.0` or `0.8`), else `null`. |
| `findings[].message` | string | Pre-rendered human sentence; do not re-derive. |
