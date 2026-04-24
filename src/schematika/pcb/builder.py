"""Column traversal, page packing, and result assembly for schematika.pcb."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

from schematika.core.transform import rotate
from schematika.electrical.builder import CircuitBuilder
from schematika.electrical.model.state import create_initial_state
from schematika.electrical.system.system import Circuit

from .adapter import CircuitIR, NetRef, adapt
from .errors import HeightOverflowError, OrphanSliceError, UnmappedPartError
from .model import ConnectorMap, PCBBuildResult, SymbolMap, SymbolMapping

if TYPE_CHECKING:
    from schematika.project import Project  # noqa: F401

# Page size constants (mm), landscape orientation
A4_LANDSCAPE: tuple[float, float] = (297.0, 210.0)
A3_LANDSCAPE: tuple[float, float] = (420.0, 297.0)

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
        if n == 2:
            result[net.name] = _NetKind.CHAIN
        elif net.name in power_net_names:
            result[net.name] = _NetKind.POWER
        else:
            result[net.name] = _NetKind.LABEL
    return result


# ---------------------------------------------------------------------------
# Mapping helpers
# ---------------------------------------------------------------------------


def _template_name_of(template: Any) -> str:
    return str(getattr(template, "name", repr(template)))


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
        for pin_name in part.pin_numbers:
            terminators.append(
                _ConnectorTerminator(
                    cmap=cmap,
                    pin_name=pin_name,
                    part_ref=part.ref,
                )
            )

    # 2. POWER / LABEL nets — one terminator per pin occurrence
    for net in ir.nets:
        kind = net_kinds.get(net.name)
        if kind not in (_NetKind.POWER, _NetKind.LABEL):
            continue
        for pin in net.pins:
            terminators.append(
                _NetEndpointTerminator(
                    net=net,
                    pin_part_ref=pin.part_ref,
                    pin_name=pin.pin_name,
                )
            )

    return terminators


# ---------------------------------------------------------------------------
# Rotation heuristic
# ---------------------------------------------------------------------------

# Heuristic: inspect the entry port's direction vector; if dy > 0 (faces DOWN
# in SVG coordinates where y grows downward), rotate 180° so the entry aligns
# upward toward the incoming wire.


def _should_rotate(symbol_factory: Any, port_name: str) -> bool:
    """Return True if the entry port naturally faces down (needs 180° flip)."""
    try:
        sym = symbol_factory()
        port = sym.ports.get(port_name)
        if port is None:
            return False
        return port.direction.dy > 0
    except Exception:
        return False


def _apply_rotation_if_needed(symbol_factory: Any, port_name: str) -> tuple[Any, bool]:
    """Return (factory_unchanged, rotated_bool)."""
    rotated = _should_rotate(symbol_factory, port_name)
    return symbol_factory, rotated


# ---------------------------------------------------------------------------
# Slice helpers
# ---------------------------------------------------------------------------


def _exit_pin_for_slice(sm: SymbolMap, slice_index: int, entry_pin: str) -> str:
    """For a 2-pin slice, return the pin that is not entry_pin."""
    slc = sm.slices[slice_index]
    for pin_name in slc.pin_map:
        if pin_name != entry_pin:
            return pin_name
    raise ValueError(
        f"Slice {slice_index} of {_template_name_of(sm.template)} "
        f"has no exit pin after removing entry={entry_pin}"
    )


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
    raise ValueError(
        f"Net {net.name} has no other pin besides ({part_ref}, {pin_name})"
    )


# ---------------------------------------------------------------------------
# Placed-symbol builders
# ---------------------------------------------------------------------------


def _placed_symbol_for_connector_terminator(
    t: _ConnectorTerminator,
) -> _PlacedSymbol:
    rotated = t.cmap.position == "bottom"
    return _PlacedSymbol(
        part_ref=f"{t.part_ref}_pin{t.pin_name}",
        symbol_factory=t.cmap.pin_symbol,
        entry_pin=None,
        tag_prefix="J",
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
    # LABEL net — no dedicated symbol; placeholder with None factory
    return _PlacedSymbol(
        part_ref=f"lbl_{t.net.name}",
        symbol_factory=None,
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
    _, rotated = _apply_rotation_if_needed(slc.symbol, entry_port_name)
    return _PlacedSymbol(
        part_ref=part_ref,
        symbol_factory=slc.symbol,
        entry_pin=entry_pin,
        tag_prefix=part_ref[0] if part_ref else "X",
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
    """Walk CHAIN nets from start_part_ref/start_pin_name, appending to placed.

    Returns True if walk completed normally, False if dedup triggered.
    """
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
            break
        if net_kinds.get(exit_net.name) in (_NetKind.POWER, _NetKind.LABEL):
            _append_net_endpoint_terminator(placed, exit_net, current_part_ref, mapping)
            break

    return True


# ---------------------------------------------------------------------------
# Phase 3 — walk chains
# ---------------------------------------------------------------------------


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
    # Determine outward pin and start symbol.
    # For a connector: the pin itself faces into the circuit.
    # For a net-endpoint: the LABEL/POWER pin is the anchor; the other mapped
    # pin of the same part is the circuit-facing exit.
    if isinstance(start, _ConnectorTerminator):
        out_part_ref = start.part_ref
        out_pin_name = start.pin_name
        start_placed = _placed_symbol_for_connector_terminator(start)
    else:
        resolved = _resolve_net_endpoint_start(start, ir, mapping)
        if resolved is None:
            return None
        out_part_ref, out_pin_name, start_placed = resolved

    outward_net = net_by_pin.get((out_part_ref, out_pin_name))
    if outward_net is None or net_kinds.get(outward_net.name) != _NetKind.CHAIN:
        return None
    if outward_net.name in walked_chain_nets:
        return None

    placed: list[_PlacedSymbol] = [start_placed]
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

    height = len(placed) * DEFAULT_SYMBOL_SLOT_HEIGHT
    return _Column(
        key="",
        placed_symbols=tuple(placed),
        width_mm=DEFAULT_COLUMN_WIDTH,
        height_mm=height,
    )


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
    state: Any,
    column_index: int,
) -> tuple[str, Circuit]:
    """Build a Schematika Circuit from a column's placed symbols."""
    key = f"pcb_col_{column_index:03d}"
    builder = CircuitBuilder(state)
    builder.set_layout(x=0, y=0)

    for ps in column.placed_symbols:
        if ps.symbol_factory is None:
            # LABEL placeholder — no symbol to render
            continue
        sym = ps.symbol_factory()
        if ps.rotated:
            sym = rotate(sym, 180)

        def make_factory(s=sym):
            def _f(*_args, **_kwargs):
                return s

            return _f

        builder.add_symbol(make_factory(), tag_prefix=ps.tag_prefix)

    result = builder.build()
    return key, result.circuit


# ---------------------------------------------------------------------------
# Orphan detection
# ---------------------------------------------------------------------------


def _all_mapped_slices(ir: CircuitIR, mapping: SymbolMapping) -> list[tuple[str, int]]:
    """All (part_ref, slice_index) pairs for parts that have a SymbolMap."""
    result: list[tuple[str, int]] = []
    for part in ir.parts:
        smap = _find_symbol_map(part.template_name, mapping)
        if smap is None:
            continue
        for i in range(len(smap.slices)):
            result.append((part.ref, i))
    return result


# ---------------------------------------------------------------------------
# Public: build
# ---------------------------------------------------------------------------


def build(
    circuit: Any,
    mapping: SymbolMapping,
    *,
    page_size: tuple[float, float] = A3_LANDSCAPE,
    column_spacing_mm: float = 40.0,
) -> PCBBuildResult:
    """Convert a SKiDL Circuit + SymbolMapping into a PCBBuildResult."""
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

    # Orphan check
    for part_ref, slice_index in _all_mapped_slices(ir, mapping):
        if (part_ref, slice_index) not in placed_slices:
            raise OrphanSliceError(part_ref=part_ref, slice_index=slice_index)

    # Phase 4+5 — render, check height, collect
    state = create_initial_state()
    built_columns: list[_Column] = []
    column_circuits: list[tuple[str, Any]] = []
    page_height = page_size[1]

    for idx, col in enumerate(raw_columns):
        if col.height_mm > page_height:
            key_temp = f"pcb_col_{idx:03d}"
            raise HeightOverflowError(
                column_key=key_temp,
                height_mm=col.height_mm,
                max_height_mm=page_height,
            )
        key, circ = _render_column_to_circuit(col, state, idx)
        built_columns.append(
            _Column(
                key=key,
                placed_symbols=col.placed_symbols,
                width_mm=col.width_mm,
                height_mm=col.height_mm,
            )
        )
        column_circuits.append((key, circ))

    pages = _pack_pages(built_columns, page_size, column_spacing_mm)

    return PCBBuildResult(
        state=state,
        columns=tuple(column_circuits),
        pages=pages,
    )


# ---------------------------------------------------------------------------
# Public: add_to_project
# ---------------------------------------------------------------------------


def add_to_project(project: "Project", result: PCBBuildResult) -> None:
    """Register all columns + pages on a Project."""
    for key, circuit in result.columns:
        project.add_circuit(
            key,
            builder_fn=lambda state, c=circuit: _circuit_to_build_result(state, c),
        )
    for title, col_keys in result.pages:
        project.page(title, list(col_keys))


def _circuit_to_build_result(state: Any, circuit: Circuit) -> Any:
    """Wrap a pre-built Circuit in a BuildResult."""
    from schematika.electrical.builder_models import BuildResult

    return BuildResult(state=state, circuit=circuit, used_terminals=[])
