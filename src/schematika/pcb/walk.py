"""Connector-anchored walk algorithm.

This module is the heart of schematika.pcb v2 — it consumes an adapter IR
plus a SymbolMapping and produces tuple[ConnectorBlock, ...] + floating
parts. Subsequent tasks add the actual chain walk; this task only adds the
enumeration helper.
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from schematika.pcb.adapter import template_name
from schematika.pcb.classify import NetKind, classify_net
from schematika.pcb.errors import UnnamedNetError
from schematika.pcb.layout_spec import LayoutSpec
from schematika.pcb.model import (
    Column,
    ConnectorBlock,
    FloatingPart,
    Page,
    PinColumns,
    PinPlacement,
    PlacedSlice,
    SymbolMap,
    SymbolMapping,
    SymbolSlice,
    Terminator,
)

# ---------------------------------------------------------------------------
# Internal accumulator (not exported)
# ---------------------------------------------------------------------------


@dataclass
class _ColumnAccumulator:
    """Mutable column being built during a walk."""

    slices: list[PlacedSlice] = field(default_factory=list)
    terminator: Terminator = Terminator.NC
    terminator_label: str | None = None


def enumerate_connectors(
    ir: Any,  # noqa: ANN401
    mapping: SymbolMapping,
) -> Iterator[Any]:
    """Yield part-IRs whose template is a connector, in declaration order.

    Args:
        ir: Internal representation with a `parts` iterable of part objects,
            each with a `template_name` attribute.
        mapping: SymbolMapping containing registered connector templates.

    Yields:
        Part objects from ir.parts whose template_name matches a registered
        connector template.
    """
    connector_template_names = {template_name(cm.template) for cm in mapping.connectors}
    for part in ir.parts:
        if part.template_name in connector_template_names:
            yield part


# ---------------------------------------------------------------------------
# WalkContext
# ---------------------------------------------------------------------------


@dataclass
class WalkContext:
    """Mutable state threaded through the walk algorithm.

    Attributes:
        ir: CircuitIR produced by the adapter.
        mapping: SymbolMapping with connectors, symbols, and power nets.
        slice_ownership: (part_ref, slice_index) to connector_ref (first-touch wins).
        max_symbols_per_column: Hard cap on slices per column.
        visited_nets: Net names already traversed (cycle guard).
        placed_slices: Slice keys whose slices have already been emitted.
    """

    ir: Any
    mapping: SymbolMapping
    slice_ownership: dict[tuple[str, int], str]
    max_symbols_per_column: int
    visited_nets: set[str] = field(default_factory=set)
    placed_slices: set[tuple[str, int]] = field(default_factory=set)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _net_for_pin(ir: Any, part_ref: str, pin_id: str) -> Any:  # noqa: ANN401
    """Return the NetRef whose pins include (part_ref, pin_id), or None."""
    for net in ir.nets:
        for pin in net.pins:
            if pin.part_ref == part_ref and pin.pin_name == pin_id:
                return net
    return None


def _power_canonical_name(net: Any, mapping: SymbolMapping) -> str:  # noqa: ANN401
    """Return the canonical power name for net, or net.name as fallback."""
    for pnet in mapping.power_nets:
        if pnet.matches(net.name):
            return pnet.canonical_name
    return net.name


def _other_pin_on_chain(net: Any, part_ref: str, pin_id: str) -> Any:  # noqa: ANN401
    """Return the PinRef on net that is NOT (part_ref, pin_id)."""
    for pin in net.pins:
        if not (pin.part_ref == part_ref and pin.pin_name == pin_id):
            return pin
    return None


def _symbol_map_for(part: Any, mapping: SymbolMapping) -> SymbolMap | None:  # noqa: ANN401
    """Return the SymbolMap registered for part.template_name, or None."""
    for smap in mapping.symbols:
        if template_name(smap.template) == part.template_name:
            return smap
    return None


def _resolve_slice(
    smap: SymbolMap,
    pin_id: str,
) -> tuple[int, SymbolSlice] | None:
    """Find which slice contains pin_id. Returns (slice_index, slice) or None."""
    for idx, slc in enumerate(smap.slices):
        if pin_id in slc.pin_map:
            return idx, slc
    return None


def _other_pin_on_slice(slc: SymbolSlice, entry_pin_id: str) -> str | None:
    """For a 2-pin slice, return the other pin id; else None."""
    pins = [p for p in slc.pin_map if p != entry_pin_id]
    if len(pins) == 1:
        return pins[0]
    return None


def _place_slice(part_ref: str, slice_index: int, slc: SymbolSlice) -> PlacedSlice:
    """Instantiate one slice as a PlacedSlice."""
    sym = slc.symbol()
    pins = tuple(
        PinPlacement(pin_id=pn, port_name=port_name)
        for pn, port_name in slc.pin_map.items()
    )
    return PlacedSlice(
        part_ref=part_ref,
        slice_index=slice_index,
        symbol=sym,
        pins=pins,
    )


# ---------------------------------------------------------------------------
# walk_pin
# ---------------------------------------------------------------------------


def _terminator_for_net(
    net: Any,  # noqa: ANN401
    mapping: SymbolMapping,
) -> tuple[Terminator, str | None]:
    """Return (terminator, label) for a net based on its classification."""
    kind = classify_net(net, power_nets=mapping.power_nets)
    if kind is NetKind.POWER:
        return Terminator.POWER, _power_canonical_name(net, mapping)
    if kind is NetKind.LABEL:
        return Terminator.LABEL, net.name.lstrip("/")
    return Terminator.NC, None


def _walk_part_to_completion(  # noqa: PLR0911
    ctx: WalkContext,
    *,
    owning_connector: str,
    entry_part_ref: str,
    entry_pin_id: str,
    entry_net_name: str,
    current_acc: _ColumnAccumulator,
    completed_columns: list[Column],
) -> tuple[Terminator, str | None]:
    """Slice-aware walker: enter at entry_pin's slice, exit at the slice's other pin.

    Places exactly ONE slice (the entry slice) into current_acc, then continues
    the chain via the slice's other pin. Other slices of the same part are NOT
    walked from here; they get their own walks if a separate chain enters them.
    """
    part = next((p for p in ctx.ir.parts if p.ref == entry_part_ref), None)
    if part is None:
        return Terminator.LABEL, entry_net_name.lstrip("/")
    smap = _symbol_map_for(part, ctx.mapping)
    if smap is None:
        return Terminator.LABEL, entry_net_name.lstrip("/")

    resolved = _resolve_slice(smap, entry_pin_id)
    if resolved is None:
        return Terminator.LABEL, entry_net_name.lstrip("/")
    slice_index, entry_slice = resolved
    slice_key = (entry_part_ref, slice_index)

    # Already placed (any prior chain) → cross-reference label, don't duplicate.
    if slice_key in ctx.placed_slices:
        return Terminator.LABEL, entry_net_name.lstrip("/")
    existing_owner = ctx.slice_ownership.get(slice_key)
    if existing_owner is not None and existing_owner != owning_connector:
        return Terminator.LABEL, entry_net_name.lstrip("/")

    ctx.slice_ownership[slice_key] = owning_connector
    ctx.visited_nets.add(entry_net_name)
    current_acc.slices.append(_place_slice(entry_part_ref, slice_index, entry_slice))
    ctx.placed_slices.add(slice_key)

    exit_pin_id = _other_pin_on_slice(entry_slice, entry_pin_id)
    if exit_pin_id is None:
        return Terminator.NC, None

    exit_net = _net_for_pin(ctx.ir, entry_part_ref, exit_pin_id)
    if exit_net is None or exit_net.name in ctx.visited_nets:
        return Terminator.NC, None

    sub_kind = classify_net(exit_net, power_nets=ctx.mapping.power_nets)
    ctx.visited_nets.add(exit_net.name)
    if sub_kind is NetKind.DROPPED:
        return Terminator.NC, None
    if sub_kind is NetKind.POWER:
        return Terminator.POWER, _power_canonical_name(exit_net, ctx.mapping)
    if sub_kind is NetKind.LABEL:
        return Terminator.LABEL, exit_net.name.lstrip("/")

    # CHAIN: split-on-cap, then recurse.
    sub_other = _other_pin_on_chain(exit_net, entry_part_ref, exit_pin_id)
    if sub_other is None:
        return Terminator.NC, None
    if len(current_acc.slices) >= ctx.max_symbols_per_column:
        completed_columns.append(
            Column(
                slices=tuple(current_acc.slices),
                terminator=Terminator.CONTINUATION,
                terminator_label=exit_net.name.lstrip("/"),
            )
        )
        current_acc.slices = []
    return _walk_part_to_completion(
        ctx,
        owning_connector=owning_connector,
        entry_part_ref=sub_other.part_ref,
        entry_pin_id=sub_other.pin_name,
        entry_net_name=exit_net.name,
        current_acc=current_acc,
        completed_columns=completed_columns,
    )


def walk_pin(  # noqa: PLR0911
    ctx: WalkContext,
    *,
    connector_ref: str,
    pin_id: str,
) -> tuple[Column, ...]:
    """Walk one connector pin's CHAIN to completion; return tuple of Columns.

    Walks from the given connector pin, placing all reachable parts atomically
    (draw-to-completion-ASAP for multi-slice parts) before returning.

    Args:
        ctx: Mutable walk context (ir, mapping, slice_ownership, etc.).
        connector_ref: Ref of the connector part owning this pin.
        pin_id: The connector pin number to walk from.

    Returns:
        A tuple of Columns. Currently always a 1-tuple; Task 2.6 will split
        into multiple Columns when max_symbols_per_column is exceeded.
    """
    ctx.visited_nets.clear()
    net = _net_for_pin(ctx.ir, connector_ref, pin_id)
    if net is None:
        return (Column(slices=(), terminator=Terminator.NC, terminator_label=None),)

    kind = classify_net(net, power_nets=ctx.mapping.power_nets)
    if kind is not NetKind.CHAIN:
        terminator, label = _terminator_for_net(net, ctx.mapping)
        return (Column(slices=(), terminator=terminator, terminator_label=label),)

    other = _other_pin_on_chain(net, connector_ref, pin_id)
    if other is None:
        return (Column(slices=(), terminator=Terminator.NC, terminator_label=None),)

    # Cross-block check: resolve other.part_ref's slice, then check its ownership.
    other_part = next((p for p in ctx.ir.parts if p.ref == other.part_ref), None)
    if other_part is None:
        return (
            Column(
                slices=(),
                terminator=Terminator.LABEL,
                terminator_label=net.name.lstrip("/"),
            ),
        )
    other_smap = _symbol_map_for(other_part, ctx.mapping)
    if other_smap is None:
        return (
            Column(
                slices=(),
                terminator=Terminator.LABEL,
                terminator_label=net.name.lstrip("/"),
            ),
        )
    other_resolved = _resolve_slice(other_smap, other.pin_name)
    if other_resolved is None:
        return (
            Column(
                slices=(),
                terminator=Terminator.LABEL,
                terminator_label=net.name.lstrip("/"),
            ),
        )
    other_slice_idx, _ = other_resolved
    other_slice_key = (other.part_ref, other_slice_idx)
    existing_owner = ctx.slice_ownership.get(other_slice_key)
    if existing_owner is not None and existing_owner != connector_ref:
        return (
            Column(
                slices=(),
                terminator=Terminator.LABEL,
                terminator_label=net.name.lstrip("/"),
            ),
        )

    current_acc = _ColumnAccumulator()
    completed_columns: list[Column] = []
    cluster_terminator, cluster_label = _walk_part_to_completion(
        ctx,
        owning_connector=connector_ref,
        entry_part_ref=other.part_ref,
        entry_pin_id=other.pin_name,
        entry_net_name=net.name,
        current_acc=current_acc,
        completed_columns=completed_columns,
    )
    # Close the final (or only) column with the cluster's actual terminator.
    final_column = Column(
        slices=tuple(current_acc.slices),
        terminator=cluster_terminator,
        terminator_label=cluster_label,
    )
    return (*completed_columns, final_column)


# ---------------------------------------------------------------------------
# build_connector_blocks
# ---------------------------------------------------------------------------


def build_connector_blocks(
    ir: Any,  # noqa: ANN401
    mapping: SymbolMapping,
    *,
    max_symbols_per_column: int,
    strict_net_names: bool,
) -> tuple[tuple[ConnectorBlock, ...], dict[tuple[str, int], str]]:
    """For each connector in declaration order, assemble its ConnectorBlock.

    Args:
        ir: CircuitIR from adapter.adapt().
        mapping: SymbolMapping with connector/symbol/power-net registrations.
        max_symbols_per_column: Hard cap on placed slices per column.
        strict_net_names: If True, raises UnnamedNetError for unnamed nets.

    Returns:
        ``(blocks, slice_ownership)`` where ``blocks`` is a tuple of ConnectorBlocks
        in declaration order and ``slice_ownership`` maps (part_ref, slice_index) →
        connector_ref.

    Raises:
        UnnamedNetError: If strict_net_names is True and a net has no name.

    Examples:
        >>> blocks, ownership = build_connector_blocks(  # doctest: +SKIP
        ...     ir, mapping, max_symbols_per_column=2, strict_net_names=False
        ... )
    """
    if strict_net_names:
        for net in ir.nets:
            if not net.name:
                raise UnnamedNetError(net_id=str(id(net)), pin_count=len(net.pins))
    ctx = WalkContext(
        ir=ir,
        mapping=mapping,
        slice_ownership={},
        max_symbols_per_column=max_symbols_per_column,
    )
    blocks: list[ConnectorBlock] = []
    for connector in enumerate_connectors(ir, mapping):
        pin_columns_list: list[PinColumns] = []
        for pin_id in connector.pin_numbers:
            cols = walk_pin(ctx, connector_ref=connector.ref, pin_id=pin_id)
            pin_columns_list.append(PinColumns(pin_id=pin_id, columns=cols))
        blocks.append(
            ConnectorBlock(
                connector_ref=connector.ref,
                functional_label=connector.description,
                pin_columns=tuple(pin_columns_list),
            )
        )
    return tuple(blocks), ctx.slice_ownership


# ---------------------------------------------------------------------------
# find_floating_parts
# ---------------------------------------------------------------------------


def find_floating_parts(
    ir: Any,  # noqa: ANN401
    mapping: SymbolMapping,
    slice_ownership: dict[tuple[str, int], str],
) -> tuple[FloatingPart, ...]:
    """Return one FloatingPart per part where every slice is unowned.

    Args:
        ir: CircuitIR from adapter.adapt().
        mapping: SymbolMapping used to identify connector templates.
        slice_ownership: Mapping of (part_ref, slice_index) → connector_ref
            from build_connector_blocks.

    Returns:
        Tuple of FloatingPart for every non-connector part where no slice is owned.

    Examples:
        >>> floating = find_floating_parts(ir, mapping, ownership)  # doctest: +SKIP
    """
    connector_template_names = {template_name(cm.template) for cm in mapping.connectors}
    floating: list[FloatingPart] = []
    for part in ir.parts:
        if part.template_name in connector_template_names:
            continue
        smap = _symbol_map_for(part, mapping)
        if smap is None:
            continue
        # Floating only if ALL slices of the part are unowned.
        all_unowned = all(
            (part.ref, idx) not in slice_ownership for idx in range(len(smap.slices))
        )
        if all_unowned:
            floating.append(FloatingPart(part_ref=part.ref))
    return tuple(floating)


# ---------------------------------------------------------------------------
# pack_pages
# ---------------------------------------------------------------------------


def pack_pages(
    blocks: tuple[ConnectorBlock, ...],
    floating: tuple[FloatingPart, ...],
    page_size: tuple[float, float],
    layout: LayoutSpec,
) -> tuple[Page, ...]:
    """Greedy width-first packer; all blocks on a page share an implicit origin_y.

    Args:
        blocks: ConnectorBlocks to distribute across pages.
        floating: FloatingParts to append to the last page (or a new page if none).
        page_size: ``(width_mm, height_mm)`` of the target page.
        layout: LayoutSpec with spacing constants.

    Returns:
        Tuple of Pages. Each Page carries ``placements`` — a tuple of
        ``(connector_ref, origin_x_mm)`` pairs — and optionally
        ``floating_part_refs`` on the last page.
    """
    if not blocks and not floating:
        return ()

    available_width = page_size[0] - 2 * layout.page_left_margin_mm
    pages: list[Page] = []
    current: list[tuple[str, float]] = []
    current_used: float = 0.0  # x-extent of the rightmost block

    def block_width(b: ConnectorBlock) -> float:
        return 2 * layout.side_padding_mm + len(b.pin_columns) * layout.pin_spacing_mm

    def close_page() -> None:
        if current:
            title = f"Connectors starting at {current[0][0]}"
            pages.append(
                Page(title=title, placements=tuple(current), floating_part_refs=())
            )

    for block in blocks:
        bw = block_width(block)
        if not current:
            current.append((block.connector_ref, 0.0))
            current_used = bw
        else:
            candidate_x = current_used + layout.inter_block_gap_mm
            if candidate_x + bw > available_width:
                close_page()
                current = [(block.connector_ref, 0.0)]
                current_used = bw
            else:
                current.append((block.connector_ref, candidate_x))
                current_used = candidate_x + bw

    close_page()

    # Append floating parts to last page (or a new page if none).
    if floating:
        floating_refs = tuple(fp.part_ref for fp in floating)
        if pages:
            last = pages[-1]
            pages[-1] = Page(
                title=last.title,
                placements=last.placements,
                floating_part_refs=floating_refs,
            )
        else:
            pages.append(
                Page(
                    title="Floating parts",
                    placements=(),
                    floating_part_refs=floating_refs,
                )
            )

    return tuple(pages)
