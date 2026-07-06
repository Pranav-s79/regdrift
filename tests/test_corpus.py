"""Parse the entire vendor corpus and spot-check known values against datasheets.

Requires tests/corpus/ to be populated: run `python scripts/fetch_corpus.py`.
"""

from functools import lru_cache
from pathlib import Path

import pytest

from regdrift.model import Cluster, Device, Peripheral, Register
from regdrift.parse import parse_svd

CORPUS = Path(__file__).parent / "corpus"
CORPUS_FILES = sorted(CORPUS.glob("*.svd"))

pytestmark = pytest.mark.skipif(
    not CORPUS_FILES, reason="corpus not fetched; run scripts/fetch_corpus.py"
)


@lru_cache(maxsize=None)
def load(filename: str) -> Device:
    return parse_svd(CORPUS / filename)


def periph(dev: Device, name: str) -> Peripheral:
    return next(p for p in dev.peripherals if p.name == name)


def child(container: Peripheral | Cluster, name: str) -> Register | Cluster:
    return next(c for c in container.children if c.name == name)


@pytest.mark.parametrize("svd", CORPUS_FILES, ids=lambda p: p.name)
def test_corpus_parses(svd: Path) -> None:
    device = parse_svd(svd)
    assert device.peripherals, f"{svd.name} parsed to zero peripherals"


# --- STM32F103 (RM0008): GPIO ------------------------------------------------


def test_stm32f103_gpioa_base_address() -> None:
    assert periph(load("STM32F103xx.svd"), "GPIOA").base_address == 0x4001_0800


def test_stm32f103_crl_reset_value_and_hex_size() -> None:
    crl = child(periph(load("STM32F103xx.svd"), "GPIOA"), "CRL")
    assert isinstance(crl, Register)
    assert crl.reset_value == 0x4444_4444  # RM0008 table: port config reset
    assert crl.size == 32  # written as <size>0x20</size> in the file


def test_stm32f103_gpiob_derived_from_gpioa() -> None:
    gpiob = periph(load("STM32F103xx.svd"), "GPIOB")
    assert gpiob.base_address == 0x4001_0C00
    crl = child(gpiob, "CRL")
    assert isinstance(crl, Register)
    assert crl.reset_value == 0x4444_4444  # inherited via derivedFrom


# --- ARM sample device: peripheral derivation --------------------------------


def test_arm_sample_timer1_derived_from_timer0() -> None:
    timer1 = periph(load("ARM_Sample.svd"), "TIMER1")
    assert timer1.base_address == 0x4001_0100
    cr = child(timer1, "CR")
    assert isinstance(cr, Register)
    assert cr.fields  # register structure copied from TIMER0


# --- nRF52840 (Nordic PS): clusters and dim arrays ----------------------------


def test_nrf52840_ficr_info_cluster() -> None:
    ficr = periph(load("nrf52840.svd"), "FICR")
    assert ficr.base_address == 0x1000_0000
    info = child(ficr, "INFO")
    assert isinstance(info, Cluster)
    assert info.address_offset == 0x100
    part = child(info, "PART")
    assert isinstance(part, Register)
    assert part.address_offset == 0x0


def test_nrf52840_pin_cnf_array_expansion() -> None:
    p0 = periph(load("nrf52840.svd"), "P0")
    assert p0.base_address == 0x5000_0000
    pin_cnf = [c for c in p0.children if c.name.startswith("PIN_CNF")]
    assert len(pin_cnf) == 32
    assert pin_cnf[0].name == "PIN_CNF0"
    assert pin_cnf[0].address_offset == 0x700
    assert pin_cnf[31].name == "PIN_CNF31"
    assert pin_cnf[31].address_offset == 0x77C
    assert isinstance(pin_cnf[0], Register)
    assert pin_cnf[0].reset_value == 0x2


# --- MK64F12 (K64 Sub-Family Reference Manual) --------------------------------


def test_mk64f12_sim_scgc5() -> None:
    sim = periph(load("MK64F12.svd"), "SIM")
    assert sim.base_address == 0x4004_7000
    scgc5 = child(sim, "SCGC5")
    assert isinstance(scgc5, Register)
    assert scgc5.address_offset == 0x1038
    porta = next(f for f in scgc5.fields if f.name == "PORTA")
    assert (porta.bit_offset, porta.bit_width) == (9, 1)


# --- RP2040, STM32H743, LPC176x: base addresses -------------------------------


def test_rp2040_timer_base_address() -> None:
    assert periph(load("rp2040.svd"), "TIMER").base_address == 0x4005_4000


def test_stm32h743_gpioa_base_address() -> None:
    assert periph(load("STM32H743x.svd"), "GPIOA").base_address == 0x5802_0000


def test_lpc176x_uart0_base_address() -> None:
    assert periph(load("LPC176x5x_v0.2.svd"), "UART0").base_address == 0x4000_C000
