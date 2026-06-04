"""Tests for result_to_drawing."""

from schematika.cable.drawing_adapter import result_to_drawing
from schematika.cable.render_config import CableRenderConfig
from schematika.cable.result import CableBuildResult
from schematika.catalog.cables import CableProductSpec
from schematika.catalog.connectors import ConnectorInstance, ConnectorSpec
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
            PartId("ca"): ConnectorSpec(part=PartId("ca"), pincount=1, pins=("1",)),
            PartId("cb"): ConnectorSpec(part=PartId("cb"), pincount=1, pins=("1",)),
        },
        cable_products={
            PartId("cab"): CableProductSpec(
                part=PartId("cab"), conductor_count=1, gauge_mm2=0.5
            )
        },
        devices={},
        cable_instances={},
    )


def _result():
    src = PinRef(device=DeviceTag("-M1"), connector=ConnectorId("J1"), port_id="1")
    tgt = PinRef(device=DeviceTag("-M2"), connector=ConnectorId("J2"), port_id="1")
    return CableBuildResult(
        name=CableId("W1"),
        wires=(
            Wire(net=NetId("n"), source=src, target=tgt, color="RD", length_mm=1200.0),
        ),
        connectors=(
            ConnectorInstance(
                device=DeviceTag("-M1"), name=ConnectorId("J1"), part=PartId("ca")
            ),
            ConnectorInstance(
                device=DeviceTag("-M2"), name=ConnectorId("J2"), part=PartId("cb")
            ),
        ),
        cable_product=PartId("cab"),
    )


def test_drawing_propagates_color_length_gauge():
    drawing = result_to_drawing(_result(), catalog=_catalog())
    assert drawing.cable.designator == "W1"
    assert drawing.cable.wire_colors == ("RD",)
    assert drawing.cable.length == 1200.0
    assert drawing.cable.wire_gauge == 0.5
    assert drawing.cable.wirecount == 1


def test_drawing_connectors_and_connections():
    drawing = result_to_drawing(_result(), catalog=_catalog())
    assert {c.designator for c in drawing.connectors} == {"J1", "J2"}
    assert len(drawing.connections) == 1
    conn = drawing.connections[0]
    assert conn.from_connector == "J1"
    assert conn.from_pin == "1"
    assert conn.to_connector == "J2"
    assert conn.cable == "W1"
    assert conn.wire == 1


def test_designator_falls_back_to_device_for_terminal_endpoint():
    src = PinRef(device=DeviceTag("-M1"), connector=ConnectorId("J1"), port_id="1")
    tgt = PinRef(device=DeviceTag("X100"), port_id="1")
    result = CableBuildResult(
        name=CableId("W1"),
        wires=(Wire(net=NetId("n"), source=src, target=tgt),),
        connectors=(
            ConnectorInstance(
                device=DeviceTag("-M1"), name=ConnectorId("J1"), part=PartId("ca")
            ),
        ),
        cable_product=PartId("cab"),
    )
    conn = result_to_drawing(result, catalog=_catalog()).connections[0]
    assert conn.from_connector == "J1"
    assert conn.to_connector == "X100"


def test_show_pincount_config_applied():
    cfg = CableRenderConfig(show_pincount=frozenset({ConnectorId("J1")}))
    drawing = result_to_drawing(_result(), catalog=_catalog(), config=cfg)
    by_name = {c.designator: c for c in drawing.connectors}
    assert by_name["J1"].show_pincount is True
    assert by_name["J2"].show_pincount is False
