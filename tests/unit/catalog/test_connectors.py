# tests/unit/catalog/test_connectors.py
"""Tests for ConnectorSpec and ConnectorInstance."""

import dataclasses

import pytest

from schematika.catalog.connectors import ConnectorInstance, ConnectorSpec
from schematika.catalog.identifiers import ConnectorId, DeviceTag, PartId


def test_connector_spec():
    spec = ConnectorSpec(part=PartId("phoenix_3pos"), pincount=3, pins=("1", "2", "PE"))
    assert spec.pincount == 3
    assert spec.pins == ("1", "2", "PE")
    assert spec.style is None


def test_connector_instance_carries_device():
    inst = ConnectorInstance(
        device=DeviceTag("-Q1"), name=ConnectorId("J1"), part=PartId("phoenix_3pos")
    )
    assert inst.device == "-Q1"
    assert inst.name == "J1"


def test_instances_frozen():
    inst = ConnectorInstance(
        device=DeviceTag("-Q1"), name=ConnectorId("J1"), part=PartId("p")
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        inst.name = ConnectorId("J2")  # ty: ignore[invalid-assignment]
