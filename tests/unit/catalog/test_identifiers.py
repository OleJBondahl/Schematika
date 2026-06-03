"""Tests for the Phase-1 typed string identifiers."""

import pytest

from schematika.catalog.errors import CatalogValidationError
from schematika.catalog.identifiers import (
    CableId,
    CircuitId,
    ConnectorId,
    DeviceTag,
    NetId,
    PartId,
    TagPrefix,
)


def test_partid_accepts_valid_charset():
    assert PartId("phoenix_3.pos-1") == "phoenix_3.pos-1"


@pytest.mark.parametrize("bad", ["bad id", "with/slash", "amp&", ""])
def test_partid_rejects_invalid(bad):
    with pytest.raises(CatalogValidationError):
        PartId(bad)


def test_netid_rejects_slash():
    with pytest.raises(CatalogValidationError):
        NetId("/foo")
    with pytest.raises(CatalogValidationError):
        NetId("a/b")


def test_netid_accepts_clean():
    assert NetId("VBUS_24V") == "VBUS_24V"


def test_tagprefix_pattern():
    assert TagPrefix("FT") == "FT"
    assert TagPrefix("K1") == "K1"
    for bad in ["", "k", "1K", "K-1"]:
        with pytest.raises(CatalogValidationError):
            TagPrefix(bad)


@pytest.mark.parametrize("cls", [ConnectorId, DeviceTag, CableId, CircuitId])
def test_nonempty_ids_reject_empty(cls):
    with pytest.raises(CatalogValidationError):
        cls("")


def test_nonempty_ids_accept():
    assert ConnectorId("J1") == "J1"
    assert DeviceTag("-Q1") == "-Q1"
    assert CableId("W12") == "W12"
    assert CircuitId("main") == "main"


def test_ids_are_str_subclasses():
    assert isinstance(PartId("x"), str)
    assert PartId("x") == "x"
    d: dict[str, int] = {NetId("n"): 1}
    assert d["n"] == 1
