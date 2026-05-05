"""Tests for PCB013: connector Y baseline consistency."""

from schematika.core.geometry import Point, Vector
from schematika.core.symbol import Port, Symbol
from schematika.pcb.builder import create_initial_state
from schematika.pcb.checks.pcb013_connector_y_inconsistent import check
from schematika.pcb.layout_spec import LayoutSpec
from schematika.pcb.model import (
    Column,
    ConnectorBlock,
    Page,
    PCBBuildResult,
    PinColumns,
    PinPlacement,
    PlacedSlice,
    SymbolMapping,
    Terminator,
)


def _mapping() -> SymbolMapping:
    return SymbolMapping(symbols=(), connectors=(), power_nets=())


def _two_port_symbol() -> Symbol:
    return Symbol(
        elements=[],
        ports={
            "top": Port("1", Point(0, 0), Vector(0, 1)),
            "bottom": Port("2", Point(0, -1), Vector(0, -1)),
        },
        label="part",
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


def _make_simple_block(ref: str) -> ConnectorBlock:
    """Create a minimal connector block with one pin and one NC column."""
    slices = (_make_placed("F1", 0),)
    col = Column(slices=slices, terminator=Terminator.NC)
    pc = PinColumns(pin_id="1", columns=(col,))
    return ConnectorBlock(connector_ref=ref, functional_label=None, pin_columns=(pc,))


def test_pcb013_passes_on_clean_layout() -> None:
    """All connector blocks render with anchor top edge at page_top_margin_mm."""
    layout = LayoutSpec()
    block = _make_simple_block("J1")
    page = Page(
        title="Page 1",
        placements=(
            ("J1", 10.0),
        ),  # origin_x at 10.0; origin_y defaults to layout.page_top_margin_mm
    )
    result = PCBBuildResult(
        state=create_initial_state(),
        connector_blocks=(block,),
        pages=(page,),
        mapping=_mapping(),
        layout=layout,
    )
    findings = check(result, circuit=None, mapping=_mapping())
    assert findings == ()


def test_pcb013_passes_with_no_pages() -> None:
    """Empty pages tuple yields no issues."""
    layout = LayoutSpec()
    block = _make_simple_block("J1")
    result = PCBBuildResult(
        state=create_initial_state(),
        connector_blocks=(block,),
        pages=(),
        mapping=_mapping(),
        layout=layout,
    )
    findings = check(result, circuit=None, mapping=_mapping())
    assert findings == ()
