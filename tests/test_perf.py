"""Performance floor: the biggest STM32 corpus file diffs quickly.

Local runs finish in ~1-2 s; the bound is generous so CI runners never
flake, while still catching an accidental complexity regression
(e.g. quadratic matching).
"""

import time
from pathlib import Path

import pytest

from regdrift.diff import diff_devices
from regdrift.parse import parse_svd

H7 = Path(__file__).parent / "corpus" / "STM32H743x.svd"

pytestmark = pytest.mark.skipif(
    not H7.exists(), reason="corpus not fetched; run scripts/fetch_corpus.py"
)


def test_h7_parse_and_diff_under_bound() -> None:
    start = time.perf_counter()
    old = parse_svd(H7)
    new = parse_svd(H7)
    changes = diff_devices(old, new)
    elapsed = time.perf_counter() - start
    assert changes == []
    assert elapsed < 10.0, f"H7 parse+diff took {elapsed:.1f}s (bound 10s, typical ~1s)"
