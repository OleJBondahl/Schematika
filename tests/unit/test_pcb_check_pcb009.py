"""Tests for PCB009: column exceeds max_symbols_per_column."""

from schematika.core.geometry import Point, Vector
from schematika.core.symbol import Port, Symbol
from schematika.pcb.builder import create_initial_state
from schematika.pcb.checks.pcb009_column_overflow import check
from schematika.pcb.findings import Severity
from schematika.pcb.model import (
    Column,
    ConnectorBlock,
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


def _make_block_with_n_slices(n: int) -> ConnectorBlock:
    slices = tuple(_make_placed(f"F{i}", i) for i in range(n))
    col = Column(slices=slices, terminator=Terminator.NC)
    pc = PinColumns(pin_id="1", columns=(col,))
    return ConnectorBlock(connector_ref="J1", functional_label=None, pin_columns=(pc,))


def test_pcb009_no_finding_within_limit() -> None:
    # 2 slices, default max is 2
    block = _make_block_with_n_slices(2)
    result = PCBBuildResult(state=create_initial_state(), connector_blocks=(block,))
    findings = check(result, circuit=None, mapping=_mapping())
    assert findings == ()


def test_pcb009_finding_when_overflow() -> None:
    # 3 slices, default max is 2
    block = _make_block_with_n_slices(3)
    result = PCBBuildResult(state=create_initial_state(), connector_blocks=(block,))
    findings = check(result, circuit=None, mapping=_mapping())
    assert len(findings) == 1
    f = findings[0]
    assert f.code == "PCB009"
    assert f.severity == Severity.WARNING
    assert f.location.connector_block_ref == "J1"
