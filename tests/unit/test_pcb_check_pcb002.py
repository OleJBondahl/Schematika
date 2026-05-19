"""Tests for PCB002: mapped part with no placed slice and not floating."""

from types import SimpleNamespace

from schematika.core.geometry import Point, Vector
from schematika.core.symbol import Port, Symbol
from schematika.pcb.adapter import CircuitIR, PartRef
from schematika.pcb.builder import create_initial_state
from schematika.pcb.checks.pcb002_unplaced_mapped_part import check
from schematika.pcb.findings import Severity
from schematika.pcb.model import (
    ConnectorMap,
    FloatingPart,
    PCBBuildResult,
    SymbolMap,
    SymbolMapping,
    SymbolSlice,
)

# ---------------------------------------------------------------------------
# Shared stubs
# ---------------------------------------------------------------------------

_conn_template = type(
    "conn_2p",
    (),
    {"name": "conn_2p", "pins": [SimpleNamespace(num="1"), SimpleNamespace(num="2")]},
)()

_fuse_template = type(
    "fuse",
    (),
    {"name": "fuse", "pins": [SimpleNamespace(num="1"), SimpleNamespace(num="2")]},
)()


def _fuse_symbol() -> Symbol:
    return Symbol(
        elements=[],
        ports={
            "top": Port("1", Point(0, 0), Vector(0, 1)),
            "bottom": Port("2", Point(0, -1), Vector(0, -1)),
        },
        label="fuse",
    )


def _mapping_with_fuse() -> SymbolMapping:
    fuse_slice = SymbolSlice(symbol=_fuse_symbol, pin_map={"1": "top", "2": "bottom"})
    return SymbolMapping(
        symbols=(SymbolMap(template=_fuse_template, slices=(fuse_slice,)),),
        connectors=(ConnectorMap(template=_conn_template),),
        power_nets=(),
    )


def _mapping_empty() -> SymbolMapping:
    return SymbolMapping(symbols=(), connectors=(), power_nets=())


def _empty_result() -> PCBBuildResult:
    return PCBBuildResult(
        state=create_initial_state(),
        connector_blocks=(),
        floating_parts=(),
    )


def _circuit_with_fuse(ref: str = "F1") -> CircuitIR:
    return CircuitIR(
        parts=(PartRef(ref=ref, template_name="fuse", pin_numbers=("1", "2")),),
        nets=(),
        nc_pins=(),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_pcb002_no_finding_when_circuit_none() -> None:
    findings = check(_empty_result(), circuit=None, mapping=_mapping_empty())
    assert findings == ()


def test_pcb002_no_finding_when_no_symbol_maps() -> None:
    # No SymbolMaps → no mapped templates → no findings even if part exists
    circuit = _circuit_with_fuse()
    findings = check(_empty_result(), circuit=circuit, mapping=_mapping_empty())
    assert findings == ()


def test_pcb002_no_finding_when_part_floating() -> None:
    # Part matches mapped template but is in floating_parts → no PCB002
    circuit = _circuit_with_fuse("F1")
    result = PCBBuildResult(
        state=create_initial_state(),
        connector_blocks=(),
        floating_parts=(FloatingPart(part_ref="F1"),),
    )
    findings = check(result, circuit=circuit, mapping=_mapping_with_fuse())
    assert findings == ()


def test_pcb002_finding_when_mapped_and_unplaced() -> None:
    circuit = _circuit_with_fuse("F1")
    findings = check(_empty_result(), circuit=circuit, mapping=_mapping_with_fuse())
    assert len(findings) == 1
    f = findings[0]
    assert f.code == "PCB002"
    assert f.severity == Severity.ERROR
    assert f.location.part_ref == "F1"
