"""Tests for PCB004: dropped 1-pin net not marked NC."""

from schematika.pcb.adapter import CircuitIR, NetRef, PinRef
from schematika.pcb.builder import create_initial_state
from schematika.pcb.checks.pcb004_dropped_net import check
from schematika.pcb.findings import Severity
from schematika.pcb.model import PCBBuildResult, SymbolMapping


def _mapping() -> SymbolMapping:
    return SymbolMapping(symbols=(), connectors=(), power_nets=())


def _result() -> PCBBuildResult:
    return PCBBuildResult(state=create_initial_state(), connector_blocks=())


def _one_pin_net(name: str, part_ref: str = "F1", pin_name: str = "1") -> NetRef:
    return NetRef(name=name, pins=(PinRef(part_ref=part_ref, pin_name=pin_name),))


def _two_pin_net(name: str) -> NetRef:
    return NetRef(
        name=name,
        pins=(
            PinRef(part_ref="F1", pin_name="1"),
            PinRef(part_ref="J1", pin_name="1"),
        ),
    )


def test_pcb004_no_finding_when_circuit_none() -> None:
    findings = check(_result(), circuit=None, mapping=_mapping())
    assert findings == ()


def test_pcb004_no_finding_on_two_pin_net() -> None:
    circuit = CircuitIR(parts=(), nets=(_two_pin_net("/CHAIN"),), nc_pins=())
    findings = check(_result(), circuit=circuit, mapping=_mapping())
    assert findings == ()


def test_pcb004_no_finding_when_nc_pin() -> None:
    # 1-pin net but (part_ref, pin_name) is in nc_set
    circuit = CircuitIR(
        parts=(),
        nets=(_one_pin_net("/NC_NET", "F1", "1"),),
        nc_pins=(("F1", "1"),),
    )
    findings = check(_result(), circuit=circuit, mapping=_mapping())
    assert findings == ()


def test_pcb004_finding_on_dropped_net() -> None:
    circuit = CircuitIR(
        parts=(),
        nets=(_one_pin_net("/DROPPED"),),
        nc_pins=(),
    )
    findings = check(_result(), circuit=circuit, mapping=_mapping())
    assert len(findings) == 1
    f = findings[0]
    assert f.code == "PCB004"
    assert f.severity == Severity.WARNING
    assert f.location.net_name == "/DROPPED"


def test_pcb004_preserves_leading_slash() -> None:
    circuit = CircuitIR(
        parts=(),
        nets=(_one_pin_net("/v24"),),
        nc_pins=(),
    )
    findings = check(_result(), circuit=circuit, mapping=_mapping())
    assert len(findings) == 1
    assert findings[0].location.net_name == "/v24"
    assert findings[0].location.net_name.startswith("/")
