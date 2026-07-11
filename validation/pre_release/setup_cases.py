#!/usr/bin/env python3
"""Download pinned CMSIS-SVD sources and build pre-release validation cases.

Run from the regdrift repository root:
    python validation/pre_release/setup_cases.py

The script uses only the Python standard library. Vendor SVD files are downloaded
from a pinned cmsis-svd-data commit, checksummed, and copied into isolated cases.
Controlled mutations are applied structurally with ElementTree rather than blind
string replacement.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

REF = "c65f8551e57c770344d229dcaa0bf838fa29aff4"
BASE_URL = f"https://raw.githubusercontent.com/cmsis-svd/cmsis-svd-data/{REF}/data"
HERE = Path(__file__).resolve().parent
SOURCE_DIR = HERE / "_sources"
CASES_DIR = HERE / "cases"
LOCK_PATH = HERE / "sources.lock.json"


@dataclass(frozen=True)
class Source:
    key: str
    vendor: str
    device: str
    path: str
    license_note: str

    @property
    def url(self) -> str:
        return f"{BASE_URL}/{self.path}"

    @property
    def filename(self) -> str:
        return Path(self.path).name


_ATMEL_LICENSE_NOTE = (
    "The Atmel repository README identifies current DFP files as Apache-2.0; "
    "verify the file header."
)

SOURCES: tuple[Source, ...] = (
    Source(
        "arm_sample", "Arm", "ARM Sample", "ARM_SAMPLE/ARM_Sample.svd",
        "Review ARM_SAMPLE vendor notices before redistribution.",
    ),
    Source(
        "stm32f407", "STMicroelectronics", "STM32F407", "STMicro/STM32F407.svd",
        "Review data/STMicro licensing before redistribution.",
    ),
    Source(
        "stm32h743", "STMicroelectronics", "STM32H743x", "STMicro/STM32H743x.svd",
        "Review data/STMicro licensing before redistribution.",
    ),
    Source(
        "nrf52840", "Nordic Semiconductor", "nRF52840", "Nordic/nrf52840.svd",
        "Review data/Nordic licensing before redistribution.",
    ),
    Source(
        "lpc176x5x", "NXP", "LPC176x5x", "NXP/LPC176x5x_v0.2.svd",
        "Review data/NXP licensing before redistribution.",
    ),
    Source(
        "mimxrt1011", "NXP", "MIMXRT1011", "NXP/MIMXRT1011.svd",
        "Review data/NXP licensing before redistribution.",
    ),
    Source(
        "rp2040", "Raspberry Pi", "RP2040", "RaspberryPi/rp2040.svd",
        "Review data/RaspberryPi licensing before redistribution.",
    ),
    Source(
        "saml11", "Microchip/Atmel", "ATSAML11E16A", "Atmel/ATSAML11E16A.svd",
        _ATMEL_LICENSE_NOTE,
    ),
    Source(
        "samd51", "Microchip/Atmel", "ATSAMD51J20A", "Atmel/ATSAMD51J20A.svd",
        _ATMEL_LICENSE_NOTE,
    ),
    Source(
        "same70a", "Microchip/Atmel", "ATSAME70Q21 Rev A", "Atmel/ATSAME70Q21.svd",
        "Deprecated revision; verify the file header and vendor notice.",
    ),
    Source(
        "same70b", "Microchip/Atmel", "ATSAME70Q21 Rev B", "Atmel/ATSAME70Q21B.svd",
        _ATMEL_LICENSE_NOTE,
    ),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parser() -> ET.XMLParser:
    return ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))


def parse_xml(path: Path) -> ET.ElementTree:
    return ET.parse(path, parser=parser())


def local_name(tag: object) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


def namespace_of(tag: str) -> str:
    if tag.startswith("{"):
        return tag.split("}", 1)[0] + "}"
    return ""


def descendants(root: ET.Element, name: str) -> Iterable[ET.Element]:
    for elem in root.iter():
        if local_name(elem.tag) == name:
            yield elem


def direct_child(elem: ET.Element, name: str) -> ET.Element | None:
    return next((child for child in list(elem) if local_name(child.tag) == name), None)


def child_text(elem: ET.Element, name: str) -> str | None:
    child = direct_child(elem, name)
    return child.text.strip() if child is not None and child.text else None


def ensure_child(elem: ET.Element, name: str, text: str) -> ET.Element:
    child = direct_child(elem, name)
    if child is None:
        child = ET.Element(namespace_of(str(elem.tag)) + name)
        # Put the new element before fields when possible; CMSIS-SVD ordering
        # matters to some validators.
        insert_at = len(elem)
        for index, existing in enumerate(list(elem)):
            if local_name(existing.tag) in {"fields", "dim", "dimIncrement", "dimIndex"}:
                insert_at = index
                break
        elem.insert(insert_at, child)
    child.text = text
    return child


def parse_int(text: str) -> int:
    value = text.strip().replace("_", "")
    if value.startswith("#"):
        value = "0b" + value[1:]
    return int(value, 0)


def format_like(original: str, value: int) -> str:
    stripped = original.strip()
    if stripped.lower().startswith("0x"):
        width = max(1, len(stripped) - 2)
        return f"0x{value:0{width}X}"
    if stripped.lower().startswith("0b"):
        width = max(1, len(stripped) - 2)
        return f"0b{value:0{width}b}"
    if stripped.startswith("#"):
        width = max(1, len(stripped) - 1)
        return "#" + f"{value:0{width}b}"
    return str(value)


def write_tree(tree: ET.ElementTree, destination: Path) -> None:
    tree.write(destination, encoding="utf-8", xml_declaration=True)
    # Confirm the produced XML is parseable before accepting it.
    ET.parse(destination)


def download(source: Source, force: bool = False) -> dict[str, object]:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    destination = SOURCE_DIR / source.filename
    if force and destination.exists():
        destination.unlink()
    if not destination.exists() or destination.stat().st_size == 0:
        request = urllib.request.Request(
            source.url, headers={"User-Agent": "regdrift-pre-release-validation/1"}
        )
        try:
            with (
                urllib.request.urlopen(request, timeout=120) as response,
                destination.open("wb") as output,
            ):
                shutil.copyfileobj(response, output)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            destination.unlink(missing_ok=True)
            raise RuntimeError(f"Failed to download {source.url}: {exc}") from exc
    if destination.stat().st_size == 0:
        raise RuntimeError(f"Downloaded file is empty: {destination}")
    try:
        parse_xml(destination)
    except ET.ParseError as exc:
        raise RuntimeError(f"Downloaded file is not valid XML: {destination}: {exc}") from exc
    return {
        "key": source.key,
        "vendor": source.vendor,
        "device": source.device,
        "source_path": source.path,
        "source_url": source.url,
        "source_commit": REF,
        "filename": source.filename,
        "size_bytes": destination.stat().st_size,
        "sha256": sha256(destination),
        "license_note": source.license_note,
    }


def load_sources(force: bool = False) -> tuple[dict[str, Path], list[dict[str, object]]]:
    paths: dict[str, Path] = {}
    records: list[dict[str, object]] = []
    for source in SOURCES:
        print(f"Downloading/verifying {source.vendor} {source.device}...")
        record = download(source, force=force)
        paths[source.key] = SOURCE_DIR / source.filename
        records.append(record)
    lock_document = {"schema_version": 1, "sources": records}
    LOCK_PATH.write_text(json.dumps(lock_document, indent=2) + "\n", encoding="utf-8")
    return paths, records


def first_named(
    root: ET.Element, element_name: str, *, require: tuple[str, ...] = ()
) -> ET.Element:
    for elem in descendants(root, element_name):
        if elem.get("derivedFrom"):
            continue
        if child_text(elem, "name") is None:
            continue
        if all(direct_child(elem, required) is not None for required in require):
            return elem
    raise RuntimeError(f"No suitable <{element_name}> found with children {require}")


def parent_map(root: ET.Element) -> dict[ET.Element, ET.Element]:
    return {child: parent for parent in root.iter() for child in list(parent)}


def mutation_register_moved(path: Path) -> dict[str, str]:
    tree = parse_xml(path)
    register = first_named(tree.getroot(), "register", require=("addressOffset",))
    offset = direct_child(register, "addressOffset")
    assert offset is not None and offset.text
    before = offset.text.strip()
    after = format_like(before, parse_int(before) + 4)
    offset.text = after
    write_tree(tree, path)
    return {
        "target_path": child_text(register, "name") or "unknown",
        "before": before,
        "after": after,
    }


def mutation_register_removed(path: Path) -> dict[str, str]:
    tree = parse_xml(path)
    root = tree.getroot()
    register = first_named(root, "register")
    name = child_text(register, "name") or "unknown"
    parents = parent_map(root)
    parent = parents.get(register)
    if parent is None:
        raise RuntimeError("Could not locate register parent")
    parent.remove(register)
    write_tree(tree, path)
    return {"target_path": name, "before": "present", "after": "removed"}


def mutation_field_layout(path: Path) -> dict[str, str]:
    tree = parse_xml(path)
    root = tree.getroot()
    for field in descendants(root, "field"):
        if field.get("derivedFrom") or child_text(field, "name") is None:
            continue
        bit_offset = direct_child(field, "bitOffset")
        if bit_offset is not None and bit_offset.text:
            before = bit_offset.text.strip()
            after = format_like(before, parse_int(before) + 1)
            bit_offset.text = after
            write_tree(tree, path)
            return {
                "target_path": child_text(field, "name") or "unknown",
                "before": before,
                "after": after,
            }
        bit_range = direct_child(field, "bitRange")
        if bit_range is not None and bit_range.text:
            before = bit_range.text.strip()
            raw = before.strip("[]")
            msb_s, lsb_s = raw.split(":", 1)
            msb, lsb = int(msb_s), int(lsb_s)
            after = f"[{msb + 1}:{lsb + 1}]"
            bit_range.text = after
            write_tree(tree, path)
            return {
                "target_path": child_text(field, "name") or "unknown",
                "before": before,
                "after": after,
            }
        lsb_elem, msb_elem = direct_child(field, "lsb"), direct_child(field, "msb")
        if lsb_elem is not None and msb_elem is not None and lsb_elem.text and msb_elem.text:
            before = f"[{msb_elem.text.strip()}:{lsb_elem.text.strip()}]"
            lsb_elem.text = str(int(lsb_elem.text.strip()) + 1)
            msb_elem.text = str(int(msb_elem.text.strip()) + 1)
            after = f"[{msb_elem.text}:{lsb_elem.text}]"
            write_tree(tree, path)
            return {
                "target_path": child_text(field, "name") or "unknown",
                "before": before,
                "after": after,
            }
    raise RuntimeError("No field with an editable bit layout found")


def mutation_field_renamed(path: Path) -> dict[str, str]:
    tree = parse_xml(path)
    field = first_named(tree.getroot(), "field")
    name = direct_child(field, "name")
    assert name is not None and name.text
    before = name.text.strip()
    after = before + "_REGDRIFT_RENAMED"
    name.text = after
    write_tree(tree, path)
    return {"target_path": after, "before": before, "after": after}


def mutation_reset_value(path: Path) -> dict[str, str]:
    tree = parse_xml(path)
    root = tree.getroot()
    for register in descendants(root, "register"):
        if register.get("derivedFrom") or child_text(register, "name") is None:
            continue
        reset = direct_child(register, "resetValue")
        if reset is not None and reset.text:
            before = reset.text.strip()
            after = format_like(before, parse_int(before) ^ 1)
            reset.text = after
            write_tree(tree, path)
            return {
                "target_path": child_text(register, "name") or "unknown",
                "before": before,
                "after": after,
            }
    register = first_named(root, "register")
    before = "inherited/unspecified"
    after = "0x1"
    ensure_child(register, "resetValue", after)
    write_tree(tree, path)
    return {
        "target_path": child_text(register, "name") or "unknown",
        "before": before,
        "after": after,
    }


def mutation_interrupt(path: Path) -> dict[str, str]:
    tree = parse_xml(path)
    interrupt = first_named(tree.getroot(), "interrupt", require=("value",))
    value = direct_child(interrupt, "value")
    assert value is not None and value.text
    before = value.text.strip()
    after = str(parse_int(before) + 1)
    value.text = after
    write_tree(tree, path)
    return {
        "target_path": child_text(interrupt, "name") or "unknown",
        "before": before,
        "after": after,
    }


def mutation_write_semantics(path: Path) -> dict[str, str]:
    tree = parse_xml(path)
    root = tree.getroot()
    for elem in root.iter():
        semantics = direct_child(elem, "modifiedWriteValues")
        if semantics is not None and semantics.text:
            before = semantics.text.strip()
            after = "oneToSet" if before != "oneToSet" else "oneToClear"
            semantics.text = after
            write_tree(tree, path)
            return {
                "target_path": child_text(elem, "name") or local_name(elem.tag),
                "before": before,
                "after": after,
            }
    field = first_named(root, "field")
    before, after = "modify/default", "oneToClear"
    ensure_child(field, "modifiedWriteValues", after)
    write_tree(tree, path)
    return {"target_path": child_text(field, "name") or "unknown", "before": before, "after": after}


def mutation_register_added(path: Path) -> dict[str, str]:
    tree = parse_xml(path)
    root = tree.getroot()
    original = first_named(root, "register", require=("addressOffset",))
    parents = parent_map(root)
    parent = parents.get(original)
    if parent is None:
        raise RuntimeError("Could not locate register parent")
    new_register = copy.deepcopy(original)
    name_elem = direct_child(new_register, "name")
    offset_elem = direct_child(new_register, "addressOffset")
    assert name_elem is not None and name_elem.text and offset_elem is not None and offset_elem.text
    original_name = name_elem.text.strip()
    original_offset = offset_elem.text.strip()
    name_elem.text = original_name + "_REGDRIFT_ADDED"
    offset_elem.text = format_like(original_offset, parse_int(original_offset) + 0x1000)
    description = direct_child(new_register, "description")
    if description is not None:
        description.text = "Synthetic additive register for pre-release validation"
    parent.append(new_register)
    write_tree(tree, path)
    return {
        "target_path": name_elem.text,
        "before": "absent",
        "after": f"added at {offset_elem.text}",
    }


def mutation_description(path: Path) -> dict[str, str]:
    tree = parse_xml(path)
    register = first_named(tree.getroot(), "register")
    description = direct_child(register, "description")
    before = description.text.strip() if description is not None and description.text else ""
    after = (before + " [regdrift pre-release description-only mutation]").strip()
    ensure_child(register, "description", after)
    write_tree(tree, path)
    return {
        "target_path": child_text(register, "name") or "unknown",
        "before": before,
        "after": after,
    }


def mutation_malformed(path: Path) -> dict[str, str]:
    data = path.read_bytes()
    if len(data) < 64:
        raise RuntimeError("Source is unexpectedly small")
    path.write_bytes(data[:-37])
    try:
        ET.parse(path)
    except ET.ParseError:
        return {
            "target_path": "XML document",
            "before": "well-formed",
            "after": "truncated/malformed",
        }
    raise RuntimeError("Malformed-XML mutation unexpectedly remained parseable")


Mutation = Callable[[Path], dict[str, str]]


def yaml_scalar(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        if not value:
            return "[]"
        return "[" + ", ".join(json.dumps(str(item)) for item in value) + "]"
    return json.dumps(str(value))


def write_metadata(case_dir: Path, metadata: dict[str, object]) -> None:
    (case_dir / "case.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    ordered = [
        "name", "category", "vendor", "device", "old_source_url", "new_source_url",
        "source_commit", "mutation", "target_path", "before", "after",
        "expected_exit_code", "expected_rules", "expected_severities", "strict", "notes",
    ]
    lines = [f"{key}: {yaml_scalar(metadata.get(key))}" for key in ordered]
    (case_dir / "case.yml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_case(
    number: int,
    slug: str,
    old_source: Source,
    source_paths: dict[str, Path],
    *,
    new_source: Source | None = None,
    mutation_name: str = "identity",
    mutation: Mutation | None = None,
    expected_exit_code: int | None = 0,
    expected_rules: list[str] | None = None,
    expected_severities: list[str] | None = None,
    strict: bool = True,
    notes: str = "",
) -> None:
    case_dir = CASES_DIR / f"{number:02d}_{slug}"
    if case_dir.exists():
        shutil.rmtree(case_dir)
    case_dir.mkdir(parents=True)
    old_path = case_dir / "old.svd"
    new_path = case_dir / "new.svd"
    shutil.copy2(source_paths[old_source.key], old_path)
    selected_new = new_source or old_source
    shutil.copy2(source_paths[selected_new.key], new_path)

    details = {"target_path": "none", "before": "identical", "after": "identical"}
    if mutation is not None:
        details = mutation(new_path)

    if not strict:
        category = "observational_real_revision"
    elif mutation is None and new_source is None:
        category = "identity"
    else:
        category = "controlled_mutation"
    if new_source is None:
        device = old_source.device
    else:
        device = f"{old_source.device} -> {new_source.device}"

    metadata: dict[str, object] = {
        "name": slug.replace("_", " "),
        "category": category,
        "vendor": old_source.vendor,
        "device": device,
        "old_source_url": old_source.url,
        "new_source_url": selected_new.url,
        "source_commit": REF,
        "old_sha256": sha256(old_path),
        "new_sha256": sha256(new_path),
        "mutation": mutation_name,
        "target_path": details["target_path"],
        "before": details["before"],
        "after": details["after"],
        "expected_exit_code": expected_exit_code,
        "expected_rules": expected_rules or [],
        "expected_severities": expected_severities or [],
        "strict": strict,
        "notes": notes,
    }
    write_metadata(case_dir, metadata)


def build_all(source_paths: dict[str, Path]) -> None:
    CASES_DIR.mkdir(parents=True, exist_ok=True)
    for child in CASES_DIR.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        elif child.name != ".gitkeep":
            child.unlink()
    by_key = {source.key: source for source in SOURCES}
    build_case(1, "identity_arm_sample", by_key["arm_sample"], source_paths)
    build_case(2, "identity_stm32h7", by_key["stm32h743"], source_paths)
    build_case(3, "identity_nrf52840", by_key["nrf52840"], source_paths)
    build_case(4, "identity_imxrt", by_key["mimxrt1011"], source_paths)
    build_case(5, "identity_rp2040", by_key["rp2040"], source_paths)
    build_case(
        6, "real_same70_revisions", by_key["same70a"], source_paths,
        new_source=by_key["same70b"], mutation_name="vendor_revision_pair",
        expected_exit_code=None, strict=False,
        notes=(
            "Observational real-world comparison. "
            "Record findings; do not hardcode pass/fail before review."
        ),
    )
    build_case(
        7, "register_moved", by_key["saml11"], source_paths,
        mutation_name="addressOffset + 4", mutation=mutation_register_moved,
        expected_exit_code=1, expected_rules=["RD001"], expected_severities=["BREAKING"],
    )
    build_case(
        8, "register_removed", by_key["saml11"], source_paths,
        mutation_name="remove one explicit register", mutation=mutation_register_removed,
        expected_exit_code=1, expected_rules=["RD002"], expected_severities=["BREAKING"],
    )
    build_case(
        9, "field_layout_changed", by_key["samd51"], source_paths,
        mutation_name="move one field bit range", mutation=mutation_field_layout,
        expected_exit_code=1, expected_rules=["RD003"], expected_severities=["BREAKING"],
    )
    build_case(
        10, "field_renamed", by_key["stm32f407"], source_paths,
        mutation_name="rename one field", mutation=mutation_field_renamed,
        expected_exit_code=1, expected_rules=["RD005"], expected_severities=["BREAKING"],
    )
    build_case(
        11, "reset_value_changed", by_key["lpc176x5x"], source_paths,
        mutation_name="flip one reset-value bit", mutation=mutation_reset_value,
        expected_exit_code=0, expected_rules=["RD010"], expected_severities=["WARNING"],
        notes=(
            "Default fail threshold is BREAKING, so a warning should return exit 0; "
            "--fail-on warning should return exit 1."
        ),
    )
    build_case(
        12, "interrupt_renumbered", by_key["nrf52840"], source_paths,
        mutation_name="IRQ value + 1", mutation=mutation_interrupt,
        expected_exit_code=1, expected_rules=["RD015"], expected_severities=["BREAKING"],
    )
    build_case(
        13, "write_semantics_changed", by_key["stm32f407"], source_paths,
        mutation_name="toggle modifiedWriteValues", mutation=mutation_write_semantics,
        expected_exit_code=1, expected_rules=["RD017"], expected_severities=["BREAKING"],
    )
    build_case(
        14, "register_added", by_key["arm_sample"], source_paths,
        mutation_name="add one register", mutation=mutation_register_added,
        expected_exit_code=0, expected_rules=["RD020"], expected_severities=["SAFE"],
    )
    build_case(
        15, "description_changed", by_key["arm_sample"], source_paths,
        mutation_name="description text only", mutation=mutation_description,
        expected_exit_code=0, expected_rules=["RD030"], expected_severities=["SAFE"],
    )
    build_case(
        16, "malformed_xml", by_key["arm_sample"], source_paths,
        mutation_name="truncate XML", mutation=mutation_malformed,
        expected_exit_code=2, expected_rules=[], expected_severities=[],
        notes="Candidate parse must fail cleanly with tool exit code 2, not a traceback.",
    )


def self_test() -> None:
    minimal = """<?xml version=\"1.0\" encoding=\"utf-8\"?>
<device><name>TEST</name><version>1</version><description>test</description><addressUnitBits>8</addressUnitBits><width>32</width>
<peripherals><peripheral><name>UART0</name><description>UART</description><baseAddress>0x40000000</baseAddress>
<interrupt><name>UART0</name><value>5</value></interrupt><registers><register><name>CTRL</name><description>Control</description>
<addressOffset>0x0</addressOffset><size>32</size><access>read-write</access><resetValue>0x0</resetValue><resetMask>0xFFFFFFFF</resetMask>
<fields><field><name>EN</name><description>Enable</description><bitOffset>0</bitOffset><bitWidth>1</bitWidth><access>read-write</access><modifiedWriteValues>oneToClear</modifiedWriteValues></field></fields>
</register></registers></peripheral></peripherals></device>"""
    mutations: list[Mutation] = [
        mutation_register_moved, mutation_register_removed, mutation_field_layout,
        mutation_field_renamed, mutation_reset_value, mutation_interrupt,
        mutation_write_semantics, mutation_register_added, mutation_description,
        mutation_malformed,
    ]
    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp) / "source.svd"
        for func in mutations:
            base.write_text(minimal, encoding="utf-8")
            result = func(base)
            if not result.get("target_path"):
                raise AssertionError(f"{func.__name__} returned incomplete metadata")
    print("setup_cases.py self-test passed")


def main() -> int:
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument(
        "--force-download", action="store_true", help="Redownload sources even if cached."
    )
    arg_parser.add_argument(
        "--self-test", action="store_true", help="Run offline mutation self-tests only."
    )
    args = arg_parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    try:
        source_paths, records = load_sources(force=args.force_download)
        build_all(source_paths)
    except Exception as exc:  # noqa: BLE001 - command-line boundary
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"\nBuilt 16 cases in {CASES_DIR}")
    print(f"Locked {len(records)} sources in {LOCK_PATH}")
    print("Next: python validation/pre_release/run_cases.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
