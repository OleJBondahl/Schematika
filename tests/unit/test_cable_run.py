"""CableRun -> CableDrawing: connector ordering, pin synthesis, net labels."""

from schematika.cable.cable_run import CableRun, cable_run_to_drawing
from schematika.catalog.cables import CableData, ConnectorData
from schematika.catalog.identifiers import ConnectorId, DeviceTag, NetId
from schematika.catalog.refs import PinRef
from schematika.catalog.wires import Wire


def _src(port: str) -> PinRef:
    return PinRef(device=DeviceTag("JB1"), connector=ConnectorId("J1"), port_id=port)


def test_fanout_drawing_shape() -> None:
    src_cd = ConnectorData(pins=(), mpn="src_mpn", pincount=4)
    bmu_cd = ConnectorData(pins=(), mpn="bmu_mpn", pincount=2)
    cable = CableData(wire_gauge=0.5, cable_note="sleeve")

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

    drawing = cable_run_to_drawing(run, "A-W001")

    # One source connector followed by per-endpoint target connectors, in
    # first-seen wire order (BMU1-J3 before X1).
    assert [c.designator for c in drawing.connectors] == ["JB1-J1", "BMU1-J3", "X1"]
    assert drawing.from_designator == "JB1-J1"
    assert drawing.to_designators == ("BMU1-J3", "X1")
    assert drawing.title == "JB1-J1 <-> BMU1-J3, X1"
    # Source pins in wire order; BMU1-J3 collects both its pins.
    assert drawing.connectors[0].pins == ("1", "2", "3")
    assert drawing.connectors[1].pins == ("A", "B")
    assert drawing.connectors[2].pins == ("1",)
    # Connector metadata carried through from ConnectorData.
    assert drawing.connectors[0].mpn == "src_mpn"
    assert drawing.connectors[1].mpn == "bmu_mpn"
    # Per-wire net labels in wire order.
    assert drawing.cable.wirelabels == ("net_a", "net_b", "net_c")
    assert drawing.cable.designator == "A-W001"
    # One CableConnection per wire, routed source -> target.
    assert [
        (c.from_pin, c.to_connector, c.to_pin, c.wire) for c in drawing.connections
    ] == [
        ("1", "BMU1-J3", "A", 1),
        ("2", "X1", "1", 2),
        ("3", "BMU1-J3", "B", 3),
    ]


def test_single_target_drawing_shape() -> None:
    cd = ConnectorData(pins=(), mpn="m", pincount=2)
    cable = CableData(wire_gauge=0.25)
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
    drawing = cable_run_to_drawing(run, "A-W005")

    assert [c.designator for c in drawing.connectors] == ["JB1-J6", "BMU2-J6"]
    assert drawing.title == "JB1-J6 <-> BMU2-J6"
    assert drawing.connectors[0].pins == ("1", "2")
    assert drawing.connectors[1].pins == ("1", "2")
    assert drawing.cable.wirelabels == ("can_h", "can_l")
    assert [(c.from_pin, c.to_pin, c.wire) for c in drawing.connections] == [
        ("1", "1", 1),
        ("2", "2", 2),
    ]


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


def test_explicit_pins_preserved_verbatim() -> None:
    # Target connector has explicit pins in REVERSE order ("3", "1"); the
    # drawing must preserve that order — not sort it.
    tgt_cd = ConnectorData(pins=("3", "1"), mpn="tgt_mpn", pincount=2)
    cable = CableData(wire_gauge=1.0)

    run = CableRun(
        wires=(
            Wire(
                net=NetId("sig_a"),
                source=_src("1"),
                target=PinRef(
                    device=DeviceTag("PLC1"), connector=ConnectorId("X1"), port_id="3"
                ),
            ),
            Wire(
                net=NetId("sig_b"),
                source=_src("2"),
                target=PinRef(
                    device=DeviceTag("PLC1"), connector=ConnectorId("X1"), port_id="1"
                ),
            ),
        ),
        cable=cable,
        connectors=(
            (
                PinRef(
                    device=DeviceTag("PLC1"), connector=ConnectorId("X1"), port_id=""
                ),
                tgt_cd,
            ),
        ),
    )

    drawing = cable_run_to_drawing(run, "A-W010")
    tgt_connector = next(c for c in drawing.connectors if c.designator == "PLC1-X1")
    assert tgt_connector.pins == ("3", "1")


def test_project_add_cable_runs_buffers() -> None:
    from schematika.project import Project

    cable = CableData(wire_gauge=0.5)
    run = CableRun(
        wires=(
            Wire(
                net=NetId("n"),
                source=_src("1"),
                target=PinRef(
                    device=DeviceTag("B1"), connector=ConnectorId("J3"), port_id="A"
                ),
            ),
        ),
        cable=cable,
    )
    p = Project()
    assert p._cable_runs == []
    returned = p.add_cable_runs([run])
    assert returned is p
    assert p._cable_runs == [run]
