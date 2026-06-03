# tests/unit/catalog/test_parts.py
"""Tests for PartSpec."""

import dataclasses

import pytest

from schematika.catalog.identifiers import PartId
from schematika.catalog.parts import PartSpec


def test_partspec_minimal():
    spec = PartSpec(
        part=PartId("phoenix_3pos"),
        mpn="3213943",
        category="connector",
        description="Phoenix 3-pos plug",
    )
    assert spec.part == "phoenix_3pos"
    assert spec.manufacturer is None


def test_partspec_frozen():
    spec = PartSpec(part=PartId("x"), mpn="1", category="device", description="d")
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.mpn = "2"  # ty: ignore[invalid-assignment]
