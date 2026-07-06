"""Fetch the vendor SVD test corpus into tests/corpus/.

Downloads ~15 representative real-world SVD files from the public
cmsis-svd-data repository (https://github.com/cmsis-svd/cmsis-svd-data),
pinned to a specific commit so test assertions stay reproducible.

The corpus is gitignored; run this script locally once, and CI runs it
(cached) on every build. Idempotent: existing non-empty files are skipped.

Usage:
    python scripts/fetch_corpus.py
"""

import sys
import urllib.error
import urllib.request
from pathlib import Path

# Pinned cmsis-svd-data commit (main as of 2025-01-05).
REF = "c65f8551e57c770344d229dcaa0bf838fa29aff4"
BASE_URL = f"https://raw.githubusercontent.com/cmsis-svd/cmsis-svd-data/{REF}/data"

# vendor-dir/filename, exactly as they appear upstream.
CORPUS = [
    # ARM's own sample devices: small, exercise derivedFrom and dim arrays.
    "ARM_SAMPLE/ARM_Sample.svd",
    "ARM_SAMPLE/CMSDK_CM3.svd",
    # STM32: several families, including one huge H7 file (multi-MB).
    "STMicro/STM32F030.svd",
    "STMicro/STM32F103xx.svd",
    "STMicro/STM32F407.svd",
    "STMicro/STM32L4x6.svd",
    "STMicro/STM32H743x.svd",
    # Nordic nRF5x.
    "Nordic/nrf51.svd",
    "Nordic/nrf52.svd",
    "Nordic/nrf52840.svd",
    # NXP: classic LPC, Kinetis, i.MX RT.
    "NXP/LPC176x5x_v0.2.svd",
    "NXP/MK64F12.svd",
    "NXP/MIMXRT1011.svd",
    # A small Atmel part.
    "Atmel/ATSAMD21E15L.svd",
    # Raspberry Pi RP2040 (heavy cluster/dim usage).
    "RaspberryPi/rp2040.svd",
]

CORPUS_DIR = Path(__file__).resolve().parent.parent / "tests" / "corpus"


def fetch(rel_path: str) -> str:
    """Download one corpus file. Returns 'fetched' or 'cached'."""
    dest = CORPUS_DIR / Path(rel_path).name
    if dest.exists() and dest.stat().st_size > 0:
        return "cached"
    url = f"{BASE_URL}/{rel_path}"
    with urllib.request.urlopen(url, timeout=60) as resp:  # noqa: S310
        dest.write_bytes(resp.read())
    return "fetched"


def main() -> int:
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    failures = []
    for rel_path in CORPUS:
        try:
            status = fetch(rel_path)
        except (urllib.error.URLError, OSError) as exc:
            failures.append(rel_path)
            print(f"  FAIL    {rel_path}: {exc}", file=sys.stderr)
            continue
        size_kib = (CORPUS_DIR / Path(rel_path).name).stat().st_size // 1024
        print(f"  {status:<7} {rel_path} ({size_kib} KiB)")
    if failures:
        print(f"\n{len(failures)}/{len(CORPUS)} files failed to download.", file=sys.stderr)
        return 1
    print(f"\nCorpus ready: {len(CORPUS)} files in {CORPUS_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
