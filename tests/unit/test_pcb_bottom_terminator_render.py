"""Tests for PIN_AT_BOTTOM renderer and PCB010 with PIN_AT_BOTTOM."""

from schematika.core.primitives import Line
from schematika.pcb.builder import create_initial_state
from schematika.pcb.checks.pcb010_crossblock_label_missing import check as pcb010_check
from schematika.pcb.layout_spec import LayoutSpec
from schematika.pcb.model import (
    Column,
    ConnectorBlock,
    PCBBuildResult,
    PinColumns,
    SymbolMapping,
    Terminator,
)
from schematika.pcb.render import render_connector_block

# ---------------------------------------------------------------------------
# Test 1: PIN_AT_BOTTOM renders a wire + connector_pin_small symbol
# ---------------------------------------------------------------------------


def test_pin_at_bottom_renders_wire_and_symbol() -> None:
    """Rendering a PIN_AT_BOTTOM column produces a downward wire and a connector_pin_small."""
    layout = LayoutSpec(bottom_terminator_y_mm=260.0)
    label = "J7:2"
    col = Column(
        slices=(),
        terminator=Terminator.PIN_AT_BOTTOM,
        terminator_label=label,
    )
    pc = PinColumns(pin_id="1", columns=(col,))
    block = ConnectorBlock(connector_ref="J1", functional_label=None, pin_columns=(pc,))

    circuit = render_connector_block(
        block,
        SymbolMapping(symbols=(), connectors=(), power_nets=()),
        origin_x_mm=0.0,
        layout=layout,
    )

    # Check there's a wire that ends at or near bottom_terminator_y_mm
    wires = [e for e in circuit.elements if isinstance(e, Line)]
    bottom_y = layout.bottom_terminator_y_mm
    downward_wire = next(
        (w for w in wires if abs(max(w.start.y, w.end.y) - bottom_y) < 0.1),
        None,
    )
    assert downward_wire is not None, (
        f"Expected a wire reaching y={bottom_y}mm; wires found: "
        f"{[(w.start.y, w.end.y) for w in wires]}"
    )

    # Check there's a connector_pin_small symbol with the label
    syms = list(circuit.symbols)
    label_syms = [s for s in syms if s.label == label]
    assert label_syms, (
        f"Expected connector_pin_small with label {label!r}; symbols: "
        f"{[s.label for s in syms]}"
    )


# ---------------------------------------------------------------------------
# Test 2: PCB010 accepts LABEL + PIN_AT_BOTTOM as a satisfied chain
# ---------------------------------------------------------------------------


def _chain_net(name: str):
    from schematika.pcb.adapter import NetRef, PinRef

    return NetRef(
        name=name,
        pins=(
            PinRef(part_ref="F1", pin_name="1"),
            PinRef(part_ref="F2", pin_name="2"),
        ),
    )


def _block_with_col(connector_ref: str, col: Column) -> ConnectorBlock:
    pc = PinColumns(pin_id="1", columns=(col,))
    return ConnectorBlock(
        connector_ref=connector_ref, functional_label=None, pin_columns=(pc,)
    )


def test_pin_at_bottom_pcb010_resolves() -> None:
    """PCB010 must not flag a chain net that has one LABEL + one PIN_AT_BOTTOM."""
    from schematika.pcb.adapter import CircuitIR

    net_name = "em_stop_chain"
    label_col = Column(
        slices=(),
        terminator=Terminator.LABEL,
        terminator_label=net_name,
        chain_net_name=net_name,
    )
    pin_at_bottom_col = Column(
        slices=(),
        terminator=Terminator.PIN_AT_BOTTOM,
        terminator_label="J7:2",
        chain_net_name=net_name,
    )
    block_j1 = _block_with_col("J1", label_col)
    block_j2 = _block_with_col("J2", pin_at_bottom_col)
    result = PCBBuildResult(
        state=create_initial_state(),
        connector_blocks=(block_j1, block_j2),
    )
    circuit = CircuitIR(
        parts=(),
        nets=(_chain_net(f"/{net_name}"),),
        nc_pins=(),
    )
    findings = pcb010_check(result, circuit=circuit, mapping=_mapping())
    assert findings == (), f"Expected no PCB010 findings, got: {findings}"


def _mapping() -> SymbolMapping:
    return SymbolMapping(symbols=(), connectors=(), power_nets=())
