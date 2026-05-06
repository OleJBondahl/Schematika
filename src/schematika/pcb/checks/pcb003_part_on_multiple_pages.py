"""PCB003: same slice placed on multiple pages."""

from collections import defaultdict
from typing import Any

from schematika.pcb.findings import Finding, FindingLocation, Severity
from schematika.pcb.model import PCBBuildResult, SymbolMapping


def check(
    result: PCBBuildResult,
    circuit: Any,  # noqa: ANN401, ARG001
    mapping: SymbolMapping,  # noqa: ARG001
) -> tuple[Finding, ...]:
    """Return ERROR for each (part_ref, slice_index) that appears on more than one page.

    Args:
        result: PCBBuildResult from build().
        circuit: SKiDL circuit IR (unused).
        mapping: SymbolMapping config (unused).

    Returns:
        Tuple of ERROR Findings, one per (part_ref, slice_index) on multiple pages.
    """
    block_by_ref = {b.connector_ref: b for b in result.connector_blocks}
    slice_pages: dict[tuple[str, int], list[str]] = defaultdict(list)

    for page in result.pages:
        for block_ref, _, _ in page.placements:
            block = block_by_ref.get(block_ref)
            if block is None:
                continue
            for pc in block.pin_columns:
                for col in pc.columns:
                    for slc in col.slices:
                        slice_pages[(slc.part_ref, slc.slice_index)].append(page.title)

    findings: list[Finding] = []
    for (part_ref, slice_index), pages in slice_pages.items():
        if len(set(pages)) > 1:
            findings.append(
                Finding(
                    code="PCB003",
                    severity=Severity.ERROR,
                    message=(
                        f"Part {part_ref!r} slice {slice_index}"
                        f" placed on multiple pages: {sorted(set(pages))}."
                    ),
                    location=FindingLocation(part_ref=part_ref),
                )
            )
    return tuple(findings)


CHECKS = (check,)
