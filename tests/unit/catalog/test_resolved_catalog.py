# tests/unit/catalog/test_resolved_catalog.py
"""Tests for ResolvedCatalog lookups."""

import pytest

from schematika.catalog.cables import CableInstance, CableProductSpec
from schematika.catalog.connectors import ConnectorSpec
from schematika.catalog.device import CatalogDevice
from schematika.catalog.errors import CatalogLookupError
from schematika.catalog.identifiers import PartId
from schematika.catalog.parts import PartSpec
from schematika.catalog.result import ResolvedCatalog


def _resolved():
    p = PartSpec(part=PartId("p1"), mpn="1", category="device", description="d")
    c = ConnectorSpec(part=PartId("c1"), pincount=2, pins=("1", "2"))
    return ResolvedCatalog(
        parts={PartId("p1"): p},
        connectors={PartId("c1"): c},
        cable_products={},
        devices={},
        cable_instances={},
    )


def test_lookup_part_hit():
    assert _resolved().lookup_part(PartId("p1")).mpn == "1"


def test_lookup_part_miss_raises():
    with pytest.raises(CatalogLookupError):
        _resolved().lookup_part(PartId("nope"))


def test_lookup_connector_hit():
    assert _resolved().lookup_connector(PartId("c1")).pincount == 2


def test_is_frozen():
    import dataclasses

    with pytest.raises(dataclasses.FrozenInstanceError):
        _resolved().parts = {}


def test_all_lookups_return_correct_object():
    part = PartSpec(part=PartId("p1"), mpn="1", category="device", description="d")
    conn = ConnectorSpec(part=PartId("c1"), pincount=2, pins=("1", "2"))
    cable_product = CableProductSpec(part=PartId("cp1"), conductor_count=4)
    device = CatalogDevice(tag="D1", description="dev")
    cable_instance = CableInstance(
        tag="W1",
        spec="4x2.5",
        cable_type="power_ac",
        from_device="A",
        to_device="B",
    )
    rc = ResolvedCatalog(
        parts={PartId("p1"): part},
        connectors={PartId("c1"): conn},
        cable_products={PartId("cp1"): cable_product},
        devices={"D1": device},
        cable_instances={"W1": cable_instance},
    )
    assert rc.lookup_part(PartId("p1")) is part
    assert rc.lookup_connector(PartId("c1")) is conn
    assert rc.lookup_cable_product(PartId("cp1")) is cable_product
    assert rc.lookup_device("D1") is device
    assert rc.lookup_cable_instance("W1") is cable_instance
