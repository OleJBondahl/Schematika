"""schematika.pcb.review - rule linter over the build result.

Each check lives in its own module under schematika.pcb.checks/.
review.py imports them explicitly and assembles ALL_CHECKS deterministically
- no global registration list, no decorator magic, no import-order surprises.

Tasks 3.2-3.13 add per-check modules and extend ALL_CHECKS.
"""

from collections.abc import Callable
from typing import Any

from schematika.pcb.adapter import adapt as _adapt_circuit
from schematika.pcb.checks import (
    pcb001_unmapped_part,
    pcb002_unplaced_mapped_part,
    pcb003_part_on_multiple_pages,
    pcb004_dropped_net,
    pcb005_chain_not_rendered,
    pcb006_power_not_rendered,
    pcb007_connector_fragmented,
    pcb008_slice_split_pages,
    pcb009_column_overflow,
    pcb010_crossblock_label_missing,
    pcb011_nc_labelled,
    pcb012_net_name_lost,
    pcb013_connector_y_inconsistent,
)
from schematika.pcb.findings import Finding
from schematika.pcb.model import PCBBuildResult, SymbolMapping

Check = Callable[[PCBBuildResult, Any, SymbolMapping], tuple[Finding, ...]]

# ALL_CHECKS is the ordered tuple of check functions. Extended as each check
# module is created (Tasks 3.2-3.13).
ALL_CHECKS: tuple[Check, ...] = (
    *pcb001_unmapped_part.CHECKS,
    *pcb002_unplaced_mapped_part.CHECKS,
    *pcb003_part_on_multiple_pages.CHECKS,
    *pcb004_dropped_net.CHECKS,
    *pcb005_chain_not_rendered.CHECKS,
    *pcb006_power_not_rendered.CHECKS,
    *pcb007_connector_fragmented.CHECKS,
    *pcb008_slice_split_pages.CHECKS,
    *pcb009_column_overflow.CHECKS,
    *pcb010_crossblock_label_missing.CHECKS,
    *pcb011_nc_labelled.CHECKS,
    *pcb012_net_name_lost.CHECKS,
    *pcb013_connector_y_inconsistent.CHECKS,
)


def _ensure_ir(circuit: Any) -> Any:  # noqa: ANN401
    """Return ``circuit`` if it already has IR shape; otherwise adapt() it.

    Detection: an IR's parts have a ``template_name`` attribute (str).
    A raw SKiDL Circuit's parts have a ``template`` attribute (class). If
    ``circuit`` is None or has no parts, return as-is (no-op for checks).
    """
    if circuit is None:
        return None
    parts = getattr(circuit, "parts", None)
    if not parts:
        return circuit  # empty — no-op regardless of shape
    if hasattr(parts[0], "template_name"):
        return circuit  # already IR
    return _adapt_circuit(circuit)


def review(
    result: PCBBuildResult,
    circuit: Any,  # noqa: ANN401
    mapping: SymbolMapping,
) -> list[Finding]:
    """Run all registered checks against the build result.

    Args:
        result: A PCBBuildResult from `schematika.pcb.build()`.
        circuit: The original SKiDL circuit (passed through to checks that need it).
        mapping: The SymbolMapping used at build time.

    Returns:
        A list of Finding records, in registration order.

    Examples:
        >>> from schematika.pcb import build, review  # doctest: +SKIP
        >>> result = build(circuit, mapping)  # doctest: +SKIP
        >>> findings = review(result, circuit, mapping)  # doctest: +SKIP
    """
    ir = _ensure_ir(circuit)
    findings: list[Finding] = []
    for check in ALL_CHECKS:
        findings.extend(check(result, ir, mapping))
    return findings
