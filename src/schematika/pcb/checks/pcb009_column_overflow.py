"""PCB009: column exceeds max_symbols_per_column."""

from typing import Any

from schematika.pcb.findings import Finding, FindingLocation, Severity
from schematika.pcb.model import PCBBuildResult, SymbolMapping


def check(
    result: PCBBuildResult,
    circuit: Any,  # noqa: ANN401, ARG001
    mapping: SymbolMapping,
) -> tuple[Finding, ...]:
    """Return WARNING for each column that exceeds max_symbols_per_column.

    Args:
        result: PCBBuildResult from build().
        circuit: SKiDL circuit IR (unused).
        mapping: SymbolMapping config; reads max_symbols_per_column (default 2).

    Returns:
        Tuple of WARNING Findings for overflowing columns.
    """
    max_sym: int = getattr(mapping, "max_symbols_per_column", 2)
    return tuple(
        Finding(
            code="PCB009",
            severity=Severity.WARNING,
            message=(
                f"Column in block {block.connector_ref!r} has "
                f"{len(col.slices)} slices (max {max_sym})."
            ),
            location=FindingLocation(connector_block_ref=block.connector_ref),
        )
        for block in result.connector_blocks
        for pc in block.pin_columns
        for col in pc.columns
        if len(col.slices) > max_sym
    )


CHECKS = (check,)
