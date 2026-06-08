"""R1: route()-declared wiring emits the frozen native terminal CSV.

The frozen literals below were captured from the legacy ``internal_wiring()``
path before it was deleted; they are the byte-identical reference output.
"""

from schematika.catalog.identifiers import DeviceTag
from schematika.catalog.refs import PinRef
from schematika.project import Project

_HEADER = b"Component From,Pin From,Terminal Tag,Terminal Pin,Component To,Pin To\r\n"


def _emit(project: Project, out_dir) -> bytes:
    project._build_all_circuits()
    project._resolve_field_devices()
    project._resolve_routes()
    project._emit_system_csv(str(out_dir))
    return (out_dir / "system_terminals.csv").read_bytes()


def test_route_two_point_matches_frozen_csv(tmp_path):
    routed = (
        Project()
        .route(
            PinRef(device=DeviceTag("X1"), port_id="1"),
            PinRef(device=DeviceTag("X2"), port_id="1"),
        )
        .use_native_terminal_emit()
    )

    assert _emit(routed, tmp_path) == _HEADER + b",,X1,1,X2,1\r\n"


def test_route_multipoint_decomposes_anchored_on_first_endpoint(tmp_path):
    routed = (
        Project()
        .route(
            PinRef(device=DeviceTag("X1"), port_id="1"),
            PinRef(device=DeviceTag("X2"), port_id="1"),
            PinRef(device=DeviceTag("X3"), port_id="1"),
        )
        .use_native_terminal_emit()
    )

    assert _emit(routed, tmp_path) == _HEADER + b",,X1,1,X2,1\r\n,,X2,1,X3,1\r\n"
