"""Tests for PCB006: power net rendered without power symbol."""

from schematika.core.geometry import Point, Vector
from schematika.core.symbol import Port, Symbol
from schematika.pcb.builder import create_initial_state
from schematika.pcb.checks.pcb006_power_not_rendered import check
from schematika.pcb.findings import Severity
from schematika.pcb.model import (
    Column,
    ConnectorBlock,
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


def _power_symbol() -> Symbol:
    return Symbol(
        elements=[],
        ports={"pwr": Port("1", Point(0, 0), Vector(0, 1))},
        label="+24V",
    )


def _make_block(
    connector_ref: str, terminator: Terminator, label: str | None
) -> ConnectorBlock:
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
    col = Column(slices=(placed,), terminator=terminator, terminator_label=label)
    pc = PinColumns(pin_id="1", columns=(col,))
    return ConnectorBlock(
        connector_ref=connector_ref, functional_label=None, pin_columns=(pc,)
    )


def _mapping_with_power() -> SymbolMapping:
    return SymbolMapping(
        symbols=(),
        connectors=(),
        power_nets=(PowerNetMap(canonical_name="+24V", symbol=_power_symbol),),
    )


def _mapping_empty() -> SymbolMapping:
    return SymbolMapping(symbols=(), connectors=(), power_nets=())


def test_pcb006_no_finding_when_no_power_nets() -> None:
    block = _make_block("J1", Terminator.LABEL, "+24V")
    result = PCBBuildResult(state=create_initial_state(), connector_blocks=(block,))
    findings = check(result, circuit=None, mapping=_mapping_empty())
    assert findings == ()


def test_pcb006_no_finding_when_power_terminator_correct() -> None:
    block = _make_block("J1", Terminator.POWER, "+24V")
    result = PCBBuildResult(state=create_initial_state(), connector_blocks=(block,))
    findings = check(result, circuit=None, mapping=_mapping_with_power())
    assert findings == ()


def test_pcb006_finding_when_power_label_without_power_terminator() -> None:
    block = _make_block("J1", Terminator.LABEL, "+24V")
    result = PCBBuildResult(state=create_initial_state(), connector_blocks=(block,))
    findings = check(result, circuit=None, mapping=_mapping_with_power())
    assert len(findings) == 1
    f = findings[0]
    assert f.code == "PCB006"
    assert f.severity == Severity.ERROR
    assert f.location.connector_block_ref == "J1"
