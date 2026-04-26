"""Column traversal, page packing, and result assembly for schematika.pcb."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Final

from schematika.core.geometry import Element, Point, Style, Vector
from schematika.core.options import SymbolConfig
from schematika.core.primitives import Text
from schematika.core.symbol import Port, Symbol
from schematika.core.transform import rotate
from schematika.electrical.builder import CircuitBuilder
from schematika.electrical.model.state import create_initial_state

from .adapter import CircuitIR, NetRef, adapt
from .adapter import template_name as _template_name_of
from .errors import (
    HeightOverflowError,
    OrphanSliceError,
    PCBBuildError,
    UnmappedPartError,
)
from .model import ConnectorMap, PCBBuildResult, SymbolMap, SymbolMapping

if TYPE_CHECKING:
    from collections.abc import Callable

    from schematika.electrical.system.system import Circuit

# Page size constants (mm), landscape orientation
A4_LANDSCAPE: tuple[float, float] = (297.0, 210.0)
A3_LANDSCAPE: tuple[float, float] = (420.0, 297.0)

# A two-pin net forms a direct CHAIN connection between exactly two components.
_CHAIN_NET_PIN_COUNT: Final = 2

# Conservative fixed-size estimates per symbol slot
DEFAULT_SYMBOL_SLOT_HEIGHT: float = 40.0
DEFAULT_COLUMN_WIDTH: float = 50.0


class _NetKind(Enum):
    CHAIN = "CHAIN"
    LABEL = "LABEL"
    POWER = "POWER"


# ---------------------------------------------------------------------------
# Internal dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _PlacedSymbol:
    """One symbol placed in a column."""

    part_ref: str
    symbol_factory: Any  # SymbolFactory callable or None for LABEL placeholder
    entry_pin: str | None
    tag_prefix: str
    rotated: bool  # True if 180° rotation was applied


@dataclass(frozen=True)
class _Column:
    """An ordered sequence of placed symbols forming one vertical column."""

    key: str
    placed_symbols: tuple[_PlacedSymbol, ...]
    width_mm: float
    height_mm: float


@dataclass(frozen=True)
class _ConnectorTerminator:
    """A terminator anchored to a connector pin."""

    cmap: ConnectorMap
    pin_name: str  # SKiDL pin number (string)
    part_ref: str  # resolved instance ref (e.g. "J1")


@dataclass(frozen=True)
class _NetEndpointTerminator:
    """A terminator anchored to a POWER or LABEL net pin."""

    net: NetRef
    pin_part_ref: str
    pin_name: str


_Terminator = _ConnectorTerminator | _NetEndpointTerminator


# ---------------------------------------------------------------------------
# Phase 2 — classify nets
# ---------------------------------------------------------------------------


def _classify_nets(
    ir: CircuitIR,
    mapping: SymbolMapping,
) -> dict[str, _NetKind]:
    """Return a kind for every net to render (0/1-pin nets dropped)."""
    power_net_names = {pn.net_name for pn in mapping.power_nets}
    result: dict[str, _NetKind] = {}
    for net in ir.nets:
        n = len(net.pins)
        if n <= 1:
            continue
        if n == _CHAIN_NET_PIN_COUNT:
            result[net.name] = _NetKind.CHAIN
        elif net.name in power_net_names:
            result[net.name] = _NetKind.POWER
        else:
            result[net.name] = _NetKind.LABEL
    return result


# ---------------------------------------------------------------------------
# Mapping helpers
# ---------------------------------------------------------------------------


def _find_symbol_map(
    template_name: str,
    mapping: SymbolMapping,
) -> SymbolMap | None:
    """Find SymbolMap for the given template name."""
    for sm in mapping.symbols:
        if _template_name_of(sm.template) == template_name:
            return sm
    return None


def _find_connector_map(
    template_name: str,
    mapping: SymbolMapping,
) -> ConnectorMap | None:
    for cm in mapping.connectors:
        if _template_name_of(cm.template) == template_name:
            return cm
    return None


# ---------------------------------------------------------------------------
# Phase 3 — enumerate terminators
# ---------------------------------------------------------------------------


def _enumerate_terminators(
    ir: CircuitIR,
    mapping: SymbolMapping,
    net_kinds: dict[str, _NetKind],
) -> list[_Terminator]:
    """Build the ordered list of terminators."""
    terminators: list[_Terminator] = []

    # 1. Connector pins — one terminator per pin per connector instance
    for part in ir.parts:
        cmap = _find_connector_map(part.template_name, mapping)
        if cmap is None:
            continue
        terminators.extend(
            _ConnectorTerminator(cmap=cmap, pin_name=pin_name, part_ref=part.ref)
            for pin_name in part.pin_numbers
        )

    # 2. POWER / LABEL nets — one terminator per pin occurrence
    for net in ir.nets:
        kind = net_kinds.get(net.name)
        if kind not in (_NetKind.POWER, _NetKind.LABEL):
            continue
        terminators.extend(
            _NetEndpointTerminator(
                net=net, pin_part_ref=pin.part_ref, pin_name=pin.pin_name
            )
            for pin in net.pins
        )

    return terminators


# ---------------------------------------------------------------------------
# Rotation heuristic
# ---------------------------------------------------------------------------

# Heuristic: inspect the entry port's direction vector; if dy > 0 (faces DOWN
# in SVG coordinates where y grows downward), rotate 180° so the entry aligns
# upward toward the incoming wire.


def _should_rotate(symbol_factory: Any, port_name: str) -> bool:  # noqa: ANN401
    """True when the entry port faces down (`dy > 0`); needs a 180° flip."""
    sym = symbol_factory()
    port = sym.ports.get(port_name)
    if port is None:
        return False
    return port.direction.dy > 0


# ---------------------------------------------------------------------------
# Slice helpers
# ---------------------------------------------------------------------------


def _exit_pin_for_slice(sm: SymbolMap, slice_index: int, entry_pin: str) -> str:
    """For a 2-pin slice, return the pin that is not entry_pin."""
    slc = sm.slices[slice_index]
    for pin_name in slc.pin_map:
        if pin_name != entry_pin:
            return pin_name
    msg = (
        f"Slice {slice_index} of {_template_name_of(sm.template)} "
        f"has no exit pin after removing entry={entry_pin}"
    )
    raise PCBBuildError(msg)


def _find_slice_index(sm: SymbolMap, pin_name: str) -> int | None:
    """Return the index of the slice that owns pin_name, or None."""
    for i, slc in enumerate(sm.slices):
        if pin_name in slc.pin_map:
            return i
    return None


# ---------------------------------------------------------------------------
# Net lookup map
# ---------------------------------------------------------------------------


def _build_net_by_pin(ir: CircuitIR) -> dict[tuple[str, str], NetRef]:
    """Map (part_ref, pin_name) -> NetRef."""
    result: dict[tuple[str, str], NetRef] = {}
    for net in ir.nets:
        for pin in net.pins:
            result[(pin.part_ref, pin.pin_name)] = net
    return result


def _other_pin(net: NetRef, part_ref: str, pin_name: str) -> tuple[str, str]:
    """For a 2-pin CHAIN net, return the other pin."""
    for pin in net.pins:
        if pin.part_ref != part_ref or pin.pin_name != pin_name:
            return pin.part_ref, pin.pin_name
    msg = f"Net {net.name} has no other pin besides ({part_ref}, {pin_name})"
    raise PCBBuildError(msg)


# ---------------------------------------------------------------------------
# Placed-symbol builders
# ---------------------------------------------------------------------------


def _label_symbol(text: str) -> Symbol:
    """Single-port glyph used for LABEL net column endpoints."""
    port = Port("1", Point(0, 0), Vector(0, -1))
    elements: list[Element] = [
        Text(
            content=text,
            position=Point(0, 5.0),
            style=Style(stroke="none", fill="black"),
            anchor="middle",
            font_size=3.0,
        )
    ]
    return Symbol(elements=elements, ports={"1": port}, label=text)


def _label_symbol_factory(net_name: str) -> Any:  # noqa: ANN401
    """Return a zero-arg factory producing a label symbol for net_name."""

    def factory(*_args: Any, **_kwargs: Any) -> Symbol:  # noqa: ANN401
        return _label_symbol(net_name)

    return factory


def _placed_symbol_for_connector_terminator(
    t: _ConnectorTerminator,
) -> _PlacedSymbol:
    rotated = t.cmap.position == "bottom"
    base_factory = t.cmap.pin_symbol
    pin_name = t.pin_name

    def factory(*args: Any, **kwargs: Any) -> Symbol:  # noqa: ANN401
        kwargs.setdefault("pin_label", pin_name)
        return base_factory(*args, **kwargs)

    return _PlacedSymbol(
        part_ref=f"{t.part_ref}_pin{t.pin_name}",
        symbol_factory=factory,
        entry_pin=None,
        tag_prefix=t.part_ref,
        rotated=rotated,
    )


def _placed_symbol_for_net_terminator(
    t: _NetEndpointTerminator, mapping: SymbolMapping
) -> _PlacedSymbol:
    for pn in mapping.power_nets:
        if pn.net_name == t.net.name:
            return _PlacedSymbol(
                part_ref=f"pwr_{t.net.name}",
                symbol_factory=pn.symbol,
                entry_pin=None,
                tag_prefix="PWR",
                rotated=False,
            )
    # LABEL net — synthesise a single-port text-glyph symbol so the endpoint
    # renders the net name on the column.
    return _PlacedSymbol(
        part_ref=f"lbl_{t.net.name}",
        symbol_factory=_label_symbol_factory(t.net.name),
        entry_pin=None,
        tag_prefix="LBL",
        rotated=False,
    )


def _placed_symbol_for_slice(
    part_ref: str,
    sm: SymbolMap,
    slice_index: int,
    entry_pin: str,
) -> _PlacedSymbol:
    slc = sm.slices[slice_index]
    entry_port_name = slc.pin_map[entry_pin]
    rotated = _should_rotate(slc.symbol, entry_port_name)
    return _PlacedSymbol(
        part_ref=part_ref,
        symbol_factory=slc.symbol,
        entry_pin=entry_pin,
        tag_prefix=part_ref,
        rotated=rotated,
    )


# ---------------------------------------------------------------------------
# Walk helpers — sub-functions to reduce complexity of _walk
# ---------------------------------------------------------------------------


def _resolve_net_endpoint_start(
    start: _NetEndpointTerminator,
    ir: CircuitIR,
    mapping: SymbolMapping,
) -> tuple[str, str, _PlacedSymbol] | None:
    """Return (out_part_ref, out_pin_name, start_placed) or None."""
    anchor_part = next((p for p in ir.parts if p.ref == start.pin_part_ref), None)
    if anchor_part is None:
        return None
    anchor_smap = _find_symbol_map(anchor_part.template_name, mapping)
    if anchor_smap is None:
        return None
    anchor_slice_idx = _find_slice_index(anchor_smap, start.pin_name)
    if anchor_slice_idx is None:
        return None
    exit_pin = _exit_pin_for_slice(anchor_smap, anchor_slice_idx, start.pin_name)
    ps = _placed_symbol_for_slice(
        start.pin_part_ref, anchor_smap, anchor_slice_idx, start.pin_name
    )
    return start.pin_part_ref, exit_pin, ps


def _append_net_endpoint_terminator(
    placed: list[_PlacedSymbol],
    exit_net: NetRef,
    current_part_ref: str,
    mapping: SymbolMapping,
) -> None:
    """Append the POWER/LABEL endpoint symbol for exit_net if found."""
    for pin in exit_net.pins:
        if pin.part_ref != current_part_ref:
            end_t = _NetEndpointTerminator(
                net=exit_net,
                pin_part_ref=pin.part_ref,
                pin_name=pin.pin_name,
            )
            placed.append(_placed_symbol_for_net_terminator(end_t, mapping))
            return


def _process_slice_at(
    other_part_ref: str,
    other_pin_name: str,
    other_template_name: str,
    mapping: SymbolMapping,
    placed: list[_PlacedSymbol],
    placed_slices: set[tuple[str, int]],
) -> str:
    """Resolve, place, and return exit pin for the slice at other_part / other_pin.

    Raises UnmappedPartError if the part has no SymbolMap.
    """
    other_smap = _find_symbol_map(other_template_name, mapping)
    if other_smap is None:
        raise UnmappedPartError(
            part_ref=other_part_ref,
            template_name=other_template_name,
        )
    slice_index = _find_slice_index(other_smap, other_pin_name)
    if slice_index is None:
        raise UnmappedPartError(
            part_ref=other_part_ref,
            template_name=other_template_name,
        )
    placed.append(
        _placed_symbol_for_slice(
            other_part_ref, other_smap, slice_index, other_pin_name
        )
    )
    placed_slices.add((other_part_ref, slice_index))
    return _exit_pin_for_slice(other_smap, slice_index, other_pin_name)


def _walk_loop(
    placed: list[_PlacedSymbol],
    start_part_ref: str,
    start_pin_name: str,
    ir: CircuitIR,
    mapping: SymbolMapping,
    net_kinds: dict[str, _NetKind],
    walked_chain_nets: set[str],
    placed_slices: set[tuple[str, int]],
    net_by_pin: dict[tuple[str, str], NetRef],
) -> bool:
    """Walks CHAIN nets, appending to *placed*; returns False on dedup."""
    current_part_ref = start_part_ref
    current_pin_name = start_pin_name

    while True:
        net = net_by_pin.get((current_part_ref, current_pin_name))
        if net is None or net_kinds.get(net.name) != _NetKind.CHAIN:
            break

        if net.name in walked_chain_nets:
            return False
        walked_chain_nets.add(net.name)

        other_part_ref, other_pin_name = _other_pin(
            net, current_part_ref, current_pin_name
        )
        other_part = next((p for p in ir.parts if p.ref == other_part_ref), None)
        if other_part is None:
            # The net's other endpoint references a part not present in the IR.
            # Adapter guarantees this can't happen for well-formed circuits; if
            # it does, any slice left unplaced will surface via _check_orphans.
            break

        other_cmap = _find_connector_map(other_part.template_name, mapping)
        if other_cmap is not None:
            end_t = _ConnectorTerminator(
                cmap=other_cmap,
                pin_name=other_pin_name,
                part_ref=other_part_ref,
            )
            placed.append(_placed_symbol_for_connector_terminator(end_t))
            break

        exit_pin = _process_slice_at(
            other_part_ref,
            other_pin_name,
            other_part.template_name,
            mapping,
            placed,
            placed_slices,
        )
        current_part_ref = other_part_ref
        current_pin_name = exit_pin

        exit_net = net_by_pin.get((current_part_ref, current_pin_name))
        if exit_net is None:
            # Slice exit pin isn't on any net — dangling. Any mapped slice left
            # unplaced after all walks complete is caught by _check_orphans.
            break
        if net_kinds.get(exit_net.name) in (_NetKind.POWER, _NetKind.LABEL):
            _append_net_endpoint_terminator(placed, exit_net, current_part_ref, mapping)
            break

    return True


# ---------------------------------------------------------------------------
# Phase 3 — walk chains
# ---------------------------------------------------------------------------


def _anchor_slice_key_for(
    start: _NetEndpointTerminator,
    ir: CircuitIR,
    mapping: SymbolMapping,
) -> tuple[str, int] | None:
    """Return (part_ref, slice_index) for a LABEL/POWER anchor, or None."""
    part = next((p for p in ir.parts if p.ref == start.pin_part_ref), None)
    if part is None:
        return None
    smap = _find_symbol_map(part.template_name, mapping)
    if smap is None:
        return None
    slice_idx = _find_slice_index(smap, start.pin_name)
    if slice_idx is None:
        return None
    return (start.pin_part_ref, slice_idx)


def _make_column(placed: list[_PlacedSymbol]) -> _Column:
    return _Column(
        key="",
        placed_symbols=tuple(placed),
        width_mm=DEFAULT_COLUMN_WIDTH,
        height_mm=len(placed) * DEFAULT_SYMBOL_SLOT_HEIGHT,
    )


def _emit_label_label_column(
    start_placed: _PlacedSymbol,
    outward_net: NetRef,
    out_part_ref: str,
    mapping: SymbolMapping,
) -> _Column:
    """Emit [start, slice, end] when both sides are POWER/LABEL."""
    placed: list[_PlacedSymbol] = [start_placed]
    _append_net_endpoint_terminator(placed, outward_net, out_part_ref, mapping)
    return _make_column(placed)


def _resolve_walk_start(
    start: _Terminator,
    ir: CircuitIR,
    mapping: SymbolMapping,
    placed_slices: set[tuple[str, int]],
) -> tuple[str, str, _PlacedSymbol, tuple[str, int] | None] | None:
    """Return (out_part_ref, out_pin_name, start_placed, anchor_slice_key)."""
    if isinstance(start, _ConnectorTerminator):
        return (
            start.part_ref,
            start.pin_name,
            _placed_symbol_for_connector_terminator(start),
            None,
        )
    resolved = _resolve_net_endpoint_start(start, ir, mapping)
    if resolved is None:
        return None
    out_part_ref, out_pin_name, start_placed = resolved
    anchor_key = _anchor_slice_key_for(start, ir, mapping)
    if anchor_key is not None and anchor_key in placed_slices:
        return None
    return out_part_ref, out_pin_name, start_placed, anchor_key


def _walk(
    start: _Terminator,
    ir: CircuitIR,
    mapping: SymbolMapping,
    net_kinds: dict[str, _NetKind],
    walked_chain_nets: set[str],
    placed_slices: set[tuple[str, int]],
    net_by_pin: dict[tuple[str, str], NetRef],
) -> _Column | None:
    """Walk from a terminator through CHAIN nets until another terminator."""
    resolved = _resolve_walk_start(start, ir, mapping, placed_slices)
    if resolved is None:
        return None
    out_part_ref, out_pin_name, start_placed, anchor_slice_key = resolved

    outward_net = net_by_pin.get((out_part_ref, out_pin_name))
    if outward_net is None or outward_net.name in walked_chain_nets:
        return None

    outward_kind = net_kinds.get(outward_net.name)
    label_power = {_NetKind.POWER, _NetKind.LABEL}
    if outward_kind in label_power and anchor_slice_key is not None:
        placed_slices.add(anchor_slice_key)
        return _emit_label_label_column(
            start_placed, outward_net, out_part_ref, mapping
        )
    if outward_kind != _NetKind.CHAIN:
        return None

    if anchor_slice_key is not None:
        placed_slices.add(anchor_slice_key)

    placed = [start_placed]
    ok = _walk_loop(
        placed,
        out_part_ref,
        out_pin_name,
        ir,
        mapping,
        net_kinds,
        walked_chain_nets,
        placed_slices,
        net_by_pin,
    )
    if not ok:
        return None
    return _make_column(placed)


# ---------------------------------------------------------------------------
# Phase 4 — pack pages
# ---------------------------------------------------------------------------


def _pack_pages(
    columns: list[_Column],
    page_size: tuple[float, float],
    column_spacing_mm: float,
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Greedy left-to-right packing; new page when width exceeded."""
    page_width = page_size[0]
    pages: list[tuple[str, list[str]]] = []
    current_keys: list[str] = []
    current_width: float = 0.0

    for col in columns:
        slot_width = col.width_mm + column_spacing_mm
        if current_keys and current_width + slot_width > page_width:
            pages.append((f"Page {len(pages) + 1}", current_keys))
            current_keys = []
            current_width = 0.0
        current_keys.append(col.key)
        current_width += slot_width

    if current_keys:
        pages.append((f"Page {len(pages) + 1}", current_keys))

    return tuple((title, tuple(keys)) for title, keys in pages)


# ---------------------------------------------------------------------------
# Phase 5 — render column to Circuit
# ---------------------------------------------------------------------------


def _render_column_to_circuit(
    column: _Column,
    state: Any,  # noqa: ANN401  # GenerationState; opaque to pcb module
    column_index: int,
    x_offset: float = 0.0,
) -> tuple[str, Circuit]:
    """Build a Schematika Circuit from a column's placed symbols."""
    key = f"pcb_col_{column_index:03d}"
    builder = CircuitBuilder(state)
    builder.set_layout(x=x_offset, y=0)

    for ps in column.placed_symbols:
        # Peek the symbol once to learn port names for pins=.
        pin_names = tuple(ps.symbol_factory().ports.keys())

        def make_factory(
            *,
            orig: Callable[..., Symbol] = ps.symbol_factory,
            rotated: bool = ps.rotated,
        ) -> Callable[..., Symbol]:
            def _f(*args: Any, **kwargs: Any) -> Symbol:  # noqa: ANN401
                sym = orig(*args, **kwargs)
                if rotated:
                    sym = rotate(sym, 180)
                return sym

            return _f

        builder.add_symbol(
            make_factory(),
            config=SymbolConfig(tag_prefix=ps.tag_prefix, pins=pin_names),
        )

    fixed_tags = {ps.tag_prefix: ps.tag_prefix for ps in column.placed_symbols}
    result = builder.build(fixed_tags=fixed_tags)
    return key, result.circuit


# ---------------------------------------------------------------------------
# Orphan detection
# ---------------------------------------------------------------------------


def _check_orphan_slices(
    ir: CircuitIR,
    mapping: SymbolMapping,
    placed_slices: set[tuple[str, int]],
) -> None:
    """All-NC slices are silent; truly disconnected slices raise OrphanSliceError."""
    nc_pin_set = frozenset(ir.nc_pins)
    for part_ref, slice_index in _all_mapped_slices(ir, mapping):
        if (part_ref, slice_index) in placed_slices:
            continue
        part = next(p for p in ir.parts if p.ref == part_ref)
        smap = _find_symbol_map(part.template_name, mapping)
        if smap is None:
            continue
        slice_pins = tuple(smap.slices[slice_index].pin_map.keys())
        if all((part_ref, pin) in nc_pin_set for pin in slice_pins):
            continue
        raise OrphanSliceError(part_ref=part_ref, slice_index=slice_index)


def _all_mapped_slices(ir: CircuitIR, mapping: SymbolMapping) -> list[tuple[str, int]]:
    """All (part_ref, slice_index) pairs for parts that have a SymbolMap."""
    result: list[tuple[str, int]] = []
    for part in ir.parts:
        smap = _find_symbol_map(part.template_name, mapping)
        if smap is None:
            continue
        result.extend((part.ref, i) for i in range(len(smap.slices)))
    return result


# ---------------------------------------------------------------------------
# Public: build  # noqa: ERA001
# ---------------------------------------------------------------------------


def build(
    circuit: Any,  # noqa: ANN401  # SKiDL Circuit; duck-typed boundary
    mapping: SymbolMapping,
    *,
    page_size: tuple[float, float] = A3_LANDSCAPE,
    column_spacing_mm: float = 40.0,
) -> PCBBuildResult:
    """Convert a SKiDL Circuit + SymbolMapping into a PCBBuildResult.

    Walks the netlist, classifies nets as chain/label/power, assigns each
    component slice to a column, packs columns into pages, and renders each
    column as a ``Circuit``.

    Args:
        circuit: A SKiDL ``Circuit`` object (duck-typed; any object with
            ``nets`` and ``parts`` attributes works).
        mapping: ``SymbolMapping`` that maps SKiDL template names to
            Schematika symbol slices and connector designators.
        page_size: ``(width_mm, height_mm)`` of the output page.
            Defaults to ``A3_LANDSCAPE`` (420 x 297 mm).
        column_spacing_mm: Horizontal gap between columns on the same page,
            in millimetres. Defaults to 40.0.

    Returns:
        PCBBuildResult: Frozen result containing the packed pages and
            per-column ``Circuit`` objects.

    Raises:
        UnmappedPartError: If a non-connector part has no ``SymbolMap`` entry
            in *mapping*.
        OrphanSliceError: If a mapped symbol slice is unreachable from any
            terminator (isolated loop in the netlist).
        HeightOverflowError: If a single column's rendered height exceeds the
            page height.

    Examples:
        >>> from schematika.pcb import PCBBuildError
        >>> try:
        ...     raise PCBBuildError("no mapping for R1")
        ... except PCBBuildError:
        ...     pass
        >>> # Full build requires a live SKiDL Circuit; see tests/test_pcb.py.
    """
    ir = adapt(circuit)

    # Phase 2 — classify nets
    net_kinds = _classify_nets(ir, mapping)

    # Validate: every non-connector part must have a SymbolMap
    for part in ir.parts:
        if _find_connector_map(part.template_name, mapping) is not None:
            continue
        if _find_symbol_map(part.template_name, mapping) is None:
            raise UnmappedPartError(
                part_ref=part.ref,
                template_name=part.template_name,
            )

    # Phase 3 — enumerate terminators + walk
    terminators = _enumerate_terminators(ir, mapping, net_kinds)
    net_by_pin = _build_net_by_pin(ir)
    walked_chain_nets: set[str] = set()
    placed_slices: set[tuple[str, int]] = set()
    raw_columns: list[_Column] = []

    for t in terminators:
        col = _walk(
            t, ir, mapping, net_kinds, walked_chain_nets, placed_slices, net_by_pin
        )
        if col is not None:
            raw_columns.append(col)

    _check_orphan_slices(ir, mapping, placed_slices)

    state = create_initial_state()
    column_circuits, pages = _render_and_pack(
        raw_columns, state, page_size, column_spacing_mm
    )

    return PCBBuildResult(
        state=state,
        columns=tuple(column_circuits),
        pages=pages,
    )


def _render_and_pack(
    raw_columns: list[_Column],
    state: Any,  # noqa: ANN401  # GenerationState; opaque to pcb module
    page_size: tuple[float, float],
    column_spacing_mm: float,
) -> tuple[list[tuple[str, Any]], tuple[tuple[str, tuple[str, ...]], ...]]:
    """Pack columns into pages and render each at its per-page x offset."""
    page_width = page_size[0]
    page_height = page_size[1]
    column_circuits: list[tuple[str, Any]] = []
    pages_keys: list[list[str]] = [[]]
    page_x: float = 0.0

    for idx, col in enumerate(raw_columns):
        if col.height_mm > page_height:
            raise HeightOverflowError(
                column_key=f"pcb_col_{idx:03d}",
                height_mm=col.height_mm,
                max_height_mm=page_height,
            )
        slot_width = col.width_mm + column_spacing_mm
        if pages_keys[-1] and page_x + slot_width > page_width:
            pages_keys.append([])
            page_x = 0.0
        key, circ = _render_column_to_circuit(col, state, idx, x_offset=page_x)
        column_circuits.append((key, circ))
        pages_keys[-1].append(key)
        page_x += slot_width

    pages = tuple(
        (f"Page {i + 1}", tuple(keys)) for i, keys in enumerate(pages_keys) if keys
    )
    return column_circuits, pages
