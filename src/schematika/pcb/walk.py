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
from schematika.pcb.model import (
    Column,
    PinPlacement,
    PlacedSlice,
    SymbolMap,
    SymbolMapping,
    Terminator,
)


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


def _walk_remaining_pin(
    ctx: WalkContext,
    *,
    owning_connector: str,
    part_ref: str,
    pin_id: str,
    cluster: list[PlacedSlice],
    exits: list[tuple[Terminator, str | None]],
) -> None:
    """Classify one remaining pin and append its result to cluster/exits."""
    net = _net_for_pin(ctx.ir, part_ref, pin_id)
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
    # CHAIN: recurse into the next part.
    sub_other = _other_pin_on_chain(net, part_ref, pin_id)
    if sub_other is None:
        return
    sub_slices, sub_term, sub_label = _walk_part_to_completion(
        ctx,
        owning_connector=owning_connector,
        entry_part_ref=sub_other.part_ref,
        entry_pin_id=sub_other.pin_name,
        entry_net_name=net.name,
    )
    cluster.extend(sub_slices)
    exits.append((sub_term, sub_label))


def _walk_part_to_completion(
    ctx: WalkContext,
    *,
    owning_connector: str,
    entry_part_ref: str,
    entry_pin_id: str,
    entry_net_name: str,
) -> tuple[list[PlacedSlice], Terminator, str | None]:
    """Recursively place a part and walk all its remaining pins to completion.

    Returns a (placed_slices, terminator, label) triple representing the
    full cluster reachable from entry_part_ref.
    """
    part = next((p for p in ctx.ir.parts if p.ref == entry_part_ref), None)
    if part is None:
        return [], Terminator.LABEL, entry_net_name.lstrip("/")

    smap = _symbol_map_for(part, ctx.mapping)
    if smap is None:
        return [], Terminator.LABEL, entry_net_name.lstrip("/")

    existing_owner = ctx.ownership.get(entry_part_ref)
    if existing_owner is not None and existing_owner != owning_connector:
        return [], Terminator.LABEL, entry_net_name.lstrip("/")

    ctx.ownership[entry_part_ref] = owning_connector
    ctx.visited_nets.add(entry_net_name)

    cluster: list[PlacedSlice] = list(_place_part(part, smap))
    exits: list[tuple[Terminator, str | None]] = []
    for slice_def in smap.slices:
        for pin_id in slice_def.pin_map:
            if pin_id == entry_pin_id:
                continue
            _walk_remaining_pin(
                ctx,
                owning_connector=owning_connector,
                part_ref=entry_part_ref,
                pin_id=pin_id,
                cluster=cluster,
                exits=exits,
            )

    # Pick a single terminator: first POWER, then first LABEL, else NC.
    chosen_terminator = Terminator.NC
    chosen_label: str | None = None
    for term, label in exits:
        if term is Terminator.POWER:
            chosen_terminator, chosen_label = Terminator.POWER, label
            break
    else:
        for term, label in exits:
            if term is Terminator.LABEL:
                chosen_terminator, chosen_label = Terminator.LABEL, label
                break

    return cluster, chosen_terminator, chosen_label


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

    cluster_slices, cluster_terminator, cluster_label = _walk_part_to_completion(
        ctx,
        owning_connector=connector_ref,
        entry_part_ref=other.part_ref,
        entry_pin_id=other.pin_name,
        entry_net_name=net.name,
    )
    return (
        Column(
            slices=tuple(cluster_slices),
            terminator=cluster_terminator,
            terminator_label=cluster_label,
        ),
    )
