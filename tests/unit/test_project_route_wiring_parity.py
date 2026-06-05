"""C1a: route()/add_wires() convert to terminal-only ConnectionRows matching internal_wiring()."""

from schematika.catalog import PinRef
from schematika.catalog.identifiers import DeviceTag, NetId
from schematika.project import Project, _wires_to_terminal_rows


def _project() -> Project:
    # Mirror the Project(...) construction used in tests/unit/test_project_harness.py.
    return Project()


def test_wires_to_terminal_rows_basic() -> None:
    from schematika.catalog.wires import Wire
    from schematika.electrical.harness import HarnessBuildResult

    wires = (
        Wire(
            net=NetId("K1_A1"),
            source=PinRef(device=DeviceTag("K1"), port_id="A1"),
            target=PinRef(device=DeviceTag("X1"), port_id="3"),
        ),
    )
    result = HarnessBuildResult(wires=wires, plc_assignments=())
    rows = _wires_to_terminal_rows(result)
    assert rows == [("K1", "A1", "X1", "3", "", "")]


def test_resolve_routes_matches_internal_wiring() -> None:
    rows = [("K1", "A1", "X1", "3", "", ""), ("K2", "A2", "X1", "4", "", "")]

    legacy = _project().internal_wiring(rows)

    new = _project()
    new.route(
        PinRef(device=DeviceTag("K1"), port_id="A1"),
        PinRef(device=DeviceTag("X1"), port_id="3"),
    )
    new.route(
        PinRef(device=DeviceTag("K2"), port_id="A2"),
        PinRef(device=DeviceTag("X1"), port_id="4"),
    )
    new._resolve_routes()

    assert sorted(new._terminal_only_connections) == sorted(
        legacy._terminal_only_connections
    )


def test_resolve_routes_noop_when_no_declarations() -> None:
    p = _project()
    p._resolve_routes()
    assert p._terminal_only_connections == []


def test_build_circuits_invokes_resolve_routes() -> None:
    p = _project()
    p.route(
        PinRef(device=DeviceTag("K1"), port_id="A1"),
        PinRef(device=DeviceTag("X1"), port_id="3"),
    )
    p.route(
        PinRef(device=DeviceTag("K2"), port_id="A2"),
        PinRef(device=DeviceTag("X1"), port_id="4"),
    )

    assert p._terminal_only_connections == []

    p.build_circuits()

    assert sorted(p._terminal_only_connections) == sorted(
        [("K1", "A1", "X1", "3", "", ""), ("K2", "A2", "X1", "4", "", "")]
    )
