"""Diff invariants over the real vendor corpus.

Synthetic per-change-kind pairs live in test_diff_matching.py and
test_diff_modified.py; this module checks the corpus-wide invariants.
The corpus pins single versions of each vendor file (no two revisions of
the same chip), so the real-world exercise diffs two related chips from
the same vendor family instead.
"""

from pathlib import Path

import pytest

from regdrift.diff import diff_devices
from regdrift.parse import parse_svd

CORPUS = Path(__file__).parent / "corpus"
CORPUS_FILES = sorted(CORPUS.glob("*.svd"))

pytestmark = pytest.mark.skipif(
    not CORPUS_FILES, reason="corpus not fetched; run scripts/fetch_corpus.py"
)


@pytest.mark.parametrize("svd", CORPUS_FILES, ids=lambda p: p.name)
def test_identity_diff_is_empty(svd: Path) -> None:
    device = parse_svd(svd)
    assert diff_devices(device, device) == []


@pytest.mark.parametrize("svd", CORPUS_FILES, ids=lambda p: p.name)
def test_identity_diff_of_reparsed_file_is_empty(svd: Path) -> None:
    # Two independent parses of the same file must produce equal models.
    assert diff_devices(parse_svd(svd), parse_svd(svd)) == []


def test_real_vendor_family_diff_smoke() -> None:
    """nrf52 -> nrf52840: a real family evolution flows through the engine."""
    old = parse_svd(CORPUS / "nrf52.svd")
    new = parse_svd(CORPUS / "nrf52840.svd")
    changes = diff_devices(old, new)
    kinds = {c.kind for c in changes}
    # The 52840 added peripherals (e.g. USBD, CRYPTOCELL) and kept most of
    # the 52832's map, so we expect a rich but sane change list.
    assert "added" in kinds
    assert any(c.kind == "added" and c.path == "USBD" for c in changes)
    assert len(changes) > 100
    # every change carries a well-formed path and kind
    assert all(c.path and c.kind in {"added", "removed", "moved", "renamed", "modified"}
               for c in changes)
