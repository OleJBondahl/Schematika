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


def test_review_adapts_raw_skidl_like_circuit() -> None:
    """review() should adapt a raw-SKiDL-shaped circuit before passing to checks.

    A raw SKiDL part has `.template` (class), not `.template_name` (str). The
    review() function detects this and adapts before dispatching.
    """
    from types import SimpleNamespace

    # Build a raw-SKiDL-shaped circuit with one part that has .template (not .template_name)
    fake_template = type("conn_2p", (), {"__name__": "conn_2p"})
    raw_part = SimpleNamespace(
        ref="J1",
        name="conn_2p",
        description=None,
        pins=(SimpleNamespace(num="1"), SimpleNamespace(num="2")),
        template=fake_template,
    )
    raw_circuit = SimpleNamespace(
        parts=(raw_part,), nets=(), NC=SimpleNamespace(pins=())
    )

    result = PCBBuildResult(
        state=create_initial_state(),
        connector_blocks=(),
        floating_parts=(),
        pages=(),
    )
    mapping = SymbolMapping(symbols=(), connectors=(), power_nets=())

    findings = review(result, raw_circuit, mapping)
    # No findings expected — empty mapping has nothing to check.
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
