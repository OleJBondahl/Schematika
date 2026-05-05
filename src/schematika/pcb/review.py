"""schematika.pcb.review - rule linter over the build result.

Each check lives in its own module under schematika.pcb.checks/.
review.py imports them explicitly and assembles ALL_CHECKS deterministically
- no global registration list, no decorator magic, no import-order surprises.

Tasks 3.2-3.13 add per-check modules and extend ALL_CHECKS.
"""

from collections.abc import Callable
from typing import Any

from schematika.pcb.findings import Finding
from schematika.pcb.model import PCBBuildResult, SymbolMapping

Check = Callable[[PCBBuildResult, Any, SymbolMapping], tuple[Finding, ...]]

# ALL_CHECKS is the ordered tuple of check functions. Extended as each check
# module is created (Tasks 3.2-3.13).
ALL_CHECKS: tuple[Check, ...] = ()


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
    findings: list[Finding] = []
    for check in ALL_CHECKS:
        findings.extend(check(result, circuit, mapping))
    return findings
