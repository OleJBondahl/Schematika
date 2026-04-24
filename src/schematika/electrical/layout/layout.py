"""Layout and automatic connection functions for electrical symbols.

This module provides high-level layout functions for arranging and connecting
electrical symbols automatically. Key features include:
- Port matching based on direction vectors
- Automatic wire routing between aligned components
- Labeled wire connections with specifications (color, size)
- Vertical chain layout with automatic connections
"""

from collections.abc import Callable
from typing import Any

from schematika.electrical.model.constants import DEFAULT_WIRE_ALIGNMENT_TOLERANCE
from schematika.electrical.model.core import Element, Point, Port, Symbol, Vector
from schematika.electrical.model.parts import standard_style
from schematika.electrical.model.primitives import Line
from schematika.electrical.utils.transform import translate


def get_connection_ports(symbol: Symbol, direction: Vector) -> list[Port]:
    """Find all ports in the symbol that match the given direction.

    Args:
        symbol (Symbol): The symbol to check.
        direction (Vector): The direction vector to match.

    Returns:
        list[Port]: A list of matching ports.
    """
    matches = []
    seen_positions = set()

    for p in symbol.ports.values():
        dx = abs(p.direction.dx - direction.dx)
        dy = abs(p.direction.dy - direction.dy)
        if dx < 1e-6 and dy < 1e-6:
            # Check for spatial duplicates
            # (e.g. aliased ports pointing to same location)
            pos_key = (round(p.position.x, 4), round(p.position.y, 4))

            if pos_key not in seen_positions:
                matches.append(p)
                seen_positions.add(pos_key)

    return matches


def draw_wire(sym1: Symbol, sym2: Symbol) -> list[Line]:
    """Automatically connects two symbols with Lines.

    Finds all downward facing ports in sym1 and upward facing ports in sym2.
    Connects pairs that are horizontally aligned.

    Args:
        sym1 (Symbol): The upper symbol (source).
        sym2 (Symbol): The lower symbol (target).

    Returns:
        list[Line]: A list of connection lines.
    """
    lines = []

    down_ports = get_connection_ports(sym1, Vector(0, 1))
    up_ports = get_connection_ports(sym2, Vector(0, -1))

    for dp in down_ports:
        for up in up_ports:
            # Check vertical alignment (same X)
            if abs(dp.position.x - up.position.x) < DEFAULT_WIRE_ALIGNMENT_TOLERANCE:
                lines.append(Line(dp.position, up.position, style=standard_style()))

    return lines


def _find_matching_ports(
    down_ports: list[Port], up_ports: list[Port]
) -> list[tuple[Port, Port]]:
    """Pair up downward ports with upward ports based on X position."""
    pairs = []
    # Sort downward ports by X position for consistent ordering
    sorted_down = sorted(down_ports, key=lambda p: p.position.x)

    for dp in sorted_down:
        # Find matching upward port
        for up in up_ports:
            if abs(dp.position.x - up.position.x) < DEFAULT_WIRE_ALIGNMENT_TOLERANCE:
                pairs.append((dp, up))
                break
    return pairs


def _get_wire_label_spec(
    dp: Port,
    match_index: int,
    wire_specs: dict[str, tuple] | list[tuple] | None,
) -> tuple[str, str]:
    """Determine the label (color, size) for a wire."""
    if not wire_specs:
        return ("", "")

    spec = ("", "")
    if isinstance(wire_specs, list):
        if match_index < len(wire_specs):
            spec = wire_specs[match_index]
    elif isinstance(wire_specs, dict):
        spec = wire_specs.get(dp.id, ("", ""))

    return spec if isinstance(spec, tuple) else ("", "")


def draw_wire_labeled(
    sym1: Symbol,
    sym2: Symbol,
    wire_specs: dict[str, tuple] | list[tuple] | None = None,
) -> list[Element]:
    """Automatically connects two symbols with labeled wires.

    High-level function that creates connections between aligned ports
    and adds wire specification labels (color, size) to each wire.

    Finds all downward facing ports in sym1 and upward facing ports in sym2.
    Connects pairs that are horizontally aligned and adds labels based on
    wire specifications.

    Args:
        sym1 (Symbol): The upper symbol (source).
        sym2 (Symbol): The lower symbol (target).
        wire_specs: Specification for wire labels.
            - If dict[str, tuple]: Maps Port ID to (color, size).
            - If list[tuple]: Maps (color, size) to ports by X-position (Left to Right).
            If None or not found, wire is created without label.

    Returns:
        list[Element]: List of connection lines and label texts.
    """
    from .wire_labels import create_labeled_wire

    elements = []
    wire_specs = wire_specs or {}

    # Get ports
    down_ports = get_connection_ports(sym1, Vector(0, 1))
    up_ports = get_connection_ports(sym2, Vector(0, -1))

    # Match ports
    # Note: Matching logic implies we iterate down_ports
    # in sorted order and find 'up' match
    port_pairs = _find_matching_ports(down_ports, up_ports)

    for i, (dp, matched_up) in enumerate(port_pairs):
        # Determine label spec
        color, size = _get_wire_label_spec(dp, i, wire_specs)

        # Create labeled wire
        wire_elements = create_labeled_wire(
            dp.position, matched_up.position, color, size
        )
        elements.extend(wire_elements)

    return elements


def layout_vertical_chain(
    symbols: list[Symbol], start: Point, spacing: float
) -> list[Element]:
    """Arranges a list of symbols in a vertical column and connects them.

    Args:
        symbols (list[Symbol]): List of Symbol templates (usually centered at 0,0).
        start (Point): Starting Point (center of the first symbol).
        spacing (float): Vertical distance between centers.

    Returns:
        list[Element]: List of Elements (Placed Symbols and Connecting Lines).
    """
    elements = []
    placed_symbols = []

    current_x = start.x
    current_y = start.y

    for sym in symbols:
        placed = translate(sym, current_x, current_y)

        placed_symbols.append(placed)
        elements.append(placed)

        current_y += spacing

    # Connect them
    for i in range(len(placed_symbols) - 1):
        top = placed_symbols[i]
        bot = placed_symbols[i + 1]

        lines = draw_wire(top, bot)
        elements.extend(lines)

    return elements


# --- Horizontal Flow Helpers ---


def layout_horizontal(
    start_state: Any,
    start_x: float,
    start_y: float,
    spacing: float,
    count: int,
    generate_func: Callable[[Any, float, float], tuple[Any, list[Element]]],
) -> tuple[Any, list[Element]]:
    """Layout multiple copies of a circuit horizontally, propagating state.

    Args:
        start_state: Initial autonumbering state.
        start_x: X position of the first circuit.
        start_y: Y position for all circuits.
        spacing: Horizontal distance between circuits.
        count: Number of copies to create.
        generate_func: Function that takes (state, x, y) and
                       returns (new_state, elements).
                       Expected signature: f(state: dict,
                       x: float, y: float) ->
                       (dict, list[Element])

    Returns:
        tuple[dict[str, Any], list[Element]]: Final state and list of all elements.
    """
    current_state = start_state
    all_elements = []

    for i in range(count):
        x_pos = start_x + (i * spacing)
        # Pass current_state, receive new state
        current_state, elems = generate_func(current_state, x_pos, start_y)
        all_elements.extend(elems)

    return current_state, all_elements


def create_horizontal_layout(
    state: Any,
    start_x: float,
    start_y: float,
    count: int,
    spacing: float,
    generator_func_single: Callable[
        [Any, float, float, dict[str, Any], dict[str, Any], int],
        tuple[Any, Any],
    ],
    default_tag_generators: dict[str, Callable],
    tag_generators: dict[str, Callable] | None = None,
    terminal_maps: dict[str, Any] | None = None,
) -> tuple[Any, list[Any]]:
    """Generic function to create multiple circuit instances arranged horizontally.

    Iterates ``count`` times, calling ``generator_func_single`` at each step
    with an incrementing X offset.  Autonumbering state is threaded through
    every call so that tag counters (e.g. Q1, Q2, ...) stay consistent
    across instances.  The instance index is forwarded to the generator so
    it can derive dynamic pin assignments or other per-instance behaviour.

    Args:
        state: Initial autonumbering state dict.  Threaded through each
            generator call and returned with the final counter values.
        start_x: X coordinate for the first circuit instance.
        start_y: Y coordinate shared by all instances (constant row).
        count: Number of circuit copies to create.
        spacing: Horizontal distance (mm) between successive instances.
        generator_func_single: Factory called once per instance.  Expected
            signature::

                f(state, x, y, tag_generators, terminal_maps, index)
                -> (new_state, elements)

            Where *tag_generators* and *terminal_maps* are the merged
            dictionaries described below, and *index* is the zero-based
            instance number.
        default_tag_generators: Base mapping of component prefix to a
            callable that produces the next tag from state
            (e.g. ``{"Q": next_q_tag}``).  Copied before merging so the
            original dict is never mutated.
        tag_generators: Optional overrides merged on top of
            *default_tag_generators*.  Use this to substitute fixed or
            custom tag sequences for specific prefixes.
        terminal_maps: Optional terminal-mapping dict forwarded verbatim
            to the generator.  Defaults to an empty dict when ``None``.

    Returns:
        A tuple of ``(final_state, all_elements)`` where *final_state*
        carries the updated counters and *all_elements* is a flat list of
        every element produced across all instances.
    """
    tm = terminal_maps or {}
    gens = default_tag_generators.copy()
    if tag_generators:
        gens.update(tag_generators)

    current_state = state
    all_elements = []

    for i in range(count):
        x_pos = start_x + (i * spacing)
        # Pass instance index (i) to generator function
        current_state, elems = generator_func_single(
            current_state, x_pos, start_y, gens, tm, i
        )
        all_elements.extend(elems)

    return current_state, all_elements
