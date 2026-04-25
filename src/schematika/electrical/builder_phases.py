"""Internal four-phase build pipeline used by `CircuitBuilder.build()`."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

import deal

from schematika.core.exceptions import (
    CircuitValidationError,
    TagReuseError,
)
from schematika.electrical.builder_models import RealizedComponent, realized_to_dict
from schematika.electrical.builder_utils import (
    _distribute_pins,
    _find_port,
    _get_absolute_x_offset,
    _resolve_pin,
    _resolve_registry_pin,
)
from schematika.electrical.layout.layout import draw_wire
from schematika.electrical.symbols.terminals import (
    _multi_pole_terminal,
    _terminal_single_pole,
)
from schematika.electrical.system.connection_registry import log_connection
from schematika.electrical.system.system import Circuit, add_symbol
from schematika.electrical.utils.autonumbering import next_tag, next_terminal_pins

if TYPE_CHECKING:
    from collections.abc import Callable

    from schematika.electrical.builder_models import CircuitSpec, ComponentSpec
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


def _phase2_register_connections(
    state: GenerationState,
    realized_components: list[dict[str, Any]],
    spec: CircuitSpec,
) -> tuple[GenerationState, list[tuple[str, str, str, str]]]:
    """Phase 2: register linear + manual connections in the registry."""
    wire_connections: list[tuple[str, str, str, str]] = []

    # 1. Automatic Linear Connections
    for i in range(len(realized_components) - 1):
        curr = realized_components[i]
        next_comp = realized_components[i + 1]

        if not curr["spec"].connect_to_next:
            continue

        # Skip auto-connect for place_right / place_above / place_below components
        if next_comp["spec"].placed_right_of is not None:
            continue
        if next_comp["spec"].placed_above_of is not None:
            continue
        if next_comp["spec"].placed_below_of is not None:
            continue

        poles = min(curr["spec"].poles, next_comp["spec"].poles)

        for p in range(poles):
            curr_pin = _resolve_pin(curr, p, is_input=False)
            next_pin = _resolve_pin(next_comp, p, is_input=True)

            if curr["spec"].kind == "terminal" and next_comp["spec"].kind in (
                "symbol",
                "reference",
            ):
                reg_pin_curr = _resolve_registry_pin(curr, p)
                side = curr["spec"].connection_side or "bottom"
                state = log_connection(
                    state,
                    curr["tag"],
                    reg_pin_curr,
                    next_comp["tag"],
                    next_pin,
                    side=side,
                )
                wire_connections.append(
                    (curr["tag"], reg_pin_curr, next_comp["tag"], next_pin)
                )
            elif (
                curr["spec"].kind in ("symbol", "reference")
                and next_comp["spec"].kind == "terminal"
            ):
                reg_pin_next = _resolve_registry_pin(next_comp, p)
                side = next_comp["spec"].connection_side or "top"
                state = log_connection(
                    state,
                    next_comp["tag"],
                    reg_pin_next,
                    curr["tag"],
                    curr_pin,
                    side=side,
                )
                wire_connections.append(
                    (curr["tag"], curr_pin, next_comp["tag"], reg_pin_next)
                )
            elif (
                curr["spec"].kind == "reference" and next_comp["spec"].kind == "symbol"
            ):
                state, ref_pins = next_terminal_pins(state, curr["tag"], 1)
                ref_pin = ref_pins[0]
                state = log_connection(
                    state,
                    curr["tag"],
                    ref_pin,
                    next_comp["tag"],
                    next_pin,
                    side="bottom",
                )
                wire_connections.append(
                    (curr["tag"], ref_pin, next_comp["tag"], next_pin)
                )
            elif (
                curr["spec"].kind == "symbol" and next_comp["spec"].kind == "reference"
            ):
                state, ref_pins = next_terminal_pins(state, next_comp["tag"], 1)
                ref_pin = ref_pins[0]
                state = log_connection(
                    state,
                    next_comp["tag"],
                    ref_pin,
                    curr["tag"],
                    curr_pin,
                    side="top",
                )
                wire_connections.append(
                    (curr["tag"], curr_pin, next_comp["tag"], ref_pin)
                )
            elif curr["spec"].kind == "symbol" and next_comp["spec"].kind == "symbol":
                wire_connections.append(
                    (curr["tag"], curr_pin, next_comp["tag"], next_pin)
                )

    # 2. Manual Connections
    for idx_a, p_a, idx_b, p_b, side_a, side_b in spec.manual_connections:
        if idx_a >= len(realized_components) or idx_b >= len(realized_components):
            continue

        comp_a = realized_components[idx_a]
        comp_b = realized_components[idx_b]

        pin_a = _resolve_pin(comp_a, p_a, is_input=(side_a == "top"))
        pin_b = _resolve_pin(comp_b, p_b, is_input=(side_b == "top"))

        if comp_a["spec"].kind == "terminal" and comp_b["spec"].kind in (
            "symbol",
            "reference",
        ):
            reg_pin_a = _resolve_registry_pin(comp_a, p_a)
            state = log_connection(
                state, comp_a["tag"], reg_pin_a, comp_b["tag"], pin_b, side=side_a
            )
            wire_connections.append((comp_a["tag"], reg_pin_a, comp_b["tag"], pin_b))
        elif (
            comp_a["spec"].kind in ("symbol", "reference")
            and comp_b["spec"].kind == "terminal"
        ):
            reg_pin_b = _resolve_registry_pin(comp_b, p_b)
            state = log_connection(
                state, comp_b["tag"], reg_pin_b, comp_a["tag"], pin_a, side=side_b
            )
            wire_connections.append((comp_a["tag"], pin_a, comp_b["tag"], reg_pin_b))
        elif comp_a["spec"].kind == "reference" and comp_b["spec"].kind == "symbol":
            if comp_a["pins"]:
                ref_pin = comp_a["pins"][0]
            else:
                state, ref_pins = next_terminal_pins(state, comp_a["tag"], 1)
                ref_pin = ref_pins[0]
            state = log_connection(
                state, comp_a["tag"], ref_pin, comp_b["tag"], pin_b, side=side_a
            )
            wire_connections.append((comp_a["tag"], ref_pin, comp_b["tag"], pin_b))
        elif comp_a["spec"].kind == "symbol" and comp_b["spec"].kind == "reference":
            if comp_b["pins"]:
                ref_pin = comp_b["pins"][0]
            else:
                state, ref_pins = next_terminal_pins(state, comp_b["tag"], 1)
                ref_pin = ref_pins[0]
            state = log_connection(
                state, comp_b["tag"], ref_pin, comp_a["tag"], pin_a, side=side_b
            )
            wire_connections.append((comp_a["tag"], pin_a, comp_b["tag"], ref_pin))
        elif comp_a["spec"].kind == "symbol" and comp_b["spec"].kind == "symbol":
            wire_connections.append((comp_a["tag"], pin_a, comp_b["tag"], pin_b))

    return state, wire_connections


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

        # Calculate position
        if component_spec.placed_above_of is not None:
            ref_idx, pin_name = component_spec.placed_above_of
            ref_rc = realized_components[ref_idx]
            ref_sym = ref_rc["symbol"]
            port = _find_port(ref_sym, pin_name, ref_rc["spec"].pins)
            if port is None:
                msg = f"Port '{pin_name}' not found on symbol '{ref_rc['tag']}'"
                raise CircuitValidationError(msg)
            final_x = port.position.x + component_spec.x_offset
            y_offset = (
                component_spec.y_increment
                if component_spec.y_increment is not None
                else spec.layout.symbol_spacing / 2
            )
            rc["y"] = port.position.y - y_offset
        elif component_spec.placed_below_of is not None:
            ref_idx, pin_name = component_spec.placed_below_of
            ref_rc = realized_components[ref_idx]
            ref_sym = ref_rc["symbol"]
            port = _find_port(ref_sym, pin_name, ref_rc["spec"].pins)
            if port is None:
                msg = f"Port '{pin_name}' not found on symbol '{ref_rc['tag']}'"
                raise CircuitValidationError(msg)
            final_x = port.position.x + component_spec.x_offset
            y_offset = (
                component_spec.y_increment
                if component_spec.y_increment is not None
                else spec.layout.symbol_spacing / 2
            )
            rc["y"] = port.position.y + y_offset
        elif component_spec.placed_right_of is not None:
            ref_rc = realized_components[component_spec.placed_right_of]
            ref_x_offset = ref_rc["spec"].x_offset
            if ref_rc["spec"].placed_right_of is not None:
                # Chain: this is placed right of something also placed right
                # Walk back to get the absolute x offset
                ref_x_offset = _get_absolute_x_offset(
                    realized_components, component_spec.placed_right_of
                )
            final_x = x + ref_x_offset + component_spec.x_offset
        else:
            final_x = x + component_spec.x_offset

        sym = None
        if component_spec.kind == "terminal":
            lpos = component_spec.kwargs.get("label_pos") or "left"
            plpos = component_spec.kwargs.get("pin_label_pos")
            if component_spec.poles >= _MULTI_POLE_MIN:
                sym = _multi_pole_terminal(
                    tag,
                    pins=rc["pins"],
                    poles=component_spec.poles,
                    label_pos=lpos,
                    pin_label_pos=plpos,
                )
            else:
                sym = _terminal_single_pole(
                    tag, pins=rc["pins"], label_pos=lpos, pin_label_pos=plpos
                )

        elif component_spec.kind in ("symbol", "reference"):
            kwargs = component_spec.kwargs.copy()
            if rc["pins"]:
                # Distribute pins to the correct parameters based on
                # the symbol function's signature (pins=, contact_pins=, etc.)
                pin_kwargs = _distribute_pins(component_spec.func, rc["pins"], kwargs)
                kwargs.update(pin_kwargs)
            # Forward poles to factory if it accepts the parameter
            if (
                component_spec.poles > 1
                and "poles" not in kwargs
                and component_spec.func is not None
            ):
                import inspect

                sig = inspect.signature(component_spec.func)
                if "poles" in sig.parameters:
                    kwargs["poles"] = component_spec.poles
            sym = component_spec.func(tag, **kwargs)

        if sym:
            placed_sym = add_symbol(c, sym, final_x, rc["y"])
            rc["symbol"] = placed_sym  # Store placed symbol for manual connection phase


def _phase4_render_graphics(
    c: Circuit,
    realized_components: list[dict[str, Any]],
    spec: CircuitSpec,
) -> None:
    """Phase 4: render manual/matching/chain wires; per-conn labels applied inline."""
    from schematika.electrical.layout.wire_labels import (
        calculate_wire_label_position,
        create_wire_label_text,
    )
    from schematika.electrical.model.parts import standard_style
    from schematika.electrical.model.primitives import Line

    has_per_connection_labels = bool(spec.connection_wire_labels) or any(
        rc["spec"].wire_labels_above for rc in realized_components
    )

    # 1. Manual Connections Rendering
    style = standard_style()
    for conn_idx, (idx_a, p_a, idx_b, p_b, side_a, side_b) in enumerate(
        spec.manual_connections
    ):
        if idx_a >= len(realized_components) or idx_b >= len(realized_components):
            continue

        comp_a = realized_components[idx_a]
        comp_b = realized_components[idx_b]

        if "symbol" not in comp_a or "symbol" not in comp_b:
            continue

        sym_a = comp_a["symbol"]
        sym_b = comp_b["symbol"]

        pin_a = _resolve_pin(comp_a, p_a, is_input=(side_a == "top"))
        pin_b = _resolve_pin(comp_b, p_b, is_input=(side_b == "top"))

        port_a = _find_port(sym_a, pin_a, comp_a["spec"].pins)
        port_b = _find_port(sym_b, pin_b, comp_b["spec"].pins)

        if port_a and port_b:
            # Draw direct line
            line = Line(port_a.position, port_b.position, style)
            c.elements.append(line)

            # Apply per-connection wire label
            label = spec.connection_wire_labels.get(conn_idx)
            if label:
                is_vertical = abs(line.start.x - line.end.x) < _WIRE_VERTICAL_THRESHOLD
                if is_vertical:
                    pos = calculate_wire_label_position(line.start, line.end)
                    c.elements.append(create_wire_label_text(label, pos))

    # 2. Matching Connections Rendering (connect_matching)
    for idx_a, idx_b, pin_filter, _side_a, _side_b in spec.matching_connections:
        if idx_a >= len(realized_components) or idx_b >= len(realized_components):
            continue

        comp_a = realized_components[idx_a]
        comp_b = realized_components[idx_b]

        if "symbol" not in comp_a or "symbol" not in comp_b:
            continue

        sym_a = comp_a["symbol"]
        sym_b = comp_b["symbol"]

        # Find matching pin names
        pins_a = set(comp_a["pins"]) if comp_a["pins"] else set()
        pins_b = set(comp_b["pins"]) if comp_b["pins"] else set()
        common_pins = pins_a & pins_b

        if pin_filter is not None:
            common_pins = common_pins & set(pin_filter)

        # Draw horizontal wires for each matching pin
        for pin_name in common_pins:
            port_a = sym_a.ports.get(pin_name)
            port_b = sym_b.ports.get(pin_name)
            if port_a and port_b:
                line = Line(port_a.position, port_b.position, style)
                c.elements.append(line)

    # 3. Planned Chain Connections
    for pc in spec.planned_connections:
        if pc.kind != "chain":
            continue

        if pc.source_idx >= len(realized_components) or pc.target_idx >= len(
            realized_components
        ):
            continue

        src_rc = realized_components[pc.source_idx]
        tgt_rc = realized_components[pc.target_idx]

        if "symbol" not in src_rc or "symbol" not in tgt_rc:
            continue

        sym1 = src_rc["symbol"]
        sym2 = tgt_rc["symbol"]

        lines = draw_wire(sym1, sym2)
        c.elements.extend(lines)

        if has_per_connection_labels:
            tgt_spec = tgt_rc["spec"]
            if tgt_spec.wire_labels_above:
                for j, wire_line in enumerate(lines):
                    if j < len(tgt_spec.wire_labels_above):
                        wl = tgt_spec.wire_labels_above[j]
                        if wl:
                            pos = calculate_wire_label_position(
                                wire_line.start, wire_line.end
                            )
                            c.elements.append(create_wire_label_text(wl, pos))


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
    state, wire_connections = _phase2_register_connections(
        state, realized_components, spec
    )
    _phase3_instantiate_symbols(c, realized_components, spec, x)
    _phase4_render_graphics(c, realized_components, spec)

    return state, c.elements, instance_tags, wire_connections
