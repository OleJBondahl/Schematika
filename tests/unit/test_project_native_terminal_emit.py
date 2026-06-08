"""C3b-1: Project.use_native_terminal_emit() yields a byte-identical terminal CSV."""

from typing import Any

from schematika.electrical.builder import BuildResult
from schematika.electrical.builder_models import BridgeMode
from schematika.electrical.system.connection_registry import log_connection
from schematika.electrical.system.system import Circuit
from schematika.electrical.terminal import Terminal
from schematika.project import Project


def _circuit_fn(state: Any, **_kwargs: Any) -> BuildResult:
    # Prefixed terminal pins (L1:1, L1:2), a normal sequential terminal, and a
    # PLC-prefixed terminal that the system CSV must filter out.
    state = log_connection(state, "X1", "L1:1", "K1", "A1", "top")
    state = log_connection(state, "X1", "L1:2", "K2", "A1", "top")
    state = log_connection(state, "X1", "L1:1", "M1", "U", "bottom")
    state = log_connection(state, "X2", "1", "K1", "A2", "top")
    state = log_connection(state, "X2", "2", "K2", "A2", "bottom")
    state = log_connection(state, "X3", "1", "K3", "A1", "top")
    state = log_connection(state, "X3", "2", "K4", "A1", "bottom")
    state = log_connection(state, "PLC:DO", "1", "K1", "13", "top")
    return BuildResult(
        state=state,
        circuit=Circuit(),
        used_terminals=["X1", "X2", "X3"],
        bridge_groups={"X3": [(1, 2)]},
    )


def _build_project() -> Project:
    p = Project()
    p.terminals(
        Terminal("X1", bridge=BridgeMode.PER_PREFIX),
        Terminal("X2", bridge=BridgeMode.ALL),
    )
    p.add_circuit("c1", _circuit_fn)
    p.external_connections([("FIELD1", "1", "X2", "1", "CBL1", "1")])
    p.internal_wiring([("X1", "L1:1", "X2", "2", "", "")])
    return p


def test_native_terminal_csv_byte_identical_to_legacy(tmp_path):
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    native_dir = tmp_path / "native"
    native_dir.mkdir()

    p_legacy = _build_project()
    p_legacy._build_all_circuits()
    p_legacy._resolve_field_devices()
    p_legacy._resolve_routes()
    p_legacy._generate_system_csv(str(legacy_dir))

    p_native = _build_project().use_native_terminal_emit()
    p_native._build_all_circuits()
    p_native._resolve_field_devices()
    p_native._resolve_routes()
    p_native._emit_system_csv(str(native_dir))

    assert (native_dir / "system_terminals.csv").read_bytes() == (
        legacy_dir / "system_terminals.csv"
    ).read_bytes()
