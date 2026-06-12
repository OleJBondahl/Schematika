"""Internal four-phase build pipeline used by `CircuitBuilder.build()`."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, Final

import deal

from schematika.core.exceptions import (
    CircuitValidationError,
    TagReuseError,
)
from schematika.core.options import _ConnectionPair
from schematika.electrical.builder_models import RealizedComponent, realized_to_dict
from schematika.electrical.builder_utils import (
    _distribute_pins,
    _find_port,
    _get_absolute_x_offset,
    _resolve_pin,
    _resolve_registry_pin,
)
from schematika.electrical.layout.layout import draw_wire
from schematika.electrical.layout.wire_labels import (
    calculate_wire_label_position,
    create_wire_label_text,
)
from schematika.electrical.model.parts import standard_style
from schematika.electrical.model.primitives import Line
from schematika.electrical.symbols.terminals import (
    _multi_pole_terminal,
    _terminal_single_pole,
)
from schematika.electrical.system.connection_registry import log_connection
from schematika.electrical.system.system import Circuit, add_symbol
from schematika.electrical.utils.autonumbering import next_tag, next_terminal_pins

if TYPE_CHECKING:
    from collections.abc import Callable

    from schematika.core.geometry import Style
    from schematika.core.symbol import Symbol
    from schematika.electrical.builder_models import (
        CircuitSpec,
        ComponentSpec,
        PlannedConnection,
    )
    from schematika.electrical.model.state import GenerationState

# Minimum poles for a multi-pole terminal symbol.
_MULTI_POLE_MIN: Final = 2
# Tolerance for vertical wire label detection.
_WIRE_VERTICAL_THRESHOLD: Final = 0.1


@deal.pure
def _resolve_terminal_id(
    component_spec: ComponentSpec,
    terminal_maps: dict[str, Any] | None,
    spec_terminal_map: dict[str, Any],
) -> str | int:
    """2-priority lookup: runtime override → spec map → fallback to kwargs."""
    tid: str | int = component_spec.kwargs["tm_id"]
    lname = component_spec.kwargs.get("logical_name")
    if terminal_maps and lname and lname in terminal_maps:
        return terminal_maps[lname]
    if lname and lname in spec_terminal_map:
        return spec_terminal_map[lname]
    return tid


def _resolve_terminal_pins(
    state: GenerationState,
    component_spec: ComponentSpec,
    tid: str | int,
    lname: str | None,
    terminal_reuse_generators: dict[str, Callable] | None,
) -> tuple[GenerationState, list[str]]:
    """3-source pin chain: explicit pins → reuse generator → fresh allocation."""
    if component_spec.pins:
        return state, list(component_spec.pins)
    if terminal_reuse_generators and (
        str(tid) in terminal_reuse_generators
        or (lname and lname in terminal_reuse_generators)
    ):
        reuse_key = (
            lname if (lname and lname in terminal_reuse_generators) else str(tid)
        )
        state, pin_tuple = terminal_reuse_generators[reuse_key](
            state, component_spec.poles
        )
        return state, list(pin_tuple)
    state, pin_tuple = next_terminal_pins(
        state,
        tid,  # ty: ignore[invalid-argument-type]
        component_spec.poles,
        pin_prefixes=component_spec.pin_prefixes,
    )
    return state, list(pin_tuple)


def _track_pin_accumulator(
    pin_accumulator: dict[str, list[str]] | None,
    lname: str | None,
    tid: str | int,
    pins: list[str],
) -> None:
    """Mutates pin_accumulator in place; no-op when pin_accumulator is None."""
    if pin_accumulator is None:
        return
    map_key = lname if lname else str(tid)
    if map_key not in pin_accumulator:
        pin_accumulator[map_key] = []
    pin_accumulator[map_key].extend(pins)


@deal.raises(CircuitValidationError, TagReuseError)
def _resolve_symbol_or_reference_tag(
    state: GenerationState,
    component_spec: ComponentSpec,
    tag_generators: dict[str, Callable] | None,
    instance_tags: dict[str, str],
) -> tuple[GenerationState, str]:
    """Generates a tag for a symbol/reference component; records it in instance_tags."""
    prefix = component_spec.tag_prefix
    if prefix is None:
        msg = f"tag_prefix is required for component of kind '{component_spec.kind}'"
        raise CircuitValidationError(msg)
    if tag_generators and prefix in tag_generators:
        state, tag = tag_generators[prefix](state)
    else:
        state, tag = next_tag(state, prefix)
    instance_tags[prefix] = tag
    return state, tag


@deal.pure
def _compute_component_y(
    component_spec: ComponentSpec,
    current_y: float,
    realized_components: list[dict[str, Any]],
    layout_spacing: float,
) -> tuple[float, float]:
    """3-way Y: placed_right_of → ref y; above/below → placeholder; else stack."""
    if component_spec.placed_right_of is not None:
        return realized_components[component_spec.placed_right_of]["y"], current_y
    if (
        component_spec.placed_above_of is not None
        or component_spec.placed_below_of is not None
    ):
        return current_y, current_y
    comp_y = current_y
    new_current_y = current_y + component_spec.get_y_increment(layout_spacing)
    return comp_y, new_current_y


def _phase1_tag_and_state(
    state: GenerationState,
    y: float,
    spec: CircuitSpec,
    tag_generators: dict[str, Callable] | None,
    terminal_maps: dict[str, Any] | None,
    terminal_reuse_generators: dict[str, Callable] | None,
    pin_accumulator: dict[str, list[str]] | None,
) -> tuple[GenerationState, list[dict[str, Any]], dict[str, str]]:
    """Phase 1: assign tags/pins, compute initial Y; populates `realized_components`."""
    instance_tags: dict[str, str] = {}
    realized_components: list[dict[str, Any]] = []
    current_y = y

    for component_spec in spec.components:
        if component_spec.kind == "terminal":
            lname = component_spec.kwargs.get("logical_name")
            tid = _resolve_terminal_id(component_spec, terminal_maps, spec.terminal_map)
            state, pins = _resolve_terminal_pins(
                state,
                component_spec,
                tid,
                lname,
                terminal_reuse_generators,
            )
            _track_pin_accumulator(pin_accumulator, lname, tid, pins)
            tag = str(tid)
        elif component_spec.kind in ("symbol", "reference"):
            state, tag = _resolve_symbol_or_reference_tag(
                state,
                component_spec,
                tag_generators,
                instance_tags,
            )
            pins = list(component_spec.pins) if component_spec.pins else []
        else:
            # Unknown component_spec.kind: preserve original implicit fall-through.
            # tag and pins remain at the loop-init defaults (None, []).
            tag = None
            pins = []

        comp_y, current_y = _compute_component_y(
            component_spec,
            current_y,
            realized_components,
            spec.layout.symbol_spacing,
        )

        rc = RealizedComponent(
            spec=component_spec, tag=tag or "", pins=tuple(pins), y=comp_y
        )
        realized_components.append(realized_to_dict(rc))

    return state, realized_components, instance_tags


@deal.pure
def _should_auto_connect(curr: dict[str, Any], next_comp: dict[str, Any]) -> bool:
    """Returns False when the linear loop should skip this adjacent pair."""
    if not curr["spec"].connect_to_next:
        return False
    s = next_comp["spec"]
    return (
        s.placed_right_of is None
        and s.placed_above_of is None
        and s.placed_below_of is None
    )


def _register_connection_pair(
    state: GenerationState,
    pair: _ConnectionPair,
) -> tuple[GenerationState, tuple[str, str, str, str] | None]:
    """5-arm kind-pair dispatch; returns updated state and wire tuple or None."""
    kind_from = pair.comp_from["spec"].kind
    kind_to = pair.comp_to["spec"].kind

    if kind_from == "terminal" and kind_to in ("symbol", "reference"):
        reg_pin = _resolve_registry_pin(pair.comp_from, pair.p_from)
        side = pair.side_from or "bottom"
        state = log_connection(
            state,
            pair.comp_from["tag"],
            reg_pin,
            pair.comp_to["tag"],
            pair.pin_to,
            side=side,
        )
        return state, (pair.comp_from["tag"], reg_pin, pair.comp_to["tag"], pair.pin_to)

    if kind_from in ("symbol", "reference") and kind_to == "terminal":
        reg_pin = _resolve_registry_pin(pair.comp_to, pair.p_to)
        side = pair.side_to or "top"
        state = log_connection(
            state,
            pair.comp_to["tag"],
            reg_pin,
            pair.comp_from["tag"],
            pair.pin_from,
            side=side,
        )
        return state, (
            pair.comp_from["tag"],
            pair.pin_from,
            pair.comp_to["tag"],
            reg_pin,
        )

    if kind_from == "reference" and kind_to == "symbol":
        if pair.comp_from["pins"]:
            ref_pin = pair.comp_from["pins"][0]
        else:
            state, ref_pins = next_terminal_pins(state, pair.comp_from["tag"], 1)
            ref_pin = ref_pins[0]
        side = pair.side_from or "bottom"
        state = log_connection(
            state,
            pair.comp_from["tag"],
            ref_pin,
            pair.comp_to["tag"],
            pair.pin_to,
            side=side,
        )
        return state, (pair.comp_from["tag"], ref_pin, pair.comp_to["tag"], pair.pin_to)

    if kind_from == "symbol" and kind_to == "reference":
        if pair.comp_to["pins"]:
            ref_pin = pair.comp_to["pins"][0]
        else:
            state, ref_pins = next_terminal_pins(state, pair.comp_to["tag"], 1)
            ref_pin = ref_pins[0]
        side = pair.side_to or "top"
        state = log_connection(
            state,
            pair.comp_to["tag"],
            ref_pin,
            pair.comp_from["tag"],
            pair.pin_from,
            side=side,
        )
        return state, (
            pair.comp_from["tag"],
            pair.pin_from,
            pair.comp_to["tag"],
            ref_pin,
        )

    if kind_from == "symbol" and kind_to == "symbol":
        return state, (
            pair.comp_from["tag"],
            pair.pin_from,
            pair.comp_to["tag"],
            pair.pin_to,
        )

    return state, None


def _register_linear_connections(
    state: GenerationState,
    realized_components: list[dict[str, Any]],
) -> tuple[GenerationState, list[tuple[str, str, str, str]]]:
    """Encapsulates the linear auto-connection loop."""
    wires: list[tuple[str, str, str, str]] = []
    for i in range(len(realized_components) - 1):
        curr = realized_components[i]
        next_comp = realized_components[i + 1]
        if not _should_auto_connect(curr, next_comp):
            continue
        poles = min(curr["spec"].poles, next_comp["spec"].poles)
        for p in range(poles):
            curr_pin = _resolve_pin(curr, p, is_input=False)
            next_pin = _resolve_pin(next_comp, p, is_input=True)
            state, wire = _register_connection_pair(
                state,
                _ConnectionPair(
                    comp_from=curr,
                    pin_from=curr_pin,
                    side_from=curr["spec"].connection_side,
                    p_from=p,
                    comp_to=next_comp,
                    pin_to=next_pin,
                    side_to=next_comp["spec"].connection_side,
                    p_to=p,
                ),
            )
            if wire is not None:
                wires.append(wire)
    return state, wires


def _register_manual_connections(
    state: GenerationState,
    realized_components: list[dict[str, Any]],
    manual_connections: list[tuple[int, int, int, int, str, str]],
) -> tuple[GenerationState, list[tuple[str, str, str, str]]]:
    """Encapsulates the manual connection loop."""
    wires: list[tuple[str, str, str, str]] = []
    for idx_a, p_a, idx_b, p_b, side_a, side_b in manual_connections:
        if idx_a >= len(realized_components) or idx_b >= len(realized_components):
            continue
        comp_a = realized_components[idx_a]
        comp_b = realized_components[idx_b]
        pin_a = _resolve_pin(comp_a, p_a, is_input=(side_a == "top"))
        pin_b = _resolve_pin(comp_b, p_b, is_input=(side_b == "top"))
        state, wire = _register_connection_pair(
            state,
            _ConnectionPair(
                comp_from=comp_a,
                pin_from=pin_a,
                side_from=side_a,
                p_from=p_a,
                comp_to=comp_b,
                pin_to=pin_b,
                side_to=side_b,
                p_to=p_b,
            ),
        )
        if wire is not None:
            wires.append(wire)
    return state, wires


def _phase2_register_connections(
    state: GenerationState,
    realized_components: list[dict[str, Any]],
    spec: CircuitSpec,
) -> tuple[GenerationState, list[tuple[str, str, str, str]]]:
    """Phase 2: register linear + manual connections in the registry."""
    state, linear_wires = _register_linear_connections(state, realized_components)
    state, manual_wires = _register_manual_connections(
        state,
        realized_components,
        spec.manual_connections,
    )
    return state, linear_wires + manual_wires


@deal.raises(CircuitValidationError)
def _compute_above_or_below_position(
    component_spec: ComponentSpec,
    realized_components: list[dict[str, Any]],
    layout_spacing: float,
) -> tuple[float, float]:
    """Unifies placed_above_of and placed_below_of arms; sign encodes direction."""
    if component_spec.placed_above_of is not None:
        ref_idx, pin_name = component_spec.placed_above_of
        sign = -1
    else:
        ref_idx, pin_name = component_spec.placed_below_of  # ty: ignore[not-iterable]
        sign = 1
    ref_rc = realized_components[ref_idx]
    port = _find_port(ref_rc["symbol"], pin_name, ref_rc["spec"].pins)
    if port is None:
        msg = f"Port '{pin_name}' not found on symbol '{ref_rc['tag']}'"
        raise CircuitValidationError(msg)
    y_offset = (
        component_spec.y_increment
        if component_spec.y_increment is not None
        else layout_spacing / 2
    )
    return port.position.x + component_spec.x_offset, port.position.y + sign * y_offset


@deal.pure
def _compute_placed_right_position(
    component_spec: ComponentSpec,
    realized_components: list[dict[str, Any]],
    x: float,
) -> float:
    """Resolves final_x for placed_right_of; chain-walk via _get_absolute_x_offset."""
    ref_rc = realized_components[component_spec.placed_right_of]  # ty: ignore[invalid-argument-type]
    ref_x_offset = ref_rc["spec"].x_offset
    if ref_rc["spec"].placed_right_of is not None:
        ref_x_offset = _get_absolute_x_offset(
            realized_components,
            component_spec.placed_right_of,  # ty: ignore[invalid-argument-type]
        )
    return x + ref_x_offset + component_spec.x_offset


def _make_terminal_symbol(
    tag: str,
    rc: dict[str, Any],
    component_spec: ComponentSpec,
) -> Symbol:
    """Selects multi-pole vs single-pole terminal factory based on pole count."""
    lpos = component_spec.kwargs.get("label_pos") or "left"
    plpos = component_spec.kwargs.get("pin_label_pos")
    if component_spec.poles >= _MULTI_POLE_MIN:
        return _multi_pole_terminal(
            tag,
            pins=rc["pins"],
            poles=component_spec.poles,
            label_pos=lpos,
            pin_label_pos=plpos,
        )
    return _terminal_single_pole(
        tag, pins=rc["pins"], label_pos=lpos, pin_label_pos=plpos
    )


def _make_factory_symbol(
    tag: str,
    rc: dict[str, Any],
    component_spec: ComponentSpec,
) -> Symbol:
    """Distributes pins and forwards poles (via inspect) to the component factory."""
    kwargs = component_spec.kwargs.copy()
    if rc["pins"]:
        pin_kwargs = _distribute_pins(component_spec.func, rc["pins"], kwargs)
        kwargs.update(pin_kwargs)
    if (
        component_spec.poles > 1
        and "poles" not in kwargs
        and component_spec.func is not None
    ):
        sig = inspect.signature(component_spec.func)
        if "poles" in sig.parameters:
            kwargs["poles"] = component_spec.poles
    return component_spec.func(tag, **kwargs)  # ty: ignore[call-non-callable]


def _phase3_instantiate_symbols(
    c: Circuit,
    realized_components: list[dict[str, Any]],
    spec: CircuitSpec,
    x: float,
) -> None:
    """Phase 3: call symbol factories; mutates `c`; adds `symbol` to each entry."""
    for rc in realized_components:
        component_spec = rc["spec"]
        tag = rc["tag"]

        if (
            component_spec.placed_above_of is not None
            or component_spec.placed_below_of is not None
        ):
            final_x, rc["y"] = _compute_above_or_below_position(
                component_spec, realized_components, spec.layout.symbol_spacing
            )
        elif component_spec.placed_right_of is not None:
            final_x = _compute_placed_right_position(
                component_spec, realized_components, x
            )
        else:
            final_x = x + component_spec.x_offset

        if component_spec.kind == "terminal":
            sym = _make_terminal_symbol(tag, rc, component_spec)
        elif component_spec.kind in ("symbol", "reference"):
            sym = _make_factory_symbol(tag, rc, component_spec)
        else:
            sym = None  # Unknown kind: preserve fall-through

        if sym is not None:
            placed_sym = add_symbol(c, sym, final_x, rc["y"])
            rc["symbol"] = placed_sym


@deal.pure
def _get_endpoint_symbols(
    realized_components: list[dict[str, Any]],
    idx_a: int,
    idx_b: int,
) -> tuple[Symbol, Symbol] | None:
    if idx_a >= len(realized_components) or idx_b >= len(realized_components):
        return None
    comp_a = realized_components[idx_a]
    comp_b = realized_components[idx_b]
    if "symbol" not in comp_a or "symbol" not in comp_b:
        return None
    return comp_a["symbol"], comp_b["symbol"]


def _render_manual_connections(
    c: Circuit,
    realized_components: list[dict[str, Any]],
    manual_connections: list[tuple[int, int, int, int, str, str]],
    connection_wire_labels: dict[int, str],
    style: Style,
) -> None:
    """Render manual wires; labels only on vertical lines (ISA 5.1 convention)."""
    for conn_idx, (idx_a, p_a, idx_b, p_b, side_a, side_b) in enumerate(
        manual_connections
    ):
        syms = _get_endpoint_symbols(realized_components, idx_a, idx_b)
        if syms is None:
            continue
        sym_a, sym_b = syms
        comp_a = realized_components[idx_a]
        comp_b = realized_components[idx_b]
        pin_a = _resolve_pin(comp_a, p_a, is_input=(side_a == "top"))
        pin_b = _resolve_pin(comp_b, p_b, is_input=(side_b == "top"))
        port_a = _find_port(sym_a, pin_a, comp_a["spec"].pins)
        port_b = _find_port(sym_b, pin_b, comp_b["spec"].pins)
        if port_a and port_b:
            line = Line(port_a.position, port_b.position, style)
            c.elements.append(line)
            label = connection_wire_labels.get(conn_idx)
            is_vertical = abs(line.start.x - line.end.x) < _WIRE_VERTICAL_THRESHOLD
            if label and is_vertical:
                pos = calculate_wire_label_position(line.start, line.end)
                c.elements.append(create_wire_label_text(label, pos))


def _render_matching_connections(
    c: Circuit,
    realized_components: list[dict[str, Any]],
    matching_connections: list[tuple[int, int, list[str] | None, str, str]],
    style: Style,
) -> None:
    for idx_a, idx_b, pin_filter, _side_a, _side_b in matching_connections:
        syms = _get_endpoint_symbols(realized_components, idx_a, idx_b)
        if syms is None:
            continue
        sym_a, sym_b = syms
        comp_a = realized_components[idx_a]
        comp_b = realized_components[idx_b]
        pins_a = set(comp_a["pins"]) if comp_a["pins"] else set()
        pins_b = set(comp_b["pins"]) if comp_b["pins"] else set()
        common_pins = pins_a & pins_b
        if pin_filter is not None:
            common_pins = common_pins & set(pin_filter)
        for pin_name in common_pins:
            port_a = sym_a.ports.get(pin_name)
            port_b = sym_b.ports.get(pin_name)
            if port_a and port_b:
                line = Line(port_a.position, port_b.position, style)
                c.elements.append(line)


def _render_planned_chain_connections(
    c: Circuit,
    realized_components: list[dict[str, Any]],
    planned_connections: list[PlannedConnection],
    *,
    has_per_connection_labels: bool,
) -> None:
    """Applies wire_labels_above per segment when the target has them."""
    for pc in planned_connections:
        if pc.kind != "chain":
            continue
        syms = _get_endpoint_symbols(realized_components, pc.source_idx, pc.target_idx)
        if syms is None:
            continue
        sym1, sym2 = syms
        lines = draw_wire(sym1, sym2)
        c.elements.extend(lines)
        if has_per_connection_labels:
            tgt_spec = realized_components[pc.target_idx]["spec"]
            if tgt_spec.wire_labels_above:
                for j, wire_line in enumerate(lines):
                    if j < len(tgt_spec.wire_labels_above):
                        wl = tgt_spec.wire_labels_above[j]
                        if wl:
                            pos = calculate_wire_label_position(
                                wire_line.start, wire_line.end
                            )
                            c.elements.append(create_wire_label_text(wl, pos))


def _phase4_render_graphics(
    c: Circuit,
    realized_components: list[dict[str, Any]],
    spec: CircuitSpec,
) -> None:
    """Phase 4: render manual, matching, and planned-chain wires."""
    has_per_connection_labels = bool(spec.connection_wire_labels) or any(
        rc["spec"].wire_labels_above for rc in realized_components
    )
    style = standard_style()

    _render_manual_connections(
        c,
        realized_components,
        spec.manual_connections,
        spec.connection_wire_labels,
        style,
    )
    _render_matching_connections(
        c,
        realized_components,
        spec.matching_connections,
        style,
    )
    _render_planned_chain_connections(
        c,
        realized_components,
        spec.planned_connections,
        has_per_connection_labels=has_per_connection_labels,
    )


def _create_single_circuit_from_spec(
    state: GenerationState,
    x: float,
    y: float,
    spec: CircuitSpec,
    tag_generators: dict[str, Callable] | None = None,
    terminal_maps: dict[str, Any] | None = None,
    terminal_reuse_generators: dict[str, Callable] | None = None,
    pin_accumulator: dict[str, list[str]] | None = None,
) -> tuple[GenerationState, list[Any], dict[str, str], list[tuple[str, str, str, str]]]:
    """Mutates a shared `realized_components` list across four sequential phases."""
    c = Circuit()

    state, realized_components, instance_tags = _phase1_tag_and_state(
        state,
        y,
        spec,
        tag_generators,
        terminal_maps,
        terminal_reuse_generators,
        pin_accumulator,
    )
    # Symbols are instantiated before connections are registered so that
    # _resolve_pin can log real port IDs (e.g. "13"/"14" on a NO contact)
    # instead of fabricated sequential numbers.
    _phase3_instantiate_symbols(c, realized_components, spec, x)
    state, wire_connections = _phase2_register_connections(
        state, realized_components, spec
    )
    _phase4_render_graphics(c, realized_components, spec)

    return state, c.elements, instance_tags, wire_connections
