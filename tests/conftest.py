"""Shared fixtures for regdrift tests."""

from collections.abc import Callable

import pytest

from regdrift.model import Device
from regdrift.parse import parse_svd_string

_DEVICE_XML = """<?xml version="1.0" encoding="utf-8"?>
<device schemaVersion="1.1">
  <name>TESTCHIP</name>
  <version>1.0</version>
  <addressUnitBits>8</addressUnitBits>
  <width>32</width>
  {device_props}
  <peripherals>
    {peripherals}
  </peripherals>
</device>
"""

MakeDevice = Callable[..., Device]


@pytest.fixture
def make_device() -> MakeDevice:
    """Build a Device from handcrafted <peripheral> XML snippets."""

    def _make(peripherals: str, device_props: str = "") -> Device:
        return parse_svd_string(
            _DEVICE_XML.format(peripherals=peripherals, device_props=device_props)
        )

    return _make
