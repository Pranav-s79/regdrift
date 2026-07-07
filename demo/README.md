# regdrift demo

Two revisions of the same imaginary chip. `chip_v2.svd` sneaks in the
classic silent breaks: a moved register, a renamed field, a renumbered
interrupt, and a write-one-to-clear flag that became write-one-to-set.

```sh
regdrift check demo/chip_v1.svd demo/chip_v2.svd
```

Expected: exit code 1 with 4 breaking findings (RD001 moved register,
RD005 renamed field, RD015 renumbered interrupt, RD017 inverted write
semantics), 1 warning (RD010 reset value), 1 safe (RD020 added register).

Regenerate with `python scripts/make_demo.py` - `tests/test_demo.py`
fails CI if these files drift from the generator.
