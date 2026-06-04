# tests/unit/catalog/test_refs.py
"""Tests for PinRef and PartRef."""

import dataclasses

import pytest

from schematika.catalog.identifiers import ConnectorId, DeviceTag, PartId
from schematika.catalog.refs import PartRef, PinRef


def test_pinref_fields():
    ref = PinRef(device=DeviceTag("-Q1"), connector=ConnectorId("J1"), port_id="1")
    assert ref.device == "-Q1"
    assert ref.connector == "J1"
    assert ref.port_id == "1"


def test_pinref_is_frozen():
    ref = PinRef(device=DeviceTag("-Q1"), connector=ConnectorId("J1"), port_id="1")
    with pytest.raises(dataclasses.FrozenInstanceError):
        ref.port_id = "2"  # ty: ignore[invalid-assignment]


def test_pinref_kw_only():
    with pytest.raises(TypeError):
        PinRef(DeviceTag("-Q1"), ConnectorId("J1"), "1")  # ty: ignore[missing-argument, too-many-positional-arguments]


def test_partref_tag_defaults_none():
    ref = PartRef(part=PartId("phoenix_3pos"))
    assert ref.part == "phoenix_3pos"
    assert ref.tag is None


def test_pinref_connector_defaults_none():
    ref = PinRef(device=DeviceTag("X100"), port_id="1")
    assert ref.connector is None
    assert ref.device == "X100"
    assert ref.port_id == "1"


def test_pinref_connector_explicit_still_works():
    ref = PinRef(device=DeviceTag("-Q1"), connector=ConnectorId("J1"), port_id="1")
    assert ref.connector == "J1"
