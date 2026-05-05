"""PCB-style schematic builder — v2 connector-anchored implementation."""

from typing import Any

from schematika.core.state import create_initial_state

from .adapter import adapt
from .model import PCBBuildResult, SymbolMapping
from .walk import build_connector_blocks, find_floating_parts, pack_pages

__all__ = ["build", "create_initial_state"]


def build(
    circuit: Any,  # noqa: ANN401
    mapping: SymbolMapping,
    *,
    page_size: tuple[float, float] = (250.0, 297.0),
    column_spacing_mm: float = 32.0,
    max_symbols_per_column: int = 2,
    strict_net_names: bool = True,
) -> PCBBuildResult:
    """Build a PCB-style schematic from a SKiDL circuit and a SymbolMapping.

    Adapts the SKiDL circuit to internal IR, walks each connector pin to
    assemble ConnectorBlocks, collects unreachable parts as floating, then
    packs everything into pages with a greedy first-fit algorithm.

    Args:
        circuit: A SKiDL ``Circuit`` to render (duck-typed: must expose
            ``parts``, ``nets``, and ``NC``).
        mapping: A ``SymbolMapping`` describing which SKiDL templates map to
            which schematika symbols.
        page_size: ``(width_mm, height_mm)`` of the target schematic page.
            Defaults to A4 landscape-ish (250 x 297 mm).
        column_spacing_mm: Width of one symbol column in mm. Drives both the
            block-width measurement and the inter-block gap. Defaults to 32 mm.
        max_symbols_per_column: Hard cap on placed slices per column before a
            CONTINUATION split is inserted. Defaults to 2.
        strict_net_names: If True, raises ``UnnamedNetError`` for any
            multi-pin net without an explicit name. Defaults to True.

    Returns:
        A frozen ``PCBBuildResult`` containing the initial layout state,
        connector blocks, floating parts, and page assignments.

    Raises:
        UnnamedNetError: If ``strict_net_names`` is True and a net has no name.

    Examples:
        >>> from schematika.pcb.builder import build  # doctest: +SKIP
        >>> result = build(circuit, mapping)  # doctest: +SKIP
    """
    ir = adapt(circuit)
    blocks, ownership = build_connector_blocks(
        ir,
        mapping,
        max_symbols_per_column=max_symbols_per_column,
        strict_net_names=strict_net_names,
    )
    floating = find_floating_parts(ir, mapping, ownership)
    pages = pack_pages(blocks, floating, page_size, column_spacing_mm)
    return PCBBuildResult(
        state=create_initial_state(),
        connector_blocks=blocks,
        floating_parts=floating,
        pages=pages,
    )
