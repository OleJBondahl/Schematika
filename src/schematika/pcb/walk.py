"""Connector-anchored walk algorithm.

This module is the heart of schematika.pcb v2 — it consumes an adapter IR
plus a SymbolMapping and produces tuple[ConnectorBlock, ...] + floating
parts. Subsequent tasks add the actual chain walk; this task only adds the
enumeration helper.
"""

import logging
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from typing import Any

from schematika.pcb.adapter import template_name
from schematika.pcb.classify import NetKind, classify_net
from schematika.pcb.errors import BottomTerminatorOrphanNetError, UnnamedNetError
from schematika.pcb.layout_spec import LayoutSpec
from schematika.pcb.model import (
    Column,
    ConnectorBlock,
    ConnectorMap,
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

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal accumulator (not exported)
# ---------------------------------------------------------------------------


@dataclass
class _ColumnAccumulator:
    """Mutable column being built during a walk."""

    slices: list[PlacedSlice] = field(default_factory=list)
    terminator: Terminator = Terminator.NC
    terminator_label: str | None = None
    chain_net_name: str | None = None


def _bottom_terminator_template_names(mapping: SymbolMapping) -> set[str]:
    """Return template names of all bottom-terminator connectors in the mapping."""
    return {
        template_name(cm.template) for cm in mapping.connectors if cm.bottom_terminator
    }


def _dest_connector_map(
    ir: Any,  # noqa: ANN401
    dest_part_ref: str,
    mapping: SymbolMapping,
) -> ConnectorMap | None:
    """Return the ConnectorMap for dest_part_ref if it's a connector, else None."""
    for part in ir.parts:
        if part.ref == dest_part_ref:
            for cm in mapping.connectors:
                if template_name(cm.template) == part.template_name:
                    return cm
            return None
    return None


def enumerate_connectors(
    ir: Any,  # noqa: ANN401
    mapping: SymbolMapping,
) -> Iterator[Any]:
    """Yield part-IRs whose template is a non-bottom-terminator connector.

    Bottom-terminator connectors are skipped — they never become header blocks.

    Args:
        ir: Internal representation with a `parts` iterable of part objects,
            each with a `template_name` attribute.
        mapping: SymbolMapping containing registered connector templates.

    Yields:
        Part objects from ir.parts whose template_name matches a registered
        non-bottom-terminator connector template.
    """
    bottom_names = _bottom_terminator_template_names(mapping)
    connector_template_names = {template_name(cm.template) for cm in mapping.connectors}
    for part in ir.parts:
        if (
            part.template_name in connector_template_names
            and part.template_name not in bottom_names
        ):
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
    sym = slc.symbol(label=part_ref)
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


def _walk_part_to_completion(  # noqa: PLR0911, PLR0912
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
        net_label = entry_net_name.lstrip("/")
        current_acc.chain_net_name = net_label
        return Terminator.LABEL, net_label
    # Check if the destination part is a bottom-terminator connector.
    dest_cmap = _dest_connector_map(ctx.ir, entry_part_ref, ctx.mapping)
    if dest_cmap is not None and dest_cmap.bottom_terminator:
        label = f"{entry_part_ref}:{entry_pin_id}"
        current_acc.chain_net_name = entry_net_name.lstrip("/")
        return Terminator.PIN_AT_BOTTOM, label
    smap = _symbol_map_for(part, ctx.mapping)
    if smap is None:
        net_label = entry_net_name.lstrip("/")
        current_acc.chain_net_name = net_label
        return Terminator.LABEL, net_label

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
        current_acc.chain_net_name = entry_net_name.lstrip("/")
        return Terminator.POWER, _power_canonical_name(exit_net, ctx.mapping)
    if sub_kind is NetKind.LABEL:
        net_label = exit_net.name.lstrip("/")
        current_acc.chain_net_name = net_label
        return Terminator.LABEL, net_label

    # CHAIN: check if the sub_other part is a bottom-terminator connector.
    sub_other = _other_pin_on_chain(exit_net, entry_part_ref, exit_pin_id)
    if sub_other is None:
        return Terminator.NC, None
    sub_dest_cmap = _dest_connector_map(ctx.ir, sub_other.part_ref, ctx.mapping)
    if sub_dest_cmap is not None and sub_dest_cmap.bottom_terminator:
        label = f"{sub_other.part_ref}:{sub_other.pin_name}"
        current_acc.chain_net_name = exit_net.name.lstrip("/")
        return Terminator.PIN_AT_BOTTOM, label
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

    # Cross-block check: if the immediate neighbour is a bottom-terminator connector,
    # emit PIN_AT_BOTTOM directly without walking any slices.
    other_dest_cmap = _dest_connector_map(ctx.ir, other.part_ref, ctx.mapping)
    if other_dest_cmap is not None and other_dest_cmap.bottom_terminator:
        label = f"{other.part_ref}:{other.pin_name}"
        return (
            Column(
                slices=(),
                terminator=Terminator.PIN_AT_BOTTOM,
                terminator_label=label,
                chain_net_name=net.name.lstrip("/"),
            ),
        )

    # Cross-block check: resolve other.part_ref's slice, then check its ownership.
    other_part = next((p for p in ctx.ir.parts if p.ref == other.part_ref), None)
    if other_part is None:
        net_label = net.name.lstrip("/")
        return (
            Column(
                slices=(),
                terminator=Terminator.LABEL,
                terminator_label=net_label,
                chain_net_name=net_label,
            ),
        )
    other_smap = _symbol_map_for(other_part, ctx.mapping)
    if other_smap is None:
        net_label = net.name.lstrip("/")
        return (
            Column(
                slices=(),
                terminator=Terminator.LABEL,
                terminator_label=net_label,
                chain_net_name=net_label,
            ),
        )
    other_resolved = _resolve_slice(other_smap, other.pin_name)
    if other_resolved is None:
        net_label = net.name.lstrip("/")
        return (
            Column(
                slices=(),
                terminator=Terminator.LABEL,
                terminator_label=net_label,
                chain_net_name=net_label,
            ),
        )
    other_slice_idx, _ = other_resolved
    other_slice_key = (other.part_ref, other_slice_idx)
    existing_owner = ctx.slice_ownership.get(other_slice_key)
    if existing_owner is not None and existing_owner != connector_ref:
        net_label = net.name.lstrip("/")
        return (
            Column(
                slices=(),
                terminator=Terminator.LABEL,
                terminator_label=net_label,
                chain_net_name=net_label,
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
    # Ensure chain_net_name is set for LABEL terminators.
    if cluster_terminator is Terminator.LABEL and current_acc.chain_net_name is None:
        current_acc.chain_net_name = cluster_label
    # Close the final (or only) column with the cluster's actual terminator.
    final_column = Column(
        slices=tuple(current_acc.slices),
        terminator=cluster_terminator,
        terminator_label=cluster_label,
        chain_net_name=current_acc.chain_net_name,
    )
    return (*completed_columns, final_column)


# ---------------------------------------------------------------------------
# build_connector_blocks
# ---------------------------------------------------------------------------


def _validate_no_orphan_nets(
    ir: Any,  # noqa: ANN401
    mapping: SymbolMapping,
) -> None:
    """Raise BottomTerminatorOrphanNetError if a net has no path to a normal connector.

    A net is orphaned when every part that touches it is either:
    (a) a bottom-terminator connector, or
    (b) not a connector at all,
    AND there is at least one bottom-terminator connector pin on the net.

    This check catches cases like a relay coil wired directly to J7 with no
    path to any normal (non-bottom-terminator) connector.  A net that only
    touches non-connector parts (no connectors at all) is not flagged.

    Raises:
        BottomTerminatorOrphanNetError: If any such net is detected.
    """
    bottom_names = _bottom_terminator_template_names(mapping)
    if not bottom_names:
        return
    connector_template_names = {template_name(cm.template) for cm in mapping.connectors}
    # Build a map: part_ref → template_name for connectors only
    connector_part_templates: dict[str, str] = {}
    for part in ir.parts:
        if part.template_name in connector_template_names:
            connector_part_templates[part.ref] = part.template_name

    # Build set of part_refs reachable from normal (non-bottom) connectors.
    # A part is reachable if it shares a net with a normal connector pin.
    normal_connector_refs = {
        part.ref
        for part in ir.parts
        if part.template_name in connector_template_names
        and part.template_name not in bottom_names
    }
    reachable_parts: set[str] = set(normal_connector_refs)
    # One BFS/flood-fill pass to expand reachability.
    changed = True
    while changed:
        changed = False
        for net in ir.nets:
            net_refs = {pin.part_ref for pin in net.pins}
            if net_refs & reachable_parts:
                new_parts = net_refs - reachable_parts
                if new_parts:
                    reachable_parts |= new_parts
                    changed = True

    for net in ir.nets:
        connector_pins = [
            pin for pin in net.pins if pin.part_ref in connector_part_templates
        ]
        if not connector_pins:
            continue  # no connectors at all on this net → not an orphan concern
        bottom_pins = [
            pin
            for pin in connector_pins
            if connector_part_templates[pin.part_ref] in bottom_names
        ]
        if not bottom_pins:
            continue  # no bottom-terminator connectors on this net → fine
        # Net has at least one bottom-terminator pin.
        # Check that at least one part on this net is reachable from a normal connector.
        net_refs = {pin.part_ref for pin in net.pins}
        bottom_refs = {p.part_ref for p in bottom_pins}
        has_normal_anchor = bool(net_refs & reachable_parts - bottom_refs)
        if not has_normal_anchor:
            # Verify no normal connector is directly on this net.
            normal_on_net = [
                pin
                for pin in connector_pins
                if connector_part_templates[pin.part_ref] not in bottom_names
            ]
            if not normal_on_net:
                parts_on_net = [pin.part_ref for pin in net.pins]
                raise BottomTerminatorOrphanNetError(
                    net_name=net.name, parts=parts_on_net
                )


def _check_duplicate_pin_at_bottom(  # noqa: PLR0912
    blocks: list[ConnectorBlock],
    pages: list[Page] | None = None,
) -> None:
    """Emit a warning for any same-page PIN_AT_BOTTOM columns sharing a label.

    Operates on all blocks when pages=None (warn globally). When pages are
    provided, groups by page.
    """
    if pages is None:
        # Global scan: group by label across all blocks
        label_blocks: dict[str, list[str]] = defaultdict(list)
        for block in blocks:
            for pc in block.pin_columns:
                for col in pc.columns:
                    if (
                        col.terminator is Terminator.PIN_AT_BOTTOM
                        and col.terminator_label
                    ):
                        label_blocks[col.terminator_label].append(block.connector_ref)
        for label, refs in label_blocks.items():
            if len(refs) > 1:
                _log.warning(
                    "Duplicate PIN_AT_BOTTOM label %r appears in blocks: %s",
                    label,
                    refs,
                )
        return

    block_by_ref = {b.connector_ref: b for b in blocks}
    for page in pages:
        label_counts: dict[str, list[str]] = defaultdict(list)
        for block_ref, _, _ in page.placements:
            block = block_by_ref.get(block_ref)
            if block is None:
                continue
            for pc in block.pin_columns:
                for col in pc.columns:
                    if (
                        col.terminator is Terminator.PIN_AT_BOTTOM
                        and col.terminator_label
                    ):
                        label_counts[col.terminator_label].append(block_ref)
        for label, refs in label_counts.items():
            if len(refs) > 1:
                _log.warning(
                    "Page %r: duplicate PIN_AT_BOTTOM label %r in blocks: %s",
                    page.title,
                    label,
                    refs,
                )


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
        BottomTerminatorOrphanNetError: If a net touches only bottom-terminator
            connectors and no normal connectors.

    Examples:
        >>> blocks, ownership = build_connector_blocks(  # doctest: +SKIP
        ...     ir, mapping, max_symbols_per_column=2, strict_net_names=False
        ... )
    """
    if strict_net_names:
        for net in ir.nets:
            if not net.name:
                raise UnnamedNetError(net_id=str(id(net)), pin_count=len(net.pins))
    _validate_no_orphan_nets(ir, mapping)
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
        cmap = next(
            (
                cm
                for cm in mapping.connectors
                if template_name(cm.template) == connector.template_name
            ),
            None,
        )
        blocks.append(
            ConnectorBlock(
                connector_ref=connector.ref,
                functional_label=connector.description,
                pin_columns=tuple(pin_columns_list),
                bottom_terminator=cmap.bottom_terminator if cmap is not None else False,
            )
        )
    _check_duplicate_pin_at_bottom(blocks)
    return tuple(blocks), ctx.slice_ownership


# ---------------------------------------------------------------------------
# find_floating_parts
# ---------------------------------------------------------------------------


def find_floating_parts(
    ir: Any,  # noqa: ANN401
    mapping: SymbolMapping,
    slice_ownership: dict[tuple[str, int], str],
) -> tuple[FloatingPart, ...]:
    """Return one FloatingPart per part with at least one unowned slice.

    Args:
        ir: CircuitIR from adapter.adapt().
        mapping: SymbolMapping used to identify connector templates.
        slice_ownership: Mapping of (part_ref, slice_index) → connector_ref
            from build_connector_blocks.

    Returns:
        Tuple of FloatingPart for every non-connector part with at least one
        unowned slice. Each FloatingPart carries the indices of its unowned
        slices in ``slice_indices``.

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
        # Floating if ANY slice of the part is unowned.
        has_unowned_slice = any(
            (part.ref, idx) not in slice_ownership for idx in range(len(smap.slices))
        )
        if has_unowned_slice:
            unowned = tuple(
                idx
                for idx in range(len(smap.slices))
                if (part.ref, idx) not in slice_ownership
            )
            floating.append(FloatingPart(part_ref=part.ref, slice_indices=unowned))
    return tuple(floating)


# ---------------------------------------------------------------------------
# pack_pages
# ---------------------------------------------------------------------------


def compute_max_chain_height_mm(block: ConnectorBlock, layout: LayoutSpec) -> float:
    """Return the chain depth of the tallest pin in ``block``, in mm.

    Measured from the connector's own ``origin_y_mm`` down to the
    deepest terminator point across all pin_columns. Mirrors the
    geometry in render.render_connector_block / _render_column_slices /
    _render_terminator so pack_pages can decide whether the block leaves
    room for a second row below it.

    Bottom-terminator chains return ``layout.bottom_terminator_y_mm -
    origin_y`` (treating origin_y == 0 for the per-block depth) so the
    chain is correctly measured to its absolute bottom Y.
    """
    if not block.pin_columns:
        return layout.block_height_mm
    max_depth = 0.0
    for pc in block.pin_columns:
        # pin_anchor_y is the top of the chain area; relative to origin_y
        # it equals layout.block_height_mm.
        pin_anchor_rel = layout.block_height_mm
        cursor_y = pin_anchor_rel
        for col_idx, column in enumerate(pc.columns):
            if col_idx == 0:
                if column.slices:
                    chain_y = pin_anchor_rel + layout.connector_to_first_symbol_gap_mm
                elif column.terminator is Terminator.NC:
                    chain_y = pin_anchor_rel
                else:
                    chain_y = pin_anchor_rel + layout.connector_to_first_label_gap_mm
            else:
                cursor_y += layout.slice_height_mm
                chain_y = cursor_y
            # Slices stack downward at slice_height_mm each.
            terminator_rel = chain_y + len(column.slices) * layout.slice_height_mm
            # Terminator-specific extension below terminator_rel.
            if column.terminator is Terminator.POWER:
                terminator_rel += layout.power_terminator_offset_mm
            elif column.terminator is Terminator.PIN_AT_BOTTOM:
                # Bottom-terminator wires drop to the absolute bottom Y.
                # Express as relative-to-origin: bottom_terminator_y_mm
                # is absolute, but origin is added back on by the caller
                # — we compute as if origin=0, so the depth IS bottom_y.
                terminator_rel = max(terminator_rel, layout.bottom_terminator_y_mm)
            cursor_y = terminator_rel + layout.slice_height_mm
            max_depth = max(max_depth, terminator_rel)
    return max_depth


def pack_pages(  # noqa: PLR0915
    blocks: tuple[ConnectorBlock, ...],
    floating: tuple[FloatingPart, ...],
    page_size: tuple[float, float],
    layout: LayoutSpec,
) -> tuple[tuple[ConnectorBlock, ...], tuple[Page, ...]]:
    """Greedy two-row width-first packer.

    Row 1 is packed at ``origin_y = layout.vertical_margin_mm``. If every
    block in row 1 has a chain that ends at least
    ``layout.vertical_margin_mm`` above ``row2_origin_y_mm``, AND blocks
    remain unplaced, a second row is opened at
    ``row2_origin_y_mm = page_size[1] / 2 + layout.row2_origin_y_offset_mm``.
    Row 2 admits only blocks whose chain depth fits between
    ``row2_origin_y_mm`` and ``page_size[1] - layout.vertical_margin_mm``.

    Args:
        blocks: ConnectorBlocks to distribute across pages (declaration order).
        floating: FloatingParts appended to the last page (or a new page).
        page_size: ``(width_mm, height_mm)`` of the target page.
        layout: LayoutSpec.

    Returns:
        ``(updated_blocks, pages)`` — ``updated_blocks`` is the input blocks
        with ``max_chain_height_mm`` populated; each Page carries
        ``placements`` as ``(connector_ref, origin_x_mm, origin_y_mm)``
        triples.
    """
    if not blocks and not floating:
        return blocks, ()

    # Precompute max_chain_height_mm for every block.
    blocks = tuple(
        replace(b, max_chain_height_mm=compute_max_chain_height_mm(b, layout))
        for b in blocks
    )

    available_width = page_size[0] - 2 * layout.horizontal_margin_mm
    page_h = page_size[1]
    row1_y = layout.vertical_margin_mm
    row2_y = page_h / 2 + layout.row2_origin_y_offset_mm
    # Row-1 chain must end at least vertical_margin_mm above row2_y.
    row1_chain_budget = row2_y - layout.vertical_margin_mm - row1_y
    # Row-2 chain must fit between row2_y and (page_h - vertical_margin_mm).
    row2_chain_budget = page_h - layout.vertical_margin_mm - row2_y

    def block_width(b: ConnectorBlock) -> float:
        return 2 * layout.side_padding_mm + len(b.pin_columns) * layout.pin_spacing_mm

    def pack_row(
        remaining: list[ConnectorBlock],
        chain_budget: float,
    ) -> tuple[list[tuple[str, float]], list[ConnectorBlock]]:
        """Greedy width-first pack against available_width, with chain_budget filter."""
        row: list[tuple[str, float]] = []
        used = 0.0
        i = 0
        while i < len(remaining):
            b = remaining[i]
            if b.max_chain_height_mm > chain_budget:
                break  # this block (and any in declaration order behind it) waits
            bw = block_width(b)
            if not row:
                row.append((b.connector_ref, 0.0))
                used = bw
                i += 1
            else:
                candidate_x = used + layout.inter_block_gap_mm
                if candidate_x + bw > available_width:
                    break
                row.append((b.connector_ref, candidate_x))
                used = candidate_x + bw
                i += 1
        return row, remaining[i:]

    pages: list[Page] = []
    remaining: list[ConnectorBlock] = list(blocks)
    while remaining:
        # Row 1: no chain budget filter — use a budget of +infinity so any block fits.
        row1, remaining = pack_row(remaining, float("inf"))
        if not row1:
            # Defensive: a single block too tall for row1_chain_budget would loop
            # forever otherwise. The pack_row "if not row" branch admits any block
            # at row 1 regardless, so this branch is unreachable; assert and break.
            break
        # Decide whether to open row 2.
        page_placements: list[tuple[str, float, float]] = [
            (ref, x, row1_y) for ref, x in row1
        ]
        by_ref = {b.connector_ref: b for b in blocks}
        row1_blocks = [by_ref[ref] for ref, _ in row1]
        all_row1_short = all(
            b.max_chain_height_mm < row1_chain_budget for b in row1_blocks
        )
        if all_row1_short and remaining:
            row2, remaining = pack_row(remaining, row2_chain_budget)
            page_placements.extend((ref, x, row2_y) for ref, x in row2)
        title = f"Connectors starting at {row1[0][0]}"
        pages.append(
            Page(
                title=title,
                placements=tuple(page_placements),
                floating_part_refs=(),
            )
        )

    # Append floating parts.
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

    return blocks, tuple(pages)
