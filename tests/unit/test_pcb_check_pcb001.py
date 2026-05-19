"""Tests for PCB001: unmapped (floating) part."""

from schematika.pcb.builder import create_initial_state
from schematika.pcb.checks.pcb001_unmapped_part import check
from schematika.pcb.findings import Severity
from schematika.pcb.model import FloatingPart, PCBBuildResult, SymbolMapping


def _mapping() -> SymbolMapping:
    return SymbolMapping(symbols=(), connectors=(), power_nets=())


def _good_result() -> PCBBuildResult:
    return PCBBuildResult(
        state=create_initial_state(),
        connector_blocks=(),
        floating_parts=(),
    )


def _bad_result() -> PCBBuildResult:
    return PCBBuildResult(
        state=create_initial_state(),
        connector_blocks=(),
        floating_parts=(FloatingPart(part_ref="K1"),),
    )


def test_pcb001_no_finding_when_good() -> None:
    findings = check(_good_result(), circuit=None, mapping=_mapping())
    assert findings == ()


def test_pcb001_finding_when_bad() -> None:
    findings = check(_bad_result(), circuit=None, mapping=_mapping())
    assert len(findings) == 1
    f = findings[0]
    assert f.code == "PCB001"
    assert f.severity == Severity.ERROR
    assert f.location.part_ref == "K1"
