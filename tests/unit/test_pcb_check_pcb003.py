"""Tests for PCB003: part placed on multiple pages."""

from schematika.core.geometry import Point, Vector
from schematika.core.symbol import Port, Symbol
from schematika.pcb.builder import create_initial_state
from schematika.pcb.checks.pcb003_part_on_multiple_pages import check
from schematika.pcb.findings import Severity
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


def _make_block(connector_ref: str, part_ref: str) -> ConnectorBlock:
    sym = _two_port_symbol()
    placed = PlacedSlice(
        part_ref=part_ref,
        slice_index=0,
        symbol=sym,
        pins=(
            PinPlacement(pin_id="1", port_name="top"),
            PinPlacement(pin_id="2", port_name="bottom"),
        ),
    )
    col = Column(slices=(placed,), terminator=Terminator.NC)
    pc = PinColumns(pin_id="1", columns=(col,))
    return ConnectorBlock(
        connector_ref=connector_ref, functional_label=None, pin_columns=(pc,)
    )


def _good_result() -> PCBBuildResult:
    # Same part on only one page → no findings
    block_j1 = _make_block("J1", "F1")
    return PCBBuildResult(
        state=create_initial_state(),
        connector_blocks=(block_j1,),
        pages=(Page(title="Page 1", placements=(("J1", 0.0),)),),
    )


def _bad_result() -> PCBBuildResult:
    # Same part F1 on two different pages via two blocks
    block_j1 = _make_block("J1", "F1")
    block_j2 = _make_block("J2", "F1")
    return PCBBuildResult(
        state=create_initial_state(),
        connector_blocks=(block_j1, block_j2),
        pages=(
            Page(title="Page 1", placements=(("J1", 0.0),)),
            Page(title="Page 2", placements=(("J2", 0.0),)),
        ),
    )


def test_pcb003_no_finding_when_good() -> None:
    findings = check(_good_result(), circuit=None, mapping=_mapping())
    assert findings == ()


def test_pcb003_finding_when_bad() -> None:
    findings = check(_bad_result(), circuit=None, mapping=_mapping())
    assert len(findings) == 1
    f = findings[0]
    assert f.code == "PCB003"
    assert f.severity == Severity.ERROR
    assert f.location.part_ref == "F1"


def _make_block_with_slice(
    connector_ref: str, part_ref: str, slice_index: int
) -> ConnectorBlock:
    sym = _two_port_symbol()
    placed = PlacedSlice(
        part_ref=part_ref,
        slice_index=slice_index,
        symbol=sym,
        pins=(
            PinPlacement(pin_id="1", port_name="top"),
            PinPlacement(pin_id="2", port_name="bottom"),
        ),
    )
    col = Column(slices=(placed,), terminator=Terminator.NC)
    pc = PinColumns(pin_id="1", columns=(col,))
    return ConnectorBlock(
        connector_ref=connector_ref, functional_label=None, pin_columns=(pc,)
    )


def test_pcb003_no_finding_when_different_slices_on_different_pages() -> None:
    """Different slices of the same part on different pages must NOT fire PCB003."""
    block_j1 = _make_block_with_slice("J1", "K1", 0)  # K1 slice 0 on page 1
    block_j2 = _make_block_with_slice("J2", "K1", 1)  # K1 slice 1 on page 2
    result = PCBBuildResult(
        state=create_initial_state(),
        connector_blocks=(block_j1, block_j2),
        pages=(
            Page(title="Page 1", placements=(("J1", 0.0),)),
            Page(title="Page 2", placements=(("J2", 0.0),)),
        ),
    )
    findings = check(result, circuit=None, mapping=_mapping())
    assert findings == (), f"Expected no findings for different slices; got {findings}"
