# Synthetic CMSIS-SVD data

This directory is a deterministic, network-free example dataset for regdrift.
It contains two revisions of the same imaginary accelerator:

- `chip_v1.svd` is the compatible baseline.
- `chip_v2.svd` moves a register, renames a field, renumbers an interrupt,
  changes write-one-to-clear to write-one-to-set, changes a reset value, and
  adds a result register.

```sh
regdrift check demo/chip_v1.svd demo/chip_v2.svd
```

Expected: exit code 1 with 4 breaking findings (RD001 moved register,
RD005 renamed field, RD015 renumbered interrupt, RD017 inverted write
semantics), 1 warning (RD010 reset value), 1 safe (RD020 added register).

Regenerate the directory with `python scripts/make_demo.py`. The
`tests/test_demo.py` checks fail if the committed data or this guide drifts
from the generator.
