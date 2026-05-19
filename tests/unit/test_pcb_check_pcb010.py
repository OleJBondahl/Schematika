"""Tests for PCB010: cross-block CHAIN label missing on one end."""

from schematika.core.geometry import Point, Vector
from schematika.core.symbol import Port, Symbol
from schematika.pcb.adapter import CircuitIR, NetRef, PinRef
from schematika.pcb.builder import create_initial_state
from schematika.pcb.checks.pcb010_crossblock_label_missing import check
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


def _chain_net(name: str) -> NetRef:
    return NetRef(
        name=name,
        pins=(
            PinRef(part_ref="F1", pin_name="1"),
            PinRef(part_ref="F2", pin_name="2"),
        ),
    )


def test_pcb010_no_finding_when_circuit_none() -> None:
    result = PCBBuildResult(state=create_initial_state(), connector_blocks=())
    findings = check(result, circuit=None, mapping=_mapping())
    assert findings == ()


def test_pcb010_no_finding_when_label_on_both_ends() -> None:
    # Label appears twice (once per block) → both ends have labels
    block_j1 = _make_block("J1", "F1", Terminator.LABEL, "CHAIN_NET")
    block_j2 = _make_block("J2", "F2", Terminator.LABEL, "CHAIN_NET")
    result = PCBBuildResult(
        state=create_initial_state(),
        connector_blocks=(block_j1, block_j2),
    )
    circuit = CircuitIR(parts=(), nets=(_chain_net("/CHAIN_NET"),), nc_pins=())
    findings = check(result, circuit=circuit, mapping=_mapping())
    assert findings == ()


def test_pcb010_finding_when_label_only_on_one_end() -> None:
    # Label appears exactly once → one end is missing
    block_j1 = _make_block("J1", "F1", Terminator.LABEL, "CHAIN_NET")
    block_j2 = _make_block("J2", "F2", Terminator.NC, None)
    result = PCBBuildResult(
        state=create_initial_state(),
        connector_blocks=(block_j1, block_j2),
    )
    circuit = CircuitIR(parts=(), nets=(_chain_net("/CHAIN_NET"),), nc_pins=())
    findings = check(result, circuit=circuit, mapping=_mapping())
    assert len(findings) == 1
    f = findings[0]
    assert f.code == "PCB010"
    assert f.severity == Severity.WARNING
    assert f.location.net_name == "/CHAIN_NET"


def test_pcb010_preserves_leading_slash() -> None:
    block_j1 = _make_block("J1", "F1", Terminator.LABEL, "v24")
    block_j2 = _make_block("J2", "F2", Terminator.NC, None)
    result = PCBBuildResult(
        state=create_initial_state(),
        connector_blocks=(block_j1, block_j2),
    )
    circuit = CircuitIR(parts=(), nets=(_chain_net("/v24"),), nc_pins=())
    findings = check(result, circuit=circuit, mapping=_mapping())
    assert len(findings) == 1
    assert findings[0].location.net_name == "/v24"
    assert findings[0].location.net_name.startswith("/")
