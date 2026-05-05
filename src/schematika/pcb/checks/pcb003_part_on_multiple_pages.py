"""PCB003: part placed on multiple pages."""

from collections import defaultdict
from typing import Any

from schematika.pcb.findings import Finding, FindingLocation, Severity
from schematika.pcb.model import PCBBuildResult, SymbolMapping


def check(
    result: PCBBuildResult,
    circuit: Any,  # noqa: ANN401, ARG001
    mapping: SymbolMapping,  # noqa: ARG001
) -> tuple[Finding, ...]:
    """Return ERROR for each part_ref that appears on more than one page.

    Args:
        result: PCBBuildResult from build().
        circuit: SKiDL circuit IR (unused).
        mapping: SymbolMapping config (unused).

    Returns:
        Tuple of ERROR Findings, one per part_ref found on multiple pages.
    """
    block_by_ref = {b.connector_ref: b for b in result.connector_blocks}
    part_pages: dict[str, list[str]] = defaultdict(list)

    for page in result.pages:
        for block_ref, _ in page.placements:
            block = block_by_ref.get(block_ref)
            if block is None:
                continue
            for pc in block.pin_columns:
                for col in pc.columns:
                    for slc in col.slices:
                        part_pages[slc.part_ref].append(page.title)

    findings: list[Finding] = []
    for part_ref, pages in part_pages.items():
        if len(set(pages)) > 1:
            findings.append(
                Finding(
                    code="PCB003",
                    severity=Severity.ERROR,
                    message=(
                        f"Part {part_ref!r} placed on multiple pages:"
                        f" {sorted(set(pages))}."
                    ),
                    location=FindingLocation(part_ref=part_ref),
                )
            )
    return tuple(findings)


CHECKS = (check,)
