"""Stub builder — full implementation arrives in Phase 2 of the pcb rewrite."""

from typing import Any

from schematika.core.state import create_initial_state

from .errors import PCBBuildError
from .model import PCBBuildResult, SymbolMapping

__all__ = ["build", "create_initial_state"]


def build(
    circuit: Any,  # noqa: ANN401
    mapping: SymbolMapping,
    **_kwargs: Any,  # noqa: ANN401
) -> PCBBuildResult:
    """Build a PCB-style schematic from a SKiDL circuit and a SymbolMapping.

    This stub raises ``PCBBuildError`` while the v2 algorithm is being
    implemented in Phase 2 of the pcb rewrite. The signature is the
    public contract; Phase 2 fills in the body.

    Args:
        circuit: A SKiDL ``Circuit`` to render. Currently unused — the
            stub raises before reading it.
        mapping: A ``SymbolMapping`` describing which SKiDL templates
            map to which schematika symbols. Currently unused.

    Returns:
        A ``PCBBuildResult`` with the rendered connector blocks and
        page assignments. Phase 2 returns a real result.

    Raises:
        PCBBuildError: Always, until Phase 2 lands.

    Examples:
        >>> from schematika.pcb.builder import build  # doctest: +SKIP
        >>> result = build(circuit, mapping)  # doctest: +SKIP
    """
    del circuit, mapping
    msg = "schematika.pcb.build is being rewritten — Phase 2 not yet complete"
    raise PCBBuildError(msg)
