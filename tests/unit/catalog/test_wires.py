# tests/unit/catalog/test_wires.py
"""Tests for Wire."""

import dataclasses

import pytest

from schematika.catalog.identifiers import ConnectorId, DeviceTag, NetId
from schematika.catalog.refs import PinRef
from schematika.catalog.wires import Wire


def _pin(port):
    return PinRef(device=DeviceTag("-Q1"), connector=ConnectorId("J1"), port_id=port)


def test_wire_fields():
    w = Wire(net=NetId("VBUS"), source=_pin("1"), target=_pin("2"))
    assert w.net == "VBUS"
    assert w.color is None
    assert w.length_mm is None


def test_wire_frozen():
    w = Wire(net=NetId("VBUS"), source=_pin("1"), target=_pin("2"))
    with pytest.raises(dataclasses.FrozenInstanceError):
        w.color = "red"  # ty: ignore[invalid-assignment]
