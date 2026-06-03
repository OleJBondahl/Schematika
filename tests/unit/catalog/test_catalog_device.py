# tests/unit/catalog/test_catalog_device.py
"""Tests for the Phase-1 CatalogDevice.part field."""

from schematika.catalog.device import CatalogDevice
from schematika.catalog.identifiers import PartId


def test_part_defaults_none():
    assert CatalogDevice(tag="TT-101", description="d").part is None


def test_part_accepts_partid():
    dev = CatalogDevice(tag="TT-101", description="d", part=PartId("sick_tt"))
    assert dev.part == "sick_tt"
