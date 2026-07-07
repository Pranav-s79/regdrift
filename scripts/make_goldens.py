"""Regenerate golden snapshots of resolved corpus output.

Writes tests/golden/corpus_hashes.json (SHA-256 of the canonical JSON for
five corpus files) and tests/golden/ARM_Sample.json (full resolved model of
the smallest file, for readable diffs). Run after any intentional change to
parser output, and commit the result:

    python scripts/make_goldens.py
"""

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from regdrift.model import device_to_dict  # noqa: E402
from regdrift.parse import parse_svd  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "tests" / "corpus"
GOLDEN = ROOT / "tests" / "golden"

HASHED_FILES = [
    "ARM_Sample.svd",
    "CMSDK_CM3.svd",
    "STM32F103xx.svd",
    "nrf52.svd",
    "rp2040.svd",
]
FULL_JSON_FILE = "ARM_Sample.svd"


def canonical_json(svd_name: str) -> str:
    device = parse_svd(CORPUS / svd_name)
    return json.dumps(device_to_dict(device), indent=1)


def main() -> int:
    GOLDEN.mkdir(exist_ok=True)
    hashes = {
        name: hashlib.sha256(canonical_json(name).encode()).hexdigest()
        for name in HASHED_FILES
    }
    (GOLDEN / "corpus_hashes.json").write_text(json.dumps(hashes, indent=2) + "\n")
    (GOLDEN / "ARM_Sample.json").write_text(canonical_json(FULL_JSON_FILE) + "\n")
    for name, digest in hashes.items():
        print(f"{digest[:16]}  {name}")
    print(f"goldens written to {GOLDEN}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
