"""Tests for PCB014: autoconnect wire allow-list verification."""

from schematika.core.geometry import Point, Vector
from schematika.core.symbol import Port, Symbol, SymbolFactory
from schematika.pcb.builder import create_initial_state
from schematika.pcb.checks.pcb014_autoconnect_violation import check
from schematika.pcb.layout_spec import LayoutSpec
from schematika.pcb.model import (
    Column,
    ConnectorBlock,
    Page,
    PCBBuildResult,
    PinColumns,
    PinPlacement,
    PlacedSlice,
    PowerNetMap,
    SymbolMapping,
    Terminator,
)


def _two_port_symbol() -> Symbol:
    return Symbol(
        elements=[],
        ports={
            "top": Port("1", Point(0, 0), Vector(0, 1)),
            "bottom": Port("2", Point(0, -1), Vector(0, -1)),
        },
        label="part",
    )


def _one_port_symbol() -> Symbol:
    return Symbol(
        elements=[],
        ports={
            "p": Port("1", Point(0, 0), Vector(0, 1)),
        },
        label="power",
    )


def _make_placed(part_ref: str, slice_index: int = 0) -> PlacedSlice:
    return PlacedSlice(
        part_ref=part_ref,
        slice_index=slice_index,
        symbol=_two_port_symbol(),
        pins=(
            PinPlacement(pin_id="1", port_name="top"),
            PinPlacement(pin_id="2", port_name="bottom"),
        ),
    )


def _make_result(
    block: ConnectorBlock, mapping: SymbolMapping | None = None
) -> PCBBuildResult:
    if mapping is None:
        mapping = SymbolMapping(symbols=(), connectors=(), power_nets=())
    layout = LayoutSpec()
    page = Page(title="Page 1", placements=(("J1", 10.0),))
    return PCBBuildResult(
        state=create_initial_state(),
        connector_blocks=(block,),
        pages=(page,),
        mapping=mapping,
        layout=layout,
    )


def test_pcb014_passes_on_clean_render() -> None:
    """1-pin block with 2-slice NC column: renderer emits no autoconnect wires; allow-list is empty."""
    slices = (_make_placed("F1", 0), _make_placed("F1", 1))
    col = Column(slices=slices, terminator=Terminator.NC)
    pc = PinColumns(pin_id="1", columns=(col,))
    block = ConnectorBlock(connector_ref="J1", functional_label=None, pin_columns=(pc,))
    result = _make_result(block)
    findings = check(result)
    assert findings == ()


def test_pcb014_passes_with_no_columns() -> None:
    """1-pin block with zero columns: no wires expected, check is robust."""
    pc = PinColumns(pin_id="1", columns=())
    block = ConnectorBlock(connector_ref="J1", functional_label=None, pin_columns=(pc,))
    result = _make_result(block)
    findings = check(result)
    assert findings == ()


def test_pcb014_passes_on_two_columns_under_same_pin() -> None:
    """1-pin block with 2 columns (NC + NC): no cross-column wire emitted, check passes."""
    slices1 = (_make_placed("F1", 0),)
    col1 = Column(slices=slices1, terminator=Terminator.NC)
    slices2 = (_make_placed("F2", 0),)
    col2 = Column(slices=slices2, terminator=Terminator.NC)
    pc = PinColumns(pin_id="1", columns=(col1, col2))
    block = ConnectorBlock(connector_ref="J1", functional_label=None, pin_columns=(pc,))
    result = _make_result(block)
    findings = check(result)
    assert findings == ()


def test_pcb014_passes_with_power_terminator() -> None:
    """1-pin block, 1 column, 1 slice, POWER terminator: wire to power symbol is in allow-list."""
    power_sym: SymbolFactory = _one_port_symbol
    mapping = SymbolMapping(
        symbols=(),
        connectors=(),
        power_nets=(PowerNetMap(canonical_name="+24V", symbol=power_sym),),
    )
    slices = (_make_placed("F1", 0),)
    col = Column(slices=slices, terminator=Terminator.POWER, terminator_label="+24V")
    pc = PinColumns(pin_id="1", columns=(col,))
    block = ConnectorBlock(connector_ref="J1", functional_label=None, pin_columns=(pc,))
    result = _make_result(block, mapping=mapping)
    findings = check(result)
    assert findings == ()
