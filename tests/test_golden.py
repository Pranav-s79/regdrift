"""Golden snapshots: resolved parser output is locked; drift must be intentional.

If a parser change intentionally alters resolved output, regenerate with
`python scripts/make_goldens.py` and commit the result.
"""

import hashlib
import json
from pathlib import Path

import pytest

from regdrift.model import device_to_dict
from regdrift.parse import parse_svd

GOLDEN = Path(__file__).parent / "golden"
CORPUS = Path(__file__).parent / "corpus"
HASHES: dict[str, str] = json.loads((GOLDEN / "corpus_hashes.json").read_text())

pytestmark = pytest.mark.skipif(
    not (CORPUS / "ARM_Sample.svd").exists(),
    reason="corpus not fetched; run scripts/fetch_corpus.py",
)


@pytest.mark.parametrize("name", sorted(HASHES))
def test_resolved_output_hash_locked(name: str) -> None:
    actual = json.dumps(device_to_dict(parse_svd(CORPUS / name)), indent=1)
    digest = hashlib.sha256(actual.encode()).hexdigest()
    assert digest == HASHES[name], (
        f"resolved output for {name} drifted from golden; if intentional, "
        "run scripts/make_goldens.py and commit the update"
    )


def test_arm_sample_full_golden() -> None:
    expected = json.loads((GOLDEN / "ARM_Sample.json").read_text())
    actual = device_to_dict(parse_svd(CORPUS / "ARM_Sample.svd"))
    assert actual == expected
