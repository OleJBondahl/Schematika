"""Tests for PCB012: verbatim net name preservation."""

from schematika.core.geometry import Point, Vector
from schematika.core.symbol import Port, Symbol
from schematika.pcb.adapter import CircuitIR, NetRef, PinRef
from schematika.pcb.builder import create_initial_state
from schematika.pcb.checks.pcb004_dropped_net import check as check_pcb004
from schematika.pcb.checks.pcb005_chain_not_rendered import check as check_pcb005
from schematika.pcb.checks.pcb010_crossblock_label_missing import check as check_pcb010
from schematika.pcb.checks.pcb011_nc_labelled import check as check_pcb011
from schematika.pcb.findings import Finding, FindingLocation, Severity
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


def _make_block(
    connector_ref: str, part_ref: str, terminator: Terminator, label: str | None
) -> ConnectorBlock:
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
    col = Column(slices=(placed,), terminator=terminator, terminator_label=label)
    pc = PinColumns(pin_id="1", columns=(col,))
    return ConnectorBlock(
        connector_ref=connector_ref, functional_label=None, pin_columns=(pc,)
    )


def test_finding_location_preserves_leading_slash() -> None:
    f = Finding(
        code="PCB005",
        severity=Severity.ERROR,
        message="test",
        location=FindingLocation(net_name="/v24"),
    )
    assert f.location.net_name == "/v24"
    assert f.location.net_name.startswith("/")


def test_pcb004_emitted_finding_preserves_leading_slash() -> None:
    circuit = CircuitIR(
        parts=(),
        nets=(NetRef(name="/v24", pins=(PinRef(part_ref="F1", pin_name="1"),)),),
        nc_pins=(),
    )
    result = PCBBuildResult(state=create_initial_state(), connector_blocks=())
    findings = check_pcb004(result, circuit=circuit, mapping=_mapping())
    assert len(findings) == 1
    assert findings[0].location.net_name == "/v24"
    assert findings[0].location.net_name.startswith("/")


def test_pcb005_emitted_finding_preserves_leading_slash() -> None:
    block_f1 = _make_block("J1", "F1", Terminator.NC, None)
    block_f2 = _make_block("J2", "F2", Terminator.NC, None)
    result = PCBBuildResult(
        state=create_initial_state(),
        connector_blocks=(block_f1, block_f2),
    )
    circuit = CircuitIR(
        parts=(),
        nets=(
            NetRef(
                name="/v24",
                pins=(
                    PinRef(part_ref="F1", pin_name="1"),
                    PinRef(part_ref="F2", pin_name="2"),
                ),
            ),
        ),
        nc_pins=(),
    )
    findings = check_pcb005(result, circuit=circuit, mapping=_mapping())
    assert len(findings) == 1
    assert findings[0].location.net_name == "/v24"
    assert findings[0].location.net_name.startswith("/")


def test_pcb010_emitted_finding_preserves_leading_slash() -> None:
    block_j1 = _make_block("J1", "F1", Terminator.LABEL, "v24")
    block_j2 = _make_block("J2", "F2", Terminator.NC, None)
    result = PCBBuildResult(
        state=create_initial_state(),
        connector_blocks=(block_j1, block_j2),
    )
    circuit = CircuitIR(
        parts=(),
        nets=(
            NetRef(
                name="/v24",
                pins=(
                    PinRef(part_ref="F1", pin_name="1"),
                    PinRef(part_ref="F2", pin_name="2"),
                ),
            ),
        ),
        nc_pins=(),
    )
    findings = check_pcb010(result, circuit=circuit, mapping=_mapping())
    assert len(findings) == 1
    assert findings[0].location.net_name == "/v24"
    assert findings[0].location.net_name.startswith("/")


def test_pcb011_emitted_finding_preserves_leading_slash() -> None:
    circuit = CircuitIR(
        parts=(),
        nets=(NetRef(name="/v24", pins=(PinRef(part_ref="F1", pin_name="1"),)),),
        nc_pins=(("F1", "1"),),
    )
    block = _make_block("J1", "F1", Terminator.LABEL, "v24")
    result = PCBBuildResult(state=create_initial_state(), connector_blocks=(block,))
    findings = check_pcb011(result, circuit=circuit, mapping=_mapping())
    assert len(findings) == 1
    assert findings[0].location.net_name == "/v24"
    assert findings[0].location.net_name.startswith("/")
