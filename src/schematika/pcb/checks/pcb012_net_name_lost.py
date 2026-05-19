"""PCB012: verbatim net name preservation (stub — always returns empty)."""

from typing import Any

from schematika.pcb.findings import Finding
from schematika.pcb.model import PCBBuildResult, SymbolMapping


def check(
    result: PCBBuildResult,  # noqa: ARG001
    circuit: Any,  # noqa: ANN401, ARG001
    mapping: SymbolMapping,  # noqa: ARG001
) -> tuple[Finding, ...]:
    """Stub check for net name preservation — always returns no findings.

    Args:
        result: PCBBuildResult from build() (unused).
        circuit: SKiDL circuit IR (unused).
        mapping: SymbolMapping config (unused).

    Returns:
        Empty tuple (this check is enforced via tests, not runtime logic).
    """
    return ()


CHECKS = (check,)
