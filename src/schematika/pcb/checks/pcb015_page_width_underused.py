"""PCB015 — flags pages that broke before being fully utilised.

For every page that is followed by another page, this check verifies that
adding the next page's first block to the current page would have overflowed
the available width. If it would have fit, the page break was premature and
the check emits a WARNING.
"""

from schematika.pcb.findings import Finding, FindingLocation, Severity
from schematika.pcb.model import PCBBuildResult, SymbolMapping

CODE = "PCB015"


def check(
    result: PCBBuildResult,
    circuit=None,  # noqa: ANN001, ARG001
    mapping: SymbolMapping | None = None,
) -> tuple[Finding, ...]:
    """Return WARNING for each page with premature break.

    Args:
        result: PCBBuildResult from build().
        circuit: SKiDL circuit IR (unused).
        mapping: SymbolMapping config (unused).

    Returns:
        Tuple of WARNING Findings for pages that broke before full width utilization.
    """
    if mapping is None:
        mapping = SymbolMapping(symbols=(), connectors=(), power_nets=())

    findings: list[Finding] = []
    layout = result.layout
    page_size = result.page_size
    available_width = page_size[0] - 2 * layout.page_left_margin_mm

    by_ref = {b.connector_ref: b for b in result.connector_blocks}

    def block_width(ref: str) -> float:
        """Calculate the rendered width of a connector block."""
        b = by_ref.get(ref)
        if b is None:
            return 0.0
        return 2 * layout.side_padding_mm + len(b.pin_columns) * layout.pin_spacing_mm

    for i, page in enumerate(result.pages[:-1]):
        if not page.placements:
            continue
        last_ref, last_x = page.placements[-1]
        used = last_x + block_width(last_ref)

        next_page = result.pages[i + 1]
        if not next_page.placements:
            continue
        next_first_ref = next_page.placements[0][0]
        next_first_w = block_width(next_first_ref)

        if used + layout.inter_block_gap_mm + next_first_w <= available_width:
            findings.append(
                Finding(
                    code=CODE,
                    severity=Severity.WARNING,
                    message=(
                        f"Page {i + 1} broke prematurely: "
                        f"first block of page {i + 2} ({next_first_ref}, "
                        f"{next_first_w}mm) would have fit (used={used}mm + gap "
                        f"+ {next_first_w}mm <= {available_width}mm available)"
                    ),
                    location=FindingLocation(page_title=page.title),
                )
            )
    return tuple(findings)


CHECKS = (check,)
