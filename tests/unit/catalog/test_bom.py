# tests/unit/catalog/test_bom.py
"""Tests for BOMRow."""

import dataclasses

import pytest

from schematika.catalog.bom import BOMRow
from schematika.catalog.identifiers import PartId


def test_bomrow_fields():
    row = BOMRow(part=PartId("phoenix_3pos"), count=2, used_by=("J1", "J3"))
    assert row.count == 2
    assert row.used_by == ("J1", "J3")


def test_bomrow_frozen():
    row = BOMRow(part=PartId("p"), count=1, used_by=())
    with pytest.raises(dataclasses.FrozenInstanceError):
        row.count = 2  # ty: ignore[invalid-assignment]
