# regdrift rules

Every change regdrift detects is classified by exactly one rule. Severities:

- **BREAKING** — existing code (hand-written drivers or code generated from
  the old SVD, e.g. CMSIS headers, svd2rust PACs) can silently misbehave or
  stop compiling. `regdrift check` fails on unallowed BREAKING findings.
- **WARNING** — hardware or documented behavior changed in a way that
  deserves human review, but well-formed existing code keeps working.
- **SAFE** — additive or cosmetic; no effect on existing code.

Findings suppressed via the allowlist (`.regdrift.toml` or `--allow`) are
reported as **ALLOWED** and never fail the check.

## BREAKING

| ID | Change | Rationale |
| --- | --- | --- |
| RD001 | Register or cluster address moved | Every existing read/write to the old address now touches the wrong register. |
| RD002 | Register or cluster removed | Code referencing it no longer compiles, or worse, keeps poking a dead address. |
| RD003 | Field bit position or width changed | Masks and shifts in existing binaries silently corrupt neighboring bits. |
| RD004 | Access capability removed (e.g. read-write → read-only) | Writers silently no-op (or readers fault), with no compile-time signal. |
| RD005 | Peripheral, register, or field renamed | Generated headers and PACs expose names; the old identifier vanishes from the API. |
| RD006 | Peripheral base address moved | Every register in the peripheral effectively moves at once. |
| RD007 | Peripheral removed | An entire address block of the API disappears. |
| RD008 | Field removed | Field-level accessors disappear from generated code; hand-rolled masks lose meaning. |
| RD009 | Register size changed | Load/store width no longer matches the hardware; reads can fault or truncate. |
| RD011 | Enumerated value changed (same name, different value) | The same symbolic name now writes different bits — code compiles unchanged and programs the wrong configuration. |
| RD013 | Enumerated value removed | Generated enum types (svd2rust and similar) lose the variant and stop compiling; C-header-only teams can downgrade via `[severity]`. |
| RD015 | Interrupt renumbered | The vector-table slot moves; old code installs its handler in the wrong entry and NVIC calls target the wrong line. |
| RD016 | Interrupt removed | Generated vector tables and IRQ enums lose the entry; handler registration silently dangles. |
| RD017 | Write semantics changed (modifiedWriteValues) | A oneToClear ↔ oneToSet flip inverts what writing 1 does; old flag-clearing code now sets the flag. |
| RD018 | Read side effect changed (readAction) | Reads that now clear (or stop clearing) state silently break polling and debug code. |

## WARNING

| ID | Change | Rationale |
| --- | --- | --- |
| RD010 | Reset value changed | Code relying on power-on defaults (skipping init) behaves differently; needs review, not a compile break. |
| RD012 | Reset mask changed | Which bits are defined at reset changed; affects reset-state assertions and test benches. |
| RD014 | Protection attribute changed | Secure/privileged access requirements shifted; existing code may need review under the new security model. |
| RD022 | Enumerated value default flag changed | Which entry is the documented catch-all shifted; review-worthy, but no name or value existing code uses has changed. |

## SAFE

| ID | Change | Rationale |
| --- | --- | --- |
| RD020 | Peripheral, cluster, register, field, or enumerated value added | Purely additive; existing code never sees it. |
| RD021 | Access capability added (e.g. read-only → read-write) | Everything that compiled and ran before still does; new capability is opt-in. |
| RD030 | Description-only change | Documentation text; no code or hardware impact. |

## Notes

- **Calibration.** Severities assume generated-code consumers (CMSIS C
  headers *and* svd2rust-style PACs). That is why renames and enum
  removals are BREAKING even though plain C-header users may not feel
  them — the gate fails closed. Teams with a narrower toolchain can
  re-rank any rule with a `[severity]` override in `.regdrift.toml`.
- Renames (RD005) are detected heuristically: an element that disappeared
  and one that appeared at the identical offset with identical structure.
  Findings state their basis in words — "exact structural match" when
  descriptions also match, otherwise "heuristic match: descriptions
  differ". Ambiguous candidates are reported as removed
  (RD002/RD007/RD008) + added (RD020) instead of guessed.
- Access changes compare capability sets: `read-only` = {read},
  `write-only`/`writeOnce` = {write}, `read-write`/`read-writeOnce` =
  {read, write}. Losing any capability is RD004; only gaining is RD021.
- A moved *field* is not a "move": bit layout changes report as one
  `[msb:lsb]` range change under RD003, because the failure mode is
  bit-level corruption, not a wrong address.

## What regdrift does not check (yet)

Honesty section: changes to these SVD constructs currently produce **no
findings**. If your workflow depends on one, treat regdrift as a partial
gate for it.

| Construct | Impact of a silent change | Status |
| --- | --- | --- |
| `dim` render style (`[%s]` array vs `%s` list) | Generated API shape flips between array and members — compile break. | [#26](https://github.com/Pranav-s79/regdrift/issues/26) |
| `headerStructName` | Renames the generated C struct type. | documented limitation |
| `writeConstraint` / `dataType` | svd2rust safe/unsafe writer API and value types shift. | documented limitation |
| `addressBlock` | MPU/region sizing implications; register semantics unaffected. | out of scope |
| `cpu` section (`nvicPrioBits`, endianness, …) | Priority encoding / layout assumptions; essentially never changes within a device. | out of scope |
| `alternateRegister` / `alternateGroup` / `alternatePeripheral` | Alternates are modeled as ordinary same-offset siblings; their linkage is not compared. | out of scope |
| `dimArrayIndex`, `vendorExtensions` | Cosmetic / vendor-private. | out of scope |
