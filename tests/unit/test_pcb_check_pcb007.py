"""Tests for PCB007: connector fragmented across multiple blocks."""

from schematika.core.geometry import Point, Vector
from schematika.core.symbol import Port, Symbol
from schematika.pcb.builder import create_initial_state
from schematika.pcb.checks.pcb007_connector_fragmented import check
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


def _empty_block(connector_ref: str) -> ConnectorBlock:
    sym = _two_port_symbol()
    placed = PlacedSlice(
        part_ref="F1",
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
    return PCBBuildResult(
        state=create_initial_state(),
        connector_blocks=(
            _empty_block("J1"),
            _empty_block("J2"),
        ),
    )


def _bad_result() -> PCBBuildResult:
    # J1 appears twice
    return PCBBuildResult(
        state=create_initial_state(),
        connector_blocks=(
            _empty_block("J1"),
            _empty_block("J1"),
        ),
    )


def test_pcb007_no_finding_when_good() -> None:
    findings = check(_good_result(), circuit=None, mapping=_mapping())
    assert findings == ()


def test_pcb007_finding_when_connector_duplicated() -> None:
    findings = check(_bad_result(), circuit=None, mapping=_mapping())
    assert len(findings) == 1
    f = findings[0]
    assert f.code == "PCB007"
    assert f.severity == Severity.ERROR
    assert f.location.connector_block_ref == "J1"
