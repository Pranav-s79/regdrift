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
| RD015 | Interrupt renumbered | The vector-table slot moves; old code installs its handler in the wrong entry and NVIC calls target the wrong line. |
| RD016 | Interrupt removed | Generated vector tables and IRQ enums lose the entry; handler registration silently dangles. |

## WARNING

| ID | Change | Rationale |
| --- | --- | --- |
| RD010 | Reset value changed | Code relying on power-on defaults (skipping init) behaves differently; needs review, not a compile break. |
| RD011 | Enumerated value meaning changed (value, default flag, or usage) | The same name now writes different bits — behavioral drift that tooling can't prove safe. |
| RD012 | Reset mask changed | Which bits are defined at reset changed; affects reset-state assertions and test benches. |
| RD013 | Enumerated value removed | Hardware behavior is unchanged, but generated enum types in some toolchains (e.g. svd2rust) lose a variant. |
| RD014 | Protection attribute changed | Secure/privileged access requirements shifted; existing code may need review under the new security model. |

## SAFE

| ID | Change | Rationale |
| --- | --- | --- |
| RD020 | Peripheral, cluster, register, field, or enumerated value added | Purely additive; existing code never sees it. |
| RD021 | Access capability added (e.g. read-only → read-write) | Everything that compiled and ran before still does; new capability is opt-in. |
| RD030 | Description-only change | Documentation text; no code or hardware impact. |

## Notes

- Renames (RD005) are detected heuristically: an element that disappeared
  and one that appeared at the identical offset with identical structure.
  Each rename finding carries a confidence (1.0 when descriptions also
  match, 0.8 otherwise). Ambiguous candidates are reported as
  removed (RD002/RD007/RD008) + added (RD020) instead of guessed.
- Access changes compare capability sets: `read-only` = {read},
  `write-only`/`writeOnce` = {write}, `read-write`/`read-writeOnce` =
  {read, write}. Losing any capability is RD004; only gaining is RD021.
- A moved *field* is not a "move": bit position changes are RD003, because
  the failure mode is bit-level corruption, not a wrong address.
