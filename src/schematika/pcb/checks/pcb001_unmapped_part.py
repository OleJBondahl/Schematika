"""PCB001: unmapped (floating) part check."""

from typing import Any

from schematika.pcb.findings import Finding, FindingLocation, Severity
from schematika.pcb.model import PCBBuildResult, SymbolMapping


def check(
    result: PCBBuildResult,
    circuit: Any,  # noqa: ANN401, ARG001
    mapping: SymbolMapping,  # noqa: ARG001
) -> tuple[Finding, ...]:
    """Return one Finding per FloatingPart in result.floating_parts.

    Args:
        result: PCBBuildResult from build().
        circuit: SKiDL circuit IR (unused).
        mapping: SymbolMapping config (unused).

    Returns:
        Tuple of ERROR Findings, one per floating part.
    """
    return tuple(
        Finding(
            code="PCB001",
            severity=Severity.ERROR,
            message=f"Part {fp.part_ref!r} is not reachable from any connector.",
            location=FindingLocation(part_ref=fp.part_ref),
        )
        for fp in result.floating_parts
    )


CHECKS = (check,)
