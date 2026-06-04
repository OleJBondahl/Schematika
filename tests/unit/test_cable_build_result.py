"""Tests for CableBuildResult."""

import dataclasses

import pytest

from schematika.cable.result import CableBuildResult
from schematika.catalog.connectors import ConnectorInstance
from schematika.catalog.identifiers import (
    CableId,
    ConnectorId,
    DeviceTag,
    NetId,
    PartId,
)
from schematika.catalog.refs import PinRef
from schematika.catalog.wires import Wire


def _wire():
    src = PinRef(device=DeviceTag("-M1"), connector=ConnectorId("J1"), port_id="1")
    tgt = PinRef(device=DeviceTag("X1"), port_id="1")
    return Wire(net=NetId("n"), source=src, target=tgt)


def test_cable_build_result_fields():
    result = CableBuildResult(
        name=CableId("W1"),
        wires=(_wire(),),
        connectors=(
            ConnectorInstance(
                device=DeviceTag("-M1"), name=ConnectorId("J1"), part=PartId("ca")
            ),
        ),
        cable_product=PartId("cab"),
    )
    assert result.name == "W1"
    assert result.cable_product == "cab"
    assert len(result.wires) == 1
    assert len(result.connectors) == 1


def test_cable_build_result_frozen():
    result = CableBuildResult(
        name=CableId("W1"), wires=(), connectors=(), cable_product=PartId("cab")
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.cable_product = PartId("other")  # ty: ignore[invalid-assignment]


def test_new_cable_surface_exported():
    from schematika.cable import (
        CableBuilder,
        CableRenderConfig,
        result_to_drawing,
    )
    from schematika.cable import (
        CableBuildResult as PkgResult,
    )
    from schematika.cable.cable_builder import CableBuilder as _SubBuilder
    from schematika.cable.render_config import CableRenderConfig as _SubConfig

    assert PkgResult is CableBuildResult
    assert CableBuilder is _SubBuilder
    assert CableRenderConfig is _SubConfig
    assert callable(result_to_drawing)
