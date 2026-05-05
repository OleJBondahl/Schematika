"""Tests for PCB005: CHAIN net not rendered as wire or label."""

from schematika.core.geometry import Point, Vector
from schematika.core.symbol import Port, Symbol
from schematika.pcb.adapter import CircuitIR, NetRef, PinRef
from schematika.pcb.builder import create_initial_state
from schematika.pcb.checks.pcb005_chain_not_rendered import check
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


def _make_block(connector_ref: str, part_ref: str, label: str | None) -> ConnectorBlock:
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
    col = Column(
        slices=(placed,),
        terminator=Terminator.LABEL if label else Terminator.NC,
        terminator_label=label,
    )
    pc = PinColumns(pin_id="1", columns=(col,))
    return ConnectorBlock(
        connector_ref=connector_ref, functional_label=None, pin_columns=(pc,)
    )


def _chain_net(name: str) -> NetRef:
    return NetRef(
        name=name,
        pins=(
            PinRef(part_ref="F1", pin_name="1"),
            PinRef(part_ref="F2", pin_name="2"),
        ),
    )


def test_pcb005_no_finding_when_circuit_none() -> None:
    result = PCBBuildResult(state=create_initial_state(), connector_blocks=())
    findings = check(result, circuit=None, mapping=_mapping())
    assert findings == ()


def test_pcb005_no_finding_when_chain_rendered() -> None:
    # CHAIN net with label rendered in a column
    block_f1 = _make_block("J1", "F1", "CHAIN_NET")
    block_f2 = _make_block("J2", "F2", "CHAIN_NET")
    result = PCBBuildResult(
        state=create_initial_state(),
        connector_blocks=(block_f1, block_f2),
    )
    circuit = CircuitIR(parts=(), nets=(_chain_net("/CHAIN_NET"),), nc_pins=())
    findings = check(result, circuit=circuit, mapping=_mapping())
    assert findings == ()


def test_pcb005_finding_when_chain_not_rendered() -> None:
    # Both parts placed but no label for the CHAIN net
    block_f1 = _make_block("J1", "F1", None)
    block_f2 = _make_block("J2", "F2", None)
    result = PCBBuildResult(
        state=create_initial_state(),
        connector_blocks=(block_f1, block_f2),
    )
    circuit = CircuitIR(parts=(), nets=(_chain_net("/CHAIN_NET"),), nc_pins=())
    findings = check(result, circuit=circuit, mapping=_mapping())
    assert len(findings) == 1
    f = findings[0]
    assert f.code == "PCB005"
    assert f.severity == Severity.ERROR
    assert f.location.net_name == "/CHAIN_NET"


def test_pcb005_preserves_leading_slash() -> None:
    block_f1 = _make_block("J1", "F1", None)
    block_f2 = _make_block("J2", "F2", None)
    result = PCBBuildResult(
        state=create_initial_state(),
        connector_blocks=(block_f1, block_f2),
    )
    circuit = CircuitIR(parts=(), nets=(_chain_net("/v24"),), nc_pins=())
    findings = check(result, circuit=circuit, mapping=_mapping())
    assert len(findings) == 1
    net_name = findings[0].location.net_name
    assert net_name is not None
    assert net_name.startswith("/")
