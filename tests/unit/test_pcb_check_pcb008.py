"""Tests for PCB008: multi-slice part split across pages."""

from schematika.core.geometry import Point, Vector
from schematika.core.symbol import Port, Symbol
from schematika.pcb.builder import create_initial_state
from schematika.pcb.checks.pcb008_slice_split_pages import check
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


def _make_block(
    connector_ref: str, part_ref: str, slice_index: int = 0
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


def _good_result() -> PCBBuildResult:
    # Both slices of K1 on the same page
    block_j1 = _make_block("J1", "K1", 0)
    block_j2 = _make_block("J2", "K1", 1)
    return PCBBuildResult(
        state=create_initial_state(),
        connector_blocks=(block_j1, block_j2),
        pages=(Page(title="Page 1", placements=(("J1", 0.0), ("J2", 30.0))),),
    )


def _bad_result() -> PCBBuildResult:
    # K1 slice 0 on Page 1, slice 1 on Page 2
    block_j1 = _make_block("J1", "K1", 0)
    block_j2 = _make_block("J2", "K1", 1)
    return PCBBuildResult(
        state=create_initial_state(),
        connector_blocks=(block_j1, block_j2),
        pages=(
            Page(title="Page 1", placements=(("J1", 0.0),)),
            Page(title="Page 2", placements=(("J2", 0.0),)),
        ),
    )


def test_pcb008_no_finding_when_good() -> None:
    findings = check(_good_result(), circuit=None, mapping=_mapping())
    assert findings == ()


def test_pcb008_finding_when_slices_split() -> None:
    findings = check(_bad_result(), circuit=None, mapping=_mapping())
    assert len(findings) == 1
    f = findings[0]
    assert f.code == "PCB008"
    assert f.severity == Severity.ERROR
    assert f.location.part_ref == "K1"
