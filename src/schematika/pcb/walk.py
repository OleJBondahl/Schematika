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
        ownership: Maps part_ref → connector_ref (first-touch wins).
        max_symbols_per_column: Hard cap on slices per column.
        visited_nets: Net names already traversed (cycle guard).
    """

    ir: Any
    mapping: SymbolMapping
    ownership: dict[str, str]
    max_symbols_per_column: int
    visited_nets: set[str] = field(default_factory=set)


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


def _place_part(part: Any, smap: SymbolMap) -> tuple[PlacedSlice, ...]:  # noqa: ANN401
    """Instantiate all slices of smap for part and return them as PlacedSlices."""
    placed: list[PlacedSlice] = []
    for idx, slc in enumerate(smap.slices):
        sym = slc.symbol()
        pins = tuple(
            PinPlacement(pin_id=pin_num, port_name=port_name)
            for pin_num, port_name in slc.pin_map.items()
        )
        placed.append(
            PlacedSlice(
                part_ref=part.ref,
                slice_index=idx,
                symbol=sym,
                pins=pins,
            )
        )
    return tuple(placed)


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


def _pick_terminator(
    exits: list[tuple[Terminator, str | None]],
) -> tuple[Terminator, str | None]:
    """Pick a single terminator: first POWER, then first LABEL, else NC."""
    for term, label in exits:
        if term is Terminator.POWER:
            return Terminator.POWER, label
    for term, label in exits:
        if term is Terminator.LABEL:
            return Terminator.LABEL, label
    return Terminator.NC, None


def _process_pin_exits(
    ctx: WalkContext,
    *,
    net: Any,  # noqa: ANN401
    entry_part_ref: str,
    pin_id: str,
    owning_connector: str,
    current_acc: _ColumnAccumulator,
    completed_columns: list[Column],
    exits: list[tuple[Terminator, str | None]],
) -> None:
    """Process one pin's classification and recursively walk CHAIN nets.

    Classifies the net, adds POWER/LABEL terminators to exits, recurses on CHAIN,
    and emits cross-block LABEL columns directly to completed_columns (avoiding
    _pick_terminator's label-collapsing behavior).
    """
    if net is None or net.name in ctx.visited_nets:
        return
    sub_kind = classify_net(net, power_nets=ctx.mapping.power_nets)
    ctx.visited_nets.add(net.name)
    if sub_kind is NetKind.DROPPED:
        return
    if sub_kind is NetKind.POWER:
        exits.append((Terminator.POWER, _power_canonical_name(net, ctx.mapping)))
        return
    if sub_kind is NetKind.LABEL:
        exits.append((Terminator.LABEL, net.name.lstrip("/")))
        return
    # CHAIN: check cap before recursing.
    sub_other = _other_pin_on_chain(net, entry_part_ref, pin_id)
    if sub_other is None:
        return
    if len(current_acc.slices) >= ctx.max_symbols_per_column:
        # Close current column as CONTINUATION; start a fresh one.
        completed_columns.append(
            Column(
                slices=tuple(current_acc.slices),
                terminator=Terminator.CONTINUATION,
                terminator_label=net.name.lstrip("/"),
            )
        )
        current_acc.slices = []
    sub_term, sub_label = _walk_part_to_completion(
        ctx,
        owning_connector=owning_connector,
        entry_part_ref=sub_other.part_ref,
        entry_pin_id=sub_other.pin_name,
        entry_net_name=net.name,
        current_acc=current_acc,
        completed_columns=completed_columns,
    )
    if sub_term is Terminator.LABEL:
        completed_columns.append(
            Column(
                slices=(),
                terminator=Terminator.LABEL,
                terminator_label=sub_label,
            )
        )
    else:
        exits.append((sub_term, sub_label))


def _walk_part_to_completion(
    ctx: WalkContext,
    *,
    owning_connector: str,
    entry_part_ref: str,
    entry_pin_id: str,
    entry_net_name: str,
    current_acc: _ColumnAccumulator,
    completed_columns: list[Column],
) -> tuple[Terminator, str | None]:
    """Recursively place a part and walk all its remaining pins to completion.

    Places all slices of entry_part_ref atomically into current_acc, then
    processes each remaining pin. When following a CHAIN exit and the current
    accumulator is at or over max_symbols_per_column, closes the accumulator as
    a CONTINUATION column and starts a new one before recursing.

    Note: a multi-slice part is always placed atomically in current_acc even if
    its slice count alone exceeds max_symbols_per_column. The column cut only
    happens at chain boundaries between parts, never in the middle of one part.

    Args:
        ctx: Mutable walk context.
        owning_connector: Connector that owns all parts placed in this walk.
        entry_part_ref: The part to place now.
        entry_pin_id: The pin through which we entered (skip when scanning exits).
        entry_net_name: The net name we followed to arrive here.
        current_acc: The in-progress column accumulator (mutated in place).
        completed_columns: Closed columns emitted so far (mutated in place).

    Returns:
        (terminator, label) for the cluster exit of the last column.
    """
    part = next((p for p in ctx.ir.parts if p.ref == entry_part_ref), None)
    if part is None:
        return Terminator.LABEL, entry_net_name.lstrip("/")

    smap = _symbol_map_for(part, ctx.mapping)
    if smap is None:
        return Terminator.LABEL, entry_net_name.lstrip("/")

    existing_owner = ctx.ownership.get(entry_part_ref)
    if existing_owner is not None and existing_owner != owning_connector:
        return Terminator.LABEL, entry_net_name.lstrip("/")

    ctx.ownership[entry_part_ref] = owning_connector
    ctx.visited_nets.add(entry_net_name)

    # Place all slices of this part atomically into the current column.
    current_acc.slices.extend(_place_part(part, smap))

    exits: list[tuple[Terminator, str | None]] = []
    for slice_def in smap.slices:
        for pin_id in slice_def.pin_map:
            if pin_id == entry_pin_id:
                continue
            net = _net_for_pin(ctx.ir, entry_part_ref, pin_id)
            _process_pin_exits(
                ctx,
                net=net,
                entry_part_ref=entry_part_ref,
                pin_id=pin_id,
                owning_connector=owning_connector,
                current_acc=current_acc,
                completed_columns=completed_columns,
                exits=exits,
            )

    return _pick_terminator(exits)


def walk_pin(
    ctx: WalkContext,
    *,
    connector_ref: str,
    pin_id: str,
) -> tuple[Column, ...]:
    """Walk one connector pin's CHAIN to completion; return tuple of Columns.

    Walks from the given connector pin, placing all reachable parts atomically
    (draw-to-completion-ASAP for multi-slice parts) before returning.

    Args:
        ctx: Mutable walk context (ir, mapping, ownership, etc.).
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

    # Check if cross-block before delegating to completion walk.
    other_part = next((p for p in ctx.ir.parts if p.ref == other.part_ref), None)
    if other_part is None or _symbol_map_for(other_part, ctx.mapping) is None:
        return (
            Column(
                slices=(),
                terminator=Terminator.LABEL,
                terminator_label=net.name.lstrip("/"),
            ),
        )
    existing_owner = ctx.ownership.get(other.part_ref)
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
) -> tuple[tuple[ConnectorBlock, ...], dict[str, str]]:
    """For each connector in declaration order, assemble its ConnectorBlock.

    Args:
        ir: CircuitIR from adapter.adapt().
        mapping: SymbolMapping with connector/symbol/power-net registrations.
        max_symbols_per_column: Hard cap on placed slices per column.
        strict_net_names: If True, raises UnnamedNetError for unnamed nets.

    Returns:
        ``(blocks, ownership)`` where ``blocks`` is a tuple of ConnectorBlocks
        in declaration order and ``ownership`` maps part_ref → connector_ref.

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
        ownership={},
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
    return tuple(blocks), ctx.ownership


# ---------------------------------------------------------------------------
# find_floating_parts
# ---------------------------------------------------------------------------


def find_floating_parts(
    ir: Any,  # noqa: ANN401
    mapping: SymbolMapping,
    ownership: dict[str, str],
) -> tuple[FloatingPart, ...]:
    """Return all parts not owned by any connector and not connectors themselves.

    Args:
        ir: CircuitIR from adapter.adapt().
        mapping: SymbolMapping used to identify connector templates.
        ownership: Mapping of part_ref → connector_ref from build_connector_blocks.

    Returns:
        Tuple of FloatingPart for every non-connector part not in ownership.

    Examples:
        >>> floating = find_floating_parts(ir, mapping, ownership)  # doctest: +SKIP
    """
    connector_template_names = {template_name(cm.template) for cm in mapping.connectors}
    floating: list[FloatingPart] = []
    for part in ir.parts:
        if part.template_name in connector_template_names:
            continue
        if part.ref in ownership:
            continue
        floating.append(FloatingPart(part_ref=part.ref))
    return tuple(floating)


# ---------------------------------------------------------------------------
# pack_pages
# ---------------------------------------------------------------------------


def pack_pages(
    blocks: tuple[ConnectorBlock, ...],
    floating: tuple[FloatingPart, ...],
    page_size: tuple[float, float],
    column_spacing_mm: float,
) -> tuple[Page, ...]:
    """Greedy first-fit page packing; floating parts get a final dedicated page.

    Args:
        blocks: ConnectorBlocks to distribute across pages.
        floating: FloatingParts to place on a final "Floating" page.
        page_size: ``(width_mm, height_mm)`` of the target page.
        column_spacing_mm: Width of one column in mm (used to measure block widths).

    Returns:
        Tuple of Pages. Each normal page lists connector_block_refs; the final
        page (if floating is non-empty) has title "Floating" and lists
        floating_part_refs.

    Examples:
        >>> pages = pack_pages(  # doctest: +SKIP
        ...     blocks, floating, page_size=(250.0, 297.0), column_spacing_mm=32.0
        ... )
    """
    page_inner_width = page_size[0]
    pages: list[Page] = []
    current_refs: list[str] = []
    current_width: float = 0.0

    def _block_width(block: ConnectorBlock) -> float:
        if not block.pin_columns:
            return column_spacing_mm
        max_cols = max(len(pc.columns) for pc in block.pin_columns)
        return max_cols * column_spacing_mm

    for block in blocks:
        bw = _block_width(block)
        if not current_refs:
            # First block always fits (single block may exceed page width).
            current_refs.append(block.connector_ref)
            current_width = bw
        else:
            gap = column_spacing_mm
            if current_width + gap + bw > page_inner_width:
                # Overflow: close current page and start a new one.
                pages.append(
                    Page(
                        title=f"Page {len(pages) + 1}",
                        connector_block_refs=tuple(current_refs),
                    )
                )
                current_refs = [block.connector_ref]
                current_width = bw
            else:
                current_refs.append(block.connector_ref)
                current_width += gap + bw

    if current_refs:
        pages.append(
            Page(
                title=f"Page {len(pages) + 1}",
                connector_block_refs=tuple(current_refs),
            )
        )

    if floating:
        pages.append(
            Page(
                title="Floating",
                connector_block_refs=(),
                floating_part_refs=tuple(fp.part_ref for fp in floating),
            )
        )

    return tuple(pages)
