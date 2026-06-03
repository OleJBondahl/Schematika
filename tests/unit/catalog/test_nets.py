# tests/unit/catalog/test_nets.py
"""Tests for normalize_net_name."""

import pytest

from schematika.catalog.errors import CatalogValidationError
from schematika.catalog.identifiers import NetId
from schematika.catalog.nets import normalize_net_name


def test_strips_leading_slash():
    out = normalize_net_name("/VBUS_24V")
    assert out == "VBUS_24V"
    assert isinstance(out, NetId)


def test_plain_passthrough():
    assert normalize_net_name("GND") == "GND"


def test_rejects_internal_slash():
    with pytest.raises(CatalogValidationError):
        normalize_net_name("a/b")


def test_rejects_empty_result():
    with pytest.raises(CatalogValidationError):
        normalize_net_name("/")
    with pytest.raises(CatalogValidationError):
        normalize_net_name("")
