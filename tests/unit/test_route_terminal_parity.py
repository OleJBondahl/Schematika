"""R1: route()-declared wiring emits the same native terminal CSV as internal_wiring()."""

from schematika.catalog.identifiers import DeviceTag
from schematika.catalog.refs import PinRef
from schematika.project import Project


def _emit(project: Project, out_dir) -> bytes:
    project._build_all_circuits()
    project._resolve_field_devices()
    project._resolve_routes()
    project._emit_system_csv(str(out_dir))
    return (out_dir / "system_terminals.csv").read_bytes()


def test_route_two_point_matches_internal_wiring(tmp_path):
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    routed_dir = tmp_path / "routed"
    routed_dir.mkdir()

    legacy = (
        Project()
        .internal_wiring([("", "", "X1", "1", "X2", "1")])
        .use_native_terminal_emit()
    )

    routed = (
        Project()
        .route(
            PinRef(device=DeviceTag("X1"), port_id="1"),
            PinRef(device=DeviceTag("X2"), port_id="1"),
        )
        .use_native_terminal_emit()
    )

    assert _emit(legacy, legacy_dir) == _emit(routed, routed_dir)


def test_route_multipoint_decomposes_anchored_on_first_endpoint(tmp_path):
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    routed_dir = tmp_path / "routed"
    routed_dir.mkdir()

    legacy = (
        Project()
        .internal_wiring(
            [("", "", "X1", "1", "X2", "1"), ("", "", "X2", "1", "X3", "1")]
        )
        .use_native_terminal_emit()
    )

    routed = (
        Project()
        .route(
            PinRef(device=DeviceTag("X1"), port_id="1"),
            PinRef(device=DeviceTag("X2"), port_id="1"),
            PinRef(device=DeviceTag("X3"), port_id="1"),
        )
        .use_native_terminal_emit()
    )

    assert _emit(legacy, legacy_dir) == _emit(routed, routed_dir)
