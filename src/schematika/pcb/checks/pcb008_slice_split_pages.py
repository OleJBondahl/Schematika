"""PCB008: same slice of a part placed on multiple pages."""

from collections import defaultdict
from typing import Any

from schematika.pcb.findings import Finding, FindingLocation, Severity
from schematika.pcb.model import PCBBuildResult, SymbolMapping


def check(
    result: PCBBuildResult,
    circuit: Any,  # noqa: ANN401, ARG001
    mapping: SymbolMapping,  # noqa: ARG001
) -> tuple[Finding, ...]:
    """Return ERROR for each (part_ref, slice_index) that lands on more than one page.

    Different slices of the same part on different pages is allowed (each slice
    is an independent schematic unit). Only duplicate placement of the exact same
    slice is an error.

    Args:
        result: PCBBuildResult from build().
        circuit: SKiDL circuit IR (unused).
        mapping: SymbolMapping config (unused).

    Returns:
        Tuple of ERROR Findings for slices placed on multiple pages.
    """
    # Map block_ref → page title
    block_page: dict[str, str] = {}
    for page in result.pages:
        for block_ref, _ in page.placements:
            block_page[block_ref] = page.title

    # Accumulate page titles per (part_ref, slice_index)
    slice_page_titles: dict[tuple[str, int], set[str]] = defaultdict(set)
    for block in result.connector_blocks:
        page_title = block_page.get(block.connector_ref, "<unassigned>")
        for pc in block.pin_columns:
            for col in pc.columns:
                for slc in col.slices:
                    slice_page_titles[(slc.part_ref, slc.slice_index)].add(page_title)

    return tuple(
        Finding(
            code="PCB008",
            severity=Severity.ERROR,
            message=(
                f"Part {part_ref!r} slice {slice_index} is placed on multiple pages:"
                f" {sorted(pages)}."
            ),
            location=FindingLocation(part_ref=part_ref),
        )
        for (part_ref, slice_index), pages in slice_page_titles.items()
        if len(pages) > 1
    )


CHECKS = (check,)
