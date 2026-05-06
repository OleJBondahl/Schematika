"""PCB-style schematic builder — v2 connector-anchored implementation."""

from typing import Any

from schematika.core.state import create_initial_state

from .adapter import adapt
from .layout_spec import LayoutSpec
from .model import PCBBuildResult, SymbolMapping
from .walk import build_connector_blocks, find_floating_parts, pack_pages

__all__ = ["build", "create_initial_state"]


def build(
    circuit: Any,  # noqa: ANN401
    mapping: SymbolMapping,
    *,
    page_size: tuple[float, float] = (250.0, 297.0),
    max_symbols_per_column: int = 2,
    strict_net_names: bool = True,
    layout: LayoutSpec | None = None,
) -> PCBBuildResult:
    """Build a PCB-style schematic from a SKiDL circuit and a SymbolMapping.

    Args:
        circuit: A SKiDL ``Circuit`` to render.
        mapping: A ``SymbolMapping`` describing symbol/connector/power-net mappings.
        page_size: ``(width_mm, height_mm)`` of the target page. Defaults to A4-ish.
        max_symbols_per_column: Cap on placed slices per column before a
            CONTINUATION split. Defaults to 2.
        strict_net_names: If True, raises on multi-pin nets without a name.
            Defaults to True.
        layout: Optional ``LayoutSpec`` overriding default spacing/margins. If
            None, ``LayoutSpec()`` is used.

    Returns:
        A frozen ``PCBBuildResult``.

    Examples:
        >>> from schematika.pcb.builder import build  # doctest: +SKIP
        >>> result = build(circuit, mapping)  # doctest: +SKIP
    """
    if layout is None:
        layout = LayoutSpec()
    ir = adapt(circuit)
    blocks, ownership = build_connector_blocks(
        ir,
        mapping,
        max_symbols_per_column=max_symbols_per_column,
        strict_net_names=strict_net_names,
    )
    floating = find_floating_parts(ir, mapping, ownership)
    blocks, pages = pack_pages(
        blocks,
        floating,
        page_size,
        layout,
        ir=ir,
        mapping=mapping,
        slice_ownership=ownership,
    )
    return PCBBuildResult(
        state=create_initial_state(),
        connector_blocks=blocks,
        floating_parts=floating,
        pages=pages,
        mapping=mapping,
        layout=layout,
        max_symbols_per_column=max_symbols_per_column,
        page_size=page_size,
        ir=ir,
    )
