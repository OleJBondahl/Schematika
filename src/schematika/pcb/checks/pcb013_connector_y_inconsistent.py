"""PCB013 — connector Y baseline must be consistent across a page.

Every connector block on every page should render with its anchor body's
top edge at ``layout.vertical_margin_mm``. Catches accidental per-block Y
overrides.
"""

from typing import Any

from schematika.core.primitives import Polygon
from schematika.pcb.findings import Finding, FindingLocation, Severity
from schematika.pcb.model import PCBBuildResult, SymbolMapping
from schematika.pcb.render import render_connector_block


def check(
    result: PCBBuildResult,
    circuit=None,  # noqa: ANN001, ARG001
    mapping: SymbolMapping | None = None,
) -> tuple[Finding, ...]:
    """Return ERROR for each connector block with inconsistent Y baseline.

    Args:
        result: PCBBuildResult from build().
        circuit: SKiDL circuit IR (unused).
        mapping: SymbolMapping config (unused).

    Returns:
        Tuple of ERROR Findings for blocks with misaligned Y baseline.
    """
    if mapping is None:
        mapping = SymbolMapping(symbols=(), connectors=(), power_nets=())

    findings: list[Finding] = []
    expected_y = result.layout.vertical_margin_mm
    by_ref = {b.connector_ref: b for b in result.connector_blocks}

    for page_idx, page in enumerate(result.pages):
        for ref, origin_x in page.placements:
            block = by_ref.get(ref)
            if block is None:
                continue

            # Render the block at the expected position
            circuit_rendered = render_connector_block(
                block,
                mapping,
                origin_x_mm=origin_x,
                origin_y_mm=expected_y,
                layout=result.layout,
            )

            # Extract the anchor symbol (first symbol in the rendered circuit)
            if not circuit_rendered.symbols:
                continue

            anchor = circuit_rendered.symbols[0]

            # The anchor is a Polygon at elements[0]
            if not anchor.elements:
                continue

            poly: Any = anchor.elements[0]
            # Get the minimum Y coordinate (top edge) of the polygon
            if not isinstance(poly, Polygon):
                continue

            top_y = min(p.y for p in poly.points)

            # Check if the top edge is at the expected Y position
            tolerance = 1e-6
            if abs(top_y - expected_y) > tolerance:
                findings.append(
                    Finding(
                        code="PCB013",
                        severity=Severity.ERROR,
                        message=(
                            f"Page {page_idx + 1}: {ref} anchor top Y {top_y:.2f} "
                            f"!= expected {expected_y:.2f}"
                        ),
                        location=FindingLocation(
                            page_title=page.title,
                            connector_block_ref=ref,
                        ),
                    )
                )

    return tuple(findings)


CHECKS = (check,)
