"""review() returns empty list on a trivial empty mapping; Finding round-trips JSON."""

import json

from schematika.pcb import review
from schematika.pcb.builder import create_initial_state
from schematika.pcb.findings import Finding, FindingLocation, Severity
from schematika.pcb.model import PCBBuildResult, SymbolMapping


def test_review_returns_list_of_findings() -> None:
    result = PCBBuildResult(
        state=create_initial_state(),
        connector_blocks=(),
        floating_parts=(),
        pages=(),
    )
    mapping = SymbolMapping(symbols=(), connectors=(), power_nets=())
    findings = review(result, circuit=None, mapping=mapping)
    assert findings == []


def test_finding_serialises_to_json() -> None:
    f = Finding(
        code="PCB001",
        severity=Severity.ERROR,
        message="example",
        location=FindingLocation(part_ref="K1"),
    )
    payload = f.to_dict()
    json.dumps(payload)
    assert payload["code"] == "PCB001"
    assert payload["severity"] == "error"
