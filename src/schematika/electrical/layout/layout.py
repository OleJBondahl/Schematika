"""Layout helpers: vertical chains, horizontal repeats, port-matched wiring."""

from collections.abc import Callable
from typing import Any, Final

from schematika.electrical.model.constants import DEFAULT_WIRE_ALIGNMENT_TOLERANCE
from schematika.electrical.model.core import Element, Point, Port, Symbol, Vector
from schematika.electrical.model.parts import standard_style
from schematika.electrical.model.primitives import Line
from schematika.electrical.utils.transform import translate

# Tolerance for port direction vector comparison (floating-point equality).
_PORT_DIRECTION_TOLERANCE: Final = 1e-6


def get_connection_ports(symbol: Symbol, direction: Vector) -> list[Port]:
    """Ports facing *direction*; spatial duplicates are filtered."""
    matches = []
    seen_positions = set()

    for p in symbol.ports.values():
        dx = abs(p.direction.dx - direction.dx)
        dy = abs(p.direction.dy - direction.dy)
        if dx < _PORT_DIRECTION_TOLERANCE and dy < _PORT_DIRECTION_TOLERANCE:
            # Check for spatial duplicates
            # (e.g. aliased ports pointing to same location)
            pos_key = (round(p.position.x, 4), round(p.position.y, 4))

            if pos_key not in seen_positions:
                matches.append(p)
                seen_positions.add(pos_key)

    return matches


def draw_wire(sym1: Symbol, sym2: Symbol) -> list[Line]:
    """Draw wires between sym1's downward ports and sym2's upward X-aligned ports.

    Each downward port on *sym1* is paired with an upward port on *sym2* that
    shares the same x-coordinate (within the alignment tolerance). Returns one
    :class:`~schematika.electrical.model.primitives.Line` per matched pair.

    Args:
        sym1: Upper symbol providing downward-facing ports.
        sym2: Lower symbol providing upward-facing ports.

    Returns:
        List of wire lines; empty if no X-aligned port pairs exist.

    Examples:
        >>> from schematika.electrical import draw_wire
        >>> from schematika.electrical.symbols import breaker, fuse
        >>> sym1 = breaker(label="F1")
        >>> sym2 = fuse(label="F2")
        >>> wires = draw_wire(sym1, sym2)
        >>> isinstance(wires, list)
        True
    """
    down_ports = get_connection_ports(sym1, Vector(0, 1))
    up_ports = get_connection_ports(sym2, Vector(0, -1))

    return [
        Line(dp.position, up.position, style=standard_style())
        for dp in down_ports
        for up in up_ports
        if abs(dp.position.x - up.position.x) < DEFAULT_WIRE_ALIGNMENT_TOLERANCE
    ]


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
    """`wire_specs`: `{port_id: (color, size)}` or `[(color, size), ...]` (LtR)."""
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
    """Stacks symbols vertically and connects each adjacent pair via `draw_wire`."""
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
    start_state: Any,  # noqa: ANN401  # GenerationState; opaque to layout module
    start_x: float,
    start_y: float,
    spacing: float,
    count: int,
    generate_func: Callable[[Any, float, float], tuple[Any, list[Element]]],
) -> tuple[Any, list[Element]]:
    """Threads state through *count* copies of a circuit at increasing X."""
    current_state = start_state
    all_elements = []

    for i in range(count):
        x_pos = start_x + (i * spacing)
        # Pass current_state, receive new state
        current_state, elems = generate_func(current_state, x_pos, start_y)
        all_elements.extend(elems)

    return current_state, all_elements


def create_horizontal_layout(
    state: Any,  # noqa: ANN401  # GenerationState; opaque to layout module
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
    """Threads state through *count* instances; `tag_generators` overrides defaults."""
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
