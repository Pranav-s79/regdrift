"""Fuzz: corrupted SVD input must fail with a clean SvdParseError, never a crash.

The contract under fuzz is binary: either the file still parses, or the
parser raises SvdParseError (with a location). Any other exception type is
a bug — a traceback a CI user would see with no idea where to look.
"""

import random
from pathlib import Path

import pytest

from regdrift.parse import SvdParseError, parse_svd

CORPUS = Path(__file__).parent / "corpus"
SEED_FILE = CORPUS / "ARM_Sample.svd"

pytestmark = pytest.mark.skipif(
    not SEED_FILE.exists(), reason="corpus not fetched; run scripts/fetch_corpus.py"
)


def _must_parse_or_fail_cleanly(data: bytes, tmp_path: Path, name: str) -> None:
    target = tmp_path / f"{name}.svd"
    target.write_bytes(data)
    try:
        parse_svd(target)
    except SvdParseError:
        pass  # clean, located failure is exactly the contract


def test_random_byte_mutations(tmp_path: Path) -> None:
    data = SEED_FILE.read_bytes()
    rng = random.Random(0xE1EC7)
    for i in range(200):
        mutated = bytearray(data)
        for _ in range(rng.randint(1, 8)):
            mutated[rng.randrange(len(mutated))] = rng.randrange(256)
        _must_parse_or_fail_cleanly(bytes(mutated), tmp_path, f"mut{i}")


def test_truncations(tmp_path: Path) -> None:
    data = SEED_FILE.read_bytes()
    for i in range(1, 20):
        _must_parse_or_fail_cleanly(data[: len(data) * i // 20], tmp_path, f"trunc{i}")


def test_empty_and_garbage_files(tmp_path: Path) -> None:
    for name, data in [
        ("empty", b""),
        ("garbage", b"\x00\xff\xfe not xml at all"),
        ("wrong_doc", b"<html><body>hi</body></html>"),
    ]:
        target = tmp_path / f"{name}.svd"
        target.write_bytes(data)
        with pytest.raises(SvdParseError):
            parse_svd(target)
