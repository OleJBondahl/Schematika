"""PCB007: connector fragmented across multiple blocks."""

from collections import Counter
from typing import Any

from schematika.pcb.findings import Finding, FindingLocation, Severity
from schematika.pcb.model import PCBBuildResult, SymbolMapping


def check(
    result: PCBBuildResult,
    circuit: Any,  # noqa: ANN401, ARG001
    mapping: SymbolMapping,  # noqa: ARG001
) -> tuple[Finding, ...]:
    """Return ERROR for each connector_ref that appears in more than one ConnectorBlock.

    Args:
        result: PCBBuildResult from build().
        circuit: SKiDL circuit IR (unused).
        mapping: SymbolMapping config (unused).

    Returns:
        Tuple of ERROR Findings, one per fragmented connector.
    """
    counts = Counter(b.connector_ref for b in result.connector_blocks)
    return tuple(
        Finding(
            code="PCB007",
            severity=Severity.ERROR,
            message=(f"Connector {ref!r} in {count} blocks; must appear in exactly 1."),
            location=FindingLocation(connector_block_ref=ref),
        )
        for ref, count in counts.items()
        if count > 1
    )


CHECKS = (check,)
