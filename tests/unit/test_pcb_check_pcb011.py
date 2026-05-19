"""Tests for PCB011: NC pin rendered as label instead of dropped."""

from schematika.core.geometry import Point, Vector
from schematika.core.symbol import Port, Symbol
from schematika.pcb.adapter import CircuitIR, NetRef, PinRef
from schematika.pcb.builder import create_initial_state
from schematika.pcb.checks.pcb011_nc_labelled import check
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


def _make_block_with_label(label: str) -> ConnectorBlock:
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
    col = Column(slices=(placed,), terminator=Terminator.LABEL, terminator_label=label)
    pc = PinColumns(pin_id="1", columns=(col,))
    return ConnectorBlock(connector_ref="J1", functional_label=None, pin_columns=(pc,))


def _nc_net(name: str) -> NetRef:
    return NetRef(
        name=name,
        pins=(PinRef(part_ref="F1", pin_name="1"),),
    )


def test_pcb011_no_finding_when_circuit_none() -> None:
    result = PCBBuildResult(state=create_initial_state(), connector_blocks=())
    findings = check(result, circuit=None, mapping=_mapping())
    assert findings == ()


def test_pcb011_no_finding_when_no_nc_pins() -> None:
    circuit = CircuitIR(parts=(), nets=(_nc_net("/NC_NET"),), nc_pins=())
    result = PCBBuildResult(state=create_initial_state(), connector_blocks=())
    findings = check(result, circuit=circuit, mapping=_mapping())
    assert findings == ()


def test_pcb011_no_finding_when_nc_net_not_labelled() -> None:
    circuit = CircuitIR(
        parts=(),
        nets=(_nc_net("/NC_NET"),),
        nc_pins=(("F1", "1"),),
    )
    result = PCBBuildResult(state=create_initial_state(), connector_blocks=())
    findings = check(result, circuit=circuit, mapping=_mapping())
    assert findings == ()


def test_pcb011_finding_when_nc_net_is_labelled() -> None:
    circuit = CircuitIR(
        parts=(),
        nets=(_nc_net("/NC_NET"),),
        nc_pins=(("F1", "1"),),
    )
    block = _make_block_with_label("NC_NET")
    result = PCBBuildResult(state=create_initial_state(), connector_blocks=(block,))
    findings = check(result, circuit=circuit, mapping=_mapping())
    assert len(findings) == 1
    f = findings[0]
    assert f.code == "PCB011"
    assert f.severity == Severity.ERROR
    assert f.location.net_name == "/NC_NET"


def test_pcb011_preserves_leading_slash() -> None:
    circuit = CircuitIR(
        parts=(),
        nets=(_nc_net("/v24"),),
        nc_pins=(("F1", "1"),),
    )
    block = _make_block_with_label("v24")
    result = PCBBuildResult(state=create_initial_state(), connector_blocks=(block,))
    findings = check(result, circuit=circuit, mapping=_mapping())
    assert len(findings) == 1
    assert findings[0].location.net_name == "/v24"
    assert findings[0].location.net_name.startswith("/")
