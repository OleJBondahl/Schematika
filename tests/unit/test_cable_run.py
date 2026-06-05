"""C2a: CableRun renders byte-identical to the legacy InterDeviceConnection path."""

from schematika.cable.builder import _build_inter_device_drawing
from schematika.cable.cable_run import CableRun, cable_run_to_drawing
from schematika.catalog.cables import CableData, ConnectorData
from schematika.catalog.identifiers import ConnectorId, DeviceTag, NetId
from schematika.catalog.refs import PinRef
from schematika.catalog.wires import Wire
from schematika.electrical.inter_device import (
    CableTargetEndpoint,
    InterDeviceConnection,
    WireSpec,
)


def _src(port: str) -> PinRef:
    return PinRef(device=DeviceTag("JB1"), connector=ConnectorId("J1"), port_id=port)


def test_fanout_parity_with_legacy() -> None:
    src_cd = ConnectorData(pins=(), mpn="src_mpn", pincount=4)
    bmu_cd = ConnectorData(pins=(), mpn="bmu_mpn", pincount=2)
    cable = CableData(wire_gauge=0.5, cable_note="sleeve")

    conn = InterDeviceConnection(
        from_device="JB1",
        from_connector="J1",
        to_endpoints=(
            CableTargetEndpoint(device="BMU1", connector="J3", connector_data=bmu_cd),
            CableTargetEndpoint(device="X1", connector="", connector_data=None),
        ),
        cable=cable,
        from_connector_data=src_cd,
        wires=(
            WireSpec(
                from_pin="1", to_endpoint=0, to_pin="A", color="BN", net_name="net_a"
            ),
            WireSpec(
                from_pin="2", to_endpoint=1, to_pin="1", color="BU", net_name="net_b"
            ),
            WireSpec(
                from_pin="3", to_endpoint=0, to_pin="B", color=None, net_name="net_c"
            ),
        ),
    )

    run = CableRun(
        wires=(
            Wire(
                net=NetId("net_a"),
                source=_src("1"),
                target=PinRef(
                    device=DeviceTag("BMU1"), connector=ConnectorId("J3"), port_id="A"
                ),
                color="BN",
            ),
            Wire(
                net=NetId("net_b"),
                source=_src("2"),
                target=PinRef(device=DeviceTag("X1"), port_id="1"),
                color="BU",
            ),
            Wire(
                net=NetId("net_c"),
                source=_src("3"),
                target=PinRef(
                    device=DeviceTag("BMU1"), connector=ConnectorId("J3"), port_id="B"
                ),
            ),
        ),
        cable=cable,
        connectors=(
            (
                PinRef(
                    device=DeviceTag("JB1"), connector=ConnectorId("J1"), port_id=""
                ),
                src_cd,
            ),
            (
                PinRef(
                    device=DeviceTag("BMU1"), connector=ConnectorId("J3"), port_id=""
                ),
                bmu_cd,
            ),
        ),
    )

    assert cable_run_to_drawing(run, "A-W001") == _build_inter_device_drawing(
        conn, "A-W001"
    )


def test_single_target_parity_with_legacy() -> None:
    cd = ConnectorData(pins=(), mpn="m", pincount=2)
    cable = CableData(wire_gauge=0.25)
    conn = InterDeviceConnection(
        from_device="JB1",
        from_connector="J6",
        to_endpoints=(
            CableTargetEndpoint(device="BMU2", connector="J6", connector_data=cd),
        ),
        cable=cable,
        from_connector_data=cd,
        wires=(
            WireSpec(from_pin="1", to_endpoint=0, to_pin="1", net_name="can_h"),
            WireSpec(from_pin="2", to_endpoint=0, to_pin="2", net_name="can_l"),
        ),
    )
    run = CableRun(
        wires=(
            Wire(
                net=NetId("can_h"),
                source=PinRef(
                    device=DeviceTag("JB1"), connector=ConnectorId("J6"), port_id="1"
                ),
                target=PinRef(
                    device=DeviceTag("BMU2"), connector=ConnectorId("J6"), port_id="1"
                ),
            ),
            Wire(
                net=NetId("can_l"),
                source=PinRef(
                    device=DeviceTag("JB1"), connector=ConnectorId("J6"), port_id="2"
                ),
                target=PinRef(
                    device=DeviceTag("BMU2"), connector=ConnectorId("J6"), port_id="2"
                ),
            ),
        ),
        cable=cable,
        connectors=(
            (
                PinRef(
                    device=DeviceTag("JB1"), connector=ConnectorId("J6"), port_id=""
                ),
                cd,
            ),
            (
                PinRef(
                    device=DeviceTag("BMU2"), connector=ConnectorId("J6"), port_id=""
                ),
                cd,
            ),
        ),
    )
    assert cable_run_to_drawing(run, "A-W005") == _build_inter_device_drawing(
        conn, "A-W005"
    )


def test_first_seen_connector_order_and_nonint_sort() -> None:
    cable = CableData(wire_gauge=0.5)
    run = CableRun(
        wires=(
            Wire(
                net=NetId("n1"),
                source=PinRef(
                    device=DeviceTag("X"), connector=ConnectorId("F"), port_id="1a"
                ),
                target=PinRef(
                    device=DeviceTag("B1"), connector=ConnectorId("J3"), port_id="x"
                ),
            ),
            Wire(
                net=NetId("n2"),
                source=PinRef(
                    device=DeviceTag("X"), connector=ConnectorId("F"), port_id="1b"
                ),
                target=PinRef(
                    device=DeviceTag("B2"), connector=ConnectorId("J3"), port_id="y"
                ),
            ),
        ),
        cable=cable,
    )
    drawing = cable_run_to_drawing(run, "A-W009")
    assert [c.designator for c in drawing.connectors] == ["X-F", "B1-J3", "B2-J3"]
    assert drawing.connectors[0].pins == ("1a", "1b")
    assert drawing.cable.wirelabels == ("n1", "n2")
