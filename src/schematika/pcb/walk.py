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


def _resolve_chain(
    ctx: WalkContext,
    net: Any,  # noqa: ANN401
    connector_ref: str,
    entry_pin: str,
) -> Column | None:
    """Attempt to place the part at the other end of a CHAIN net.

    Returns a Column if successful, or None to signal the caller should use
    a cross-block LABEL terminator.
    """
    other = _other_pin_on_chain(net, connector_ref, entry_pin)
    if other is None:
        return Column(slices=(), terminator=Terminator.NC, terminator_label=None)

    other_part = next((p for p in ctx.ir.parts if p.ref == other.part_ref), None)
    if other_part is None:
        return Column(slices=(), terminator=Terminator.NC, terminator_label=None)

    smap = _symbol_map_for(other_part, ctx.mapping)
    if smap is None:
        return None  # cross-block LABEL

    existing_owner = ctx.ownership.get(other.part_ref)
    if existing_owner is not None and existing_owner != connector_ref:
        return None  # cross-block LABEL

    ctx.ownership[other.part_ref] = connector_ref
    placed = _place_part(other_part, smap)

    exit_pin_id = next(
        (pid for pid in other_part.pin_numbers if pid != other.pin_name), None
    )
    exit_net = (
        _net_for_pin(ctx.ir, other.part_ref, exit_pin_id) if exit_pin_id else None
    )
    terminator, label = (
        _terminator_for_net(exit_net, ctx.mapping)
        if exit_net
        else (Terminator.NC, None)
    )
    return Column(slices=placed, terminator=terminator, terminator_label=label)


def walk_pin(ctx: WalkContext, *, connector_ref: str, pin_id: str) -> Column:
    """Single-step CHAIN traversal from a connector pin; produces one Column.

    Walks one step from the given connector pin: classifies the pin's net,
    places at most one component, then determines the terminator by inspecting
    the placed component's other pin.

    Args:
        ctx: Mutable walk context (ir, mapping, ownership, etc.).
        connector_ref: Ref of the connector part owning this pin.
        pin_id: The connector pin number to walk from.

    Returns:
        A Column with zero or one PlacedSlice and a Terminator.
    """
    net = _net_for_pin(ctx.ir, connector_ref, pin_id)
    if net is None:
        return Column(slices=(), terminator=Terminator.NC, terminator_label=None)

    kind = classify_net(net, power_nets=ctx.mapping.power_nets)
    if kind is not NetKind.CHAIN:
        terminator, label = _terminator_for_net(net, ctx.mapping)
        return Column(slices=(), terminator=terminator, terminator_label=label)

    column = _resolve_chain(ctx, net, connector_ref, pin_id)
    if column is None:
        # Cross-block: other end is a connector or already owned.
        return Column(
            slices=(),
            terminator=Terminator.LABEL,
            terminator_label=net.name.lstrip("/"),
        )
    return column
