"""Tests for the CableBuilder class."""

import pytest

from schematika.cable.cable_builder import CableBuilder
from schematika.cable.errors import CableError
from schematika.catalog.cables import CableProductSpec
from schematika.catalog.connectors import ConnectorInstance, ConnectorSpec
from schematika.catalog.errors import CatalogLookupError
from schematika.catalog.identifiers import (
    CableId,
    ConnectorId,
    DeviceTag,
    NetId,
    PartId,
)
from schematika.catalog.refs import PinRef
from schematika.catalog.result import ResolvedCatalog
from schematika.catalog.wires import Wire


def _catalog():
    return ResolvedCatalog(
        parts={},
        connectors={
            PartId("ca"): ConnectorSpec(part=PartId("ca"), pincount=1, pins=("1",))
        },
        cable_products={
            PartId("cab"): CableProductSpec(part=PartId("cab"), conductor_count=1)
        },
        devices={},
        cable_instances={},
    )


def _conn():
    return ConnectorInstance(
        device=DeviceTag("-M1"), name=ConnectorId("J1"), part=PartId("ca")
    )


def _wire():
    src = PinRef(device=DeviceTag("-M1"), connector=ConnectorId("J1"), port_id="1")
    tgt = PinRef(device=DeviceTag("X1"), port_id="1")
    return Wire(net=NetId("n"), source=src, target=tgt)


def test_build_happy_path():
    b = CableBuilder(name=CableId("W1"), catalog=_catalog())
    b.set_cable_product(PartId("cab"))
    b.add_connector(_conn())
    b.add_wire(_wire())
    result = b.build()
    assert result.name == "W1"
    assert result.cable_product == "cab"
    assert len(result.wires) == 1
    assert len(result.connectors) == 1


def test_build_without_product_raises():
    b = CableBuilder(name=CableId("W1"), catalog=_catalog())
    with pytest.raises(CableError):
        b.build()


def test_set_unknown_product_raises():
    b = CableBuilder(name=CableId("W1"), catalog=_catalog())
    with pytest.raises(CatalogLookupError):
        b.set_cable_product(PartId("nope"))


def test_add_wire_unregistered_connector_raises():
    b = CableBuilder(name=CableId("W1"), catalog=_catalog())
    b.set_cable_product(PartId("cab"))
    bad_src = PinRef(device=DeviceTag("-M1"), connector=ConnectorId("J9"), port_id="1")
    bad = Wire(
        net=NetId("n"),
        source=bad_src,
        target=PinRef(device=DeviceTag("X1"), port_id="1"),
    )
    with pytest.raises(CableError):
        b.add_wire(bad)


def test_add_connector_unknown_part_raises():
    b = CableBuilder(name=CableId("W1"), catalog=_catalog())
    bad = ConnectorInstance(
        device=DeviceTag("-M1"), name=ConnectorId("J1"), part=PartId("missing")
    )
    with pytest.raises(CatalogLookupError):
        b.add_connector(bad)


def test_two_connectors_same_name_different_device_both_kept():
    b = CableBuilder(name=CableId("W1"), catalog=_catalog())
    b.set_cable_product(PartId("cab"))
    b.add_connector(
        ConnectorInstance(
            device=DeviceTag("-M1"), name=ConnectorId("J1"), part=PartId("ca")
        )
    )
    b.add_connector(
        ConnectorInstance(
            device=DeviceTag("-M2"), name=ConnectorId("J1"), part=PartId("ca")
        )
    )
    result = b.build()
    assert len(result.connectors) == 2
