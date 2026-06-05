"""C3a: terminal_csv_rows reproduces the legacy terminal CSV byte-for-byte."""

from pathlib import Path

from schematika.catalog.identifiers import DeviceTag, NetId
from schematika.catalog.refs import PinRef
from schematika.catalog.wires import Wire
from schematika.core.connection_registry import Connection, TerminalRegistry
from schematika.core.state import GenerationState
from schematika.electrical.system.connection_registry import export_registry_to_csv
from schematika.electrical.terminal_emit import terminal_csv_rows
from schematika.electrical.terminal_sidecar import TerminalSidecar, TerminalWireFact
from schematika.electrical.utils.export_utils import finalize_terminal_csv


def _wire(comp: str, cpin: str, term: str, tpin: str) -> Wire:
    return Wire(
        net=NetId(f"{comp}_{cpin}"),
        source=PinRef(device=DeviceTag(comp), port_id=cpin),
        target=PinRef(device=DeviceTag(term), port_id=tpin),
    )


def test_panel_parity_simple(tmp_path: Path) -> None:
    conns = [
        Connection("X1", "1", "K1", "A1", "top"),
        Connection("X1", "1", "M1", "U", "bottom"),
        Connection("X1", "2", "K1", "A2", "top"),
    ]
    legacy_csv = str(tmp_path / "legacy.csv")
    export_registry_to_csv(TerminalRegistry(tuple(conns)), legacy_csv, state=None)
    finalize_terminal_csv(
        legacy_csv, bridge_defs=None, prefix_bridge_tags=None, external_connections=None
    )

    wires = (
        _wire("K1", "A1", "X1", "1"),
        _wire("M1", "U", "X1", "1"),
        _wire("K1", "A2", "X1", "2"),
    )
    sidecar = TerminalSidecar(
        facts=(
            TerminalWireFact(anchor="target", side="top"),
            TerminalWireFact(anchor="target", side="bottom"),
            TerminalWireFact(anchor="target", side="top"),
        ),
        allocated_pin_keys=(("X1", "1"), ("X1", "2")),
        bridge_defs={},
        prefix_bridge_tags=frozenset(),
    )
    native_csv = str(tmp_path / "native.csv")
    terminal_csv_rows(wires, sidecar, external_rows=[], csv_path=native_csv)

    assert Path(native_csv).read_text(encoding="utf-8") == Path(legacy_csv).read_text(
        encoding="utf-8"
    )


def test_panel_parity_with_bridge_gap_fill(tmp_path: Path) -> None:
    """Pin 2 is a gap between connected pins 1 and 3.

    With state=None, legacy writes only connected pins, then gap-fill adds pin 2
    after bridges are applied → pin 2 gets no bridge value.  The native path with
    allocated_pin_keys containing only the connected pins reproduces this exactly.
    """
    conns = [
        Connection("X1", "1", "K1", "A1", "top"),
        Connection("X1", "3", "K2", "A1", "top"),
    ]
    legacy_csv = str(tmp_path / "legacy.csv")
    export_registry_to_csv(TerminalRegistry(tuple(conns)), legacy_csv, state=None)
    finalize_terminal_csv(
        legacy_csv,
        bridge_defs={"X1": "all"},
        prefix_bridge_tags=None,
        external_connections=None,
    )

    wires = (_wire("K1", "A1", "X1", "1"), _wire("K2", "A1", "X1", "3"))
    # allocated_pin_keys holds only the connected pins — pin 2 is not allocated
    # via state counters in this scenario, so it is a pure gap-fill pin.
    sidecar = TerminalSidecar(
        facts=(
            TerminalWireFact(anchor="target", side="top"),
            TerminalWireFact(anchor="target", side="top"),
        ),
        allocated_pin_keys=(("X1", "1"), ("X1", "3")),
        bridge_defs={"X1": "all"},
        prefix_bridge_tags=frozenset(),
    )
    native_csv = str(tmp_path / "native.csv")
    terminal_csv_rows(wires, sidecar, external_rows=[], csv_path=native_csv)

    assert Path(native_csv).read_text(encoding="utf-8") == Path(legacy_csv).read_text(
        encoding="utf-8"
    )


def test_panel_parity_allocated_beyond_max_connected(tmp_path: Path) -> None:
    """Allocated pins beyond the highest connected pin get placeholder rows pre-bridge.

    Legacy: state.terminal_counters["X1"]=3, only pins 1 and 3 have connections.
    _build_all_pin_keys enumerates 1,2,3 → pin 2 is a gap written as placeholder
    BEFORE finalize_terminal_csv, so update_csv_with_internal_connections sees it
    and assigns bridge="1".

    Native: allocated_pin_keys=(1,2,3) includes the unconnected pin 2 so it is
    pre-written as a placeholder before finalize_terminal_csv runs.  Both paths
    must produce an identical CSV with bridge="1" on all three pins.
    """
    conns = [
        Connection("X1", "1", "K1", "A1", "top"),
        Connection("X1", "3", "K2", "A1", "top"),
    ]
    state = GenerationState(terminal_counters={"X1": 3})
    legacy_csv = str(tmp_path / "legacy.csv")
    export_registry_to_csv(TerminalRegistry(tuple(conns)), legacy_csv, state=state)
    finalize_terminal_csv(
        legacy_csv,
        bridge_defs={"X1": "all"},
        prefix_bridge_tags=None,
        external_connections=None,
    )

    wires = (_wire("K1", "A1", "X1", "1"), _wire("K2", "A1", "X1", "3"))
    # allocated_pin_keys mirrors state.terminal_counters["X1"]=3 → pins 1,2,3
    sidecar = TerminalSidecar(
        facts=(
            TerminalWireFact(anchor="target", side="top"),
            TerminalWireFact(anchor="target", side="top"),
        ),
        allocated_pin_keys=(("X1", "1"), ("X1", "2"), ("X1", "3")),
        bridge_defs={"X1": "all"},
        prefix_bridge_tags=frozenset(),
    )
    native_csv = str(tmp_path / "native.csv")
    terminal_csv_rows(wires, sidecar, external_rows=[], csv_path=native_csv)

    assert Path(native_csv).read_text(encoding="utf-8") == Path(legacy_csv).read_text(
        encoding="utf-8"
    )


def test_anchor_source_terminal_to_terminal(tmp_path: Path) -> None:
    wire = Wire(
        net=NetId("n"),
        source=PinRef(device=DeviceTag("EXT_24V"), port_id="1"),
        target=PinRef(device=DeviceTag("FUSED_24V"), port_id=""),
    )
    sidecar = TerminalSidecar(
        facts=(TerminalWireFact(anchor="source", side="bottom"),),
        allocated_pin_keys=(("EXT_24V", "1"),),
        bridge_defs={},
        prefix_bridge_tags=frozenset(),
    )
    csv_path = str(tmp_path / "anchor.csv")
    terminal_csv_rows((wire,), sidecar, external_rows=[], csv_path=csv_path)
    text = Path(csv_path).read_text(encoding="utf-8")
    assert "EXT_24V" in text
    lines = [ln for ln in text.splitlines() if "EXT_24V,1" in ln]
    assert any("FUSED_24V" in ln for ln in lines)
