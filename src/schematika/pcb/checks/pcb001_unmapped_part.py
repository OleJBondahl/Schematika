"""PCB001: unmapped (floating) part check."""

from typing import Any

from schematika.pcb.findings import Finding, FindingLocation, Severity
from schematika.pcb.model import PCBBuildResult, SymbolMapping


def check(
    result: PCBBuildResult,
    circuit: Any,  # noqa: ANN401, ARG001
    mapping: SymbolMapping,  # noqa: ARG001
) -> tuple[Finding, ...]:
    """Return one Finding per FloatingPart with NO slice placed in any ConnectorBlock.

    Partially-placed parts (where at least one slice IS in a connector block) are
    excluded — their unowned slices appear on the floating page and are guarded by
    PCB017, not here.

    Args:
        result: PCBBuildResult from build().
        circuit: SKiDL circuit IR (unused).
        mapping: SymbolMapping config (unused).

    Returns:
        Tuple of ERROR Findings, one per fully-unowned floating part.
    """
    placed_refs: set[str] = set()
    for block in result.connector_blocks:
        for pc in block.pin_columns:
            for col in pc.columns:
                for slc in col.slices:
                    placed_refs.add(slc.part_ref)

    return tuple(
        Finding(
            code="PCB001",
            severity=Severity.ERROR,
            message=f"Part {fp.part_ref!r} is not reachable from any connector.",
            location=FindingLocation(part_ref=fp.part_ref),
        )
        for fp in result.floating_parts
        if fp.part_ref not in placed_refs
    )


CHECKS = (check,)
