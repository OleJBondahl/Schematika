# tests/unit/catalog/test_cable_product.py
"""Tests for CableProductSpec."""

import dataclasses

import pytest

from schematika.catalog.cables import CableProductSpec
from schematika.catalog.identifiers import PartId


def test_cable_product_minimal():
    spec = CableProductSpec(part=PartId("oelflex_110_4x0.75"), conductor_count=4)
    assert spec.conductor_count == 4
    assert spec.default_length_mm is None


def test_cable_product_frozen():
    spec = CableProductSpec(part=PartId("p"), conductor_count=2)
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.conductor_count = 3  # ty: ignore[invalid-assignment]


def test_cable_product_gauge_and_category():
    spec = CableProductSpec(
        part=PartId("oelflex"), conductor_count=4, gauge_mm2=0.75, category="control"
    )
    assert spec.gauge_mm2 == 0.75
    assert spec.category == "control"


def test_cable_product_gauge_category_default_none():
    spec = CableProductSpec(part=PartId("p"), conductor_count=2)
    assert spec.gauge_mm2 is None
    assert spec.category is None
