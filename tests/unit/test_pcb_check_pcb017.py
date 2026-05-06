"""Unit tests for PCB017 — slice and pin completeness."""

from types import SimpleNamespace

from schematika.core.geometry import Point, Vector
from schematika.core.symbol import Port, Symbol
from schematika.pcb.adapter import CircuitIR, PartRef
from schematika.pcb.builder import create_initial_state
from schematika.pcb.checks.pcb017_completeness import check as pcb017_check
from schematika.pcb.findings import Severity
from schematika.pcb.model import (
    Column,
    ConnectorBlock,
    FloatingPart,
    PCBBuildResult,
    PinColumns,
    PinPlacement,
    PlacedSlice,
    SymbolMap,
    SymbolMapping,
    SymbolSlice,
    Terminator,
)

# ---------------------------------------------------------------------------
# Shared stubs
# ---------------------------------------------------------------------------

_conn_template = type(
    "conn_1p",
    (),
    {"name": "conn_1p", "pins": [SimpleNamespace(num="1")]},
)()

_relay_template = type(
    "relay_3slice",
    (),
    {
        "name": "relay_3slice",
        "pins": [
            SimpleNamespace(num="A1"),
            SimpleNamespace(num="A2"),
            SimpleNamespace(num="11"),
            SimpleNamespace(num="14"),
            SimpleNamespace(num="21"),
            SimpleNamespace(num="24"),
        ],
    },
)()


def _sym_factory(label: str = "") -> Symbol:
    return Symbol(
        elements=[],
        ports={
            "top": Port("top", Point(0, -2.5), Vector(0, -1)),
            "bottom": Port("bottom", Point(0, 2.5), Vector(0, 1)),
        },
        label=label or "slice",
    )


def _mapping_with_three_slice_relay() -> SymbolMapping:
    return SymbolMapping(
        symbols=(
            SymbolMap(
                template=_relay_template,
                slices=(
                    SymbolSlice(
                        symbol=_sym_factory, pin_map={"A1": "top", "A2": "bottom"}
                    ),
                    SymbolSlice(
                        symbol=_sym_factory, pin_map={"11": "top", "14": "bottom"}
                    ),
                    SymbolSlice(
                        symbol=_sym_factory, pin_map={"21": "top", "24": "bottom"}
                    ),
                ),
            ),
        ),
        connectors=(),
        power_nets=(),
    )


def _ir_with_k1() -> CircuitIR:
    return CircuitIR(
        parts=(
            PartRef(
                ref="K1",
                template_name="relay_3slice",
                pin_numbers=("A1", "A2", "11", "14", "21", "24"),
            ),
        ),
        nets=(),
        nc_pins=(),
    )


def _placed_slice(part_ref: str, slice_index: int) -> PlacedSlice:
    pin_maps = {
        0: (("A1", "top"), ("A2", "bottom")),
        1: (("11", "top"), ("14", "bottom")),
        2: (("21", "top"), ("24", "bottom")),
    }
    pins = tuple(
        PinPlacement(pin_id=p, port_name=port) for p, port in pin_maps[slice_index]
    )
    return PlacedSlice(
        part_ref=part_ref,
        slice_index=slice_index,
        symbol=_sym_factory(label=part_ref),
        pins=pins,
    )


def _placed_slice_missing_one_pin(
    part_ref: str, slice_index: int, pin_id: str
) -> PlacedSlice:
    """Return a PlacedSlice with only the given pin (omitting the other)."""
    return PlacedSlice(
        part_ref=part_ref,
        slice_index=slice_index,
        symbol=_sym_factory(label=part_ref),
        pins=(PinPlacement(pin_id=pin_id, port_name="top"),),
    )


def _build_result(
    ir: CircuitIR,
    mapping: SymbolMapping,
    placed_slices: list[PlacedSlice],
    floating: tuple[FloatingPart, ...],
) -> PCBBuildResult:
    if placed_slices:
        col = Column(slices=tuple(placed_slices), terminator=Terminator.NC)
        pc = PinColumns(pin_id="1", columns=(col,))
        block = ConnectorBlock(
            connector_ref="J1", functional_label=None, pin_columns=(pc,)
        )
        connector_blocks = (block,)
    else:
        connector_blocks = ()
    return PCBBuildResult(
        state=create_initial_state(),
        connector_blocks=connector_blocks,
        floating_parts=floating,
        mapping=mapping,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_pcb017_passes_when_all_slices_placed() -> None:
    """K1 fully placed (all 3 slices in connector blocks) → no findings."""
    mapping = _mapping_with_three_slice_relay()
    ir = _ir_with_k1()
    placed = [_placed_slice("K1", 0), _placed_slice("K1", 1), _placed_slice("K1", 2)]
    result = _build_result(ir, mapping, placed, ())
    findings = pcb017_check(result, ir, mapping)
    assert findings == ()


def test_pcb017_passes_when_some_slices_floating() -> None:
    """K1 has 1 slice placed, 2 slices in FloatingPart → no findings."""
    mapping = _mapping_with_three_slice_relay()
    ir = _ir_with_k1()
    placed = [_placed_slice("K1", 1)]
    floating = (FloatingPart(part_ref="K1", slice_indices=(0, 2)),)
    result = _build_result(ir, mapping, placed, floating)
    findings = pcb017_check(result, ir, mapping)
    assert findings == ()


def test_pcb017_fires_when_slice_missing_everywhere() -> None:
    """K1 has slice 0 placed, slice 1 placed, slice 2 NEITHER placed nor floating."""
    mapping = _mapping_with_three_slice_relay()
    ir = _ir_with_k1()
    placed = [_placed_slice("K1", 0), _placed_slice("K1", 1)]
    floating = (FloatingPart(part_ref="K1", slice_indices=()),)
    result = _build_result(ir, mapping, placed, floating)
    findings = pcb017_check(result, ir, mapping)
    error_findings = [f for f in findings if f.severity is Severity.ERROR]
    assert len(error_findings) >= 1
    assert any("slice 2" in f.message for f in error_findings)


def test_pcb017_fires_on_dropped_pin() -> None:
    """K1 slice 1 is placed but its pins field has only one of two declared pins."""
    mapping = _mapping_with_three_slice_relay()
    ir = _ir_with_k1()
    placed = [_placed_slice_missing_one_pin("K1", 1, "11")]
    floating = (FloatingPart(part_ref="K1", slice_indices=(0, 2)),)
    result = _build_result(ir, mapping, placed, floating)
    findings = pcb017_check(result, ir, mapping)
    pin_findings = [f for f in findings if "'14'" in f.message]
    assert len(pin_findings) == 1, (
        f"Expected 1 finding for dropped pin '14', got {[f.message for f in findings]}"
    )


def test_pcb017_passes_when_circuit_is_none() -> None:
    """No circuit → check returns ()."""
    mapping = _mapping_with_three_slice_relay()
    result = PCBBuildResult(state=None, connector_blocks=())
    findings = pcb017_check(result, None, mapping)
    assert findings == ()


def test_pcb017_skips_unmapped_parts() -> None:
    """Parts with no SymbolMap (template not in mapping.symbols) emit 0 findings."""
    mapping = SymbolMapping(symbols=(), connectors=(), power_nets=())
    ir = _ir_with_k1()
    result = PCBBuildResult(state=create_initial_state(), connector_blocks=())
    findings = pcb017_check(result, ir, mapping)
    assert findings == ()
