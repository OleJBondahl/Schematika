"""Stub review() — full implementation in Phase 3."""

from typing import Any

from .model import PCBBuildResult, SymbolMapping


def review(
    result: PCBBuildResult,
    circuit: Any,  # noqa: ANN401
    mapping: SymbolMapping,
) -> list:
    """Review a PCBBuildResult for consistency and best-practice violations.

    This stub returns an empty findings list while the v2 review engine is
    being implemented in Phase 3 of the pcb rewrite. The signature is the
    public contract; Phase 3 fills in the body.

    Args:
        result: A ``PCBBuildResult`` containing the rendered connector blocks
            and page assignments. Currently unused — the stub returns before
            reading it.
        circuit: A SKiDL ``Circuit`` used to render the result. Currently unused.
        mapping: A ``SymbolMapping`` describing which SKiDL templates map to
            which schematika symbols. Currently unused.

    Returns:
        A list of ``Finding`` objects detailing any violations or warnings
        found in the result. The stub always returns an empty list until
        Phase 3 lands.

    Examples:
        >>> from schematika.pcb.review import review  # doctest: +SKIP
        >>> findings = review(result, circuit, mapping)  # doctest: +SKIP
        >>> assert findings == []  # doctest: +SKIP
    """
    del result, circuit, mapping
    return []
