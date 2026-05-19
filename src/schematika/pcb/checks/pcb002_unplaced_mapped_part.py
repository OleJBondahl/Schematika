"""PCB002: mapped part with no placed slice and not floating."""

from typing import Any

from schematika.pcb.adapter import template_name
from schematika.pcb.findings import Finding, FindingLocation, Severity
from schematika.pcb.model import PCBBuildResult, SymbolMapping


def check(
    result: PCBBuildResult,
    circuit: Any,  # noqa: ANN401
    mapping: SymbolMapping,
) -> tuple[Finding, ...]:
    """Return ERROR for each mapped part that is neither placed nor floating.

    Args:
        result: PCBBuildResult from build().
        circuit: SKiDL circuit IR; returns () if None.
        mapping: SymbolMapping config.

    Returns:
        Tuple of ERROR Findings for unplaced mapped parts.
    """
    if circuit is None:
        return ()

    mapped_template_names = {template_name(sm.template) for sm in mapping.symbols}

    placed_refs: set[str] = set()
    for block in result.connector_blocks:
        for pc in block.pin_columns:
            for col in pc.columns:
                for slc in col.slices:
                    placed_refs.add(slc.part_ref)

    floating_refs = {fp.part_ref for fp in result.floating_parts}

    findings: list[Finding] = []
    for part in circuit.parts:
        part_tname = getattr(part, "template_name", None)
        if part_tname not in mapped_template_names:
            continue
        ref = part.ref
        if ref not in placed_refs and ref not in floating_refs:
            findings.append(
                Finding(
                    code="PCB002",
                    severity=Severity.ERROR,
                    message=(
                        f"Part {ref!r} is mapped but not placed and not floating."
                    ),
                    location=FindingLocation(part_ref=ref),
                )
            )
    return tuple(findings)


CHECKS = (check,)
