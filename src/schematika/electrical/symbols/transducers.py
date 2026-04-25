"""Factory functions for IEC 60617 transducer symbols.

Provides symbol factories for current transformers (CT) and CT assemblies.
Imports constants and core types from ``electrical/model/``.
"""

from schematika.electrical.model.constants import CT_ASSEMBLY_PINS, GRID_SIZE
from schematika.electrical.model.core import Point, Port, Symbol
from schematika.electrical.model.parts import standard_style
from schematika.electrical.model.primitives import Circle, Element, Line
from schematika.electrical.utils.transform import translate

from .blocks import terminal_box


def ct() -> Symbol:
    """IEC 60617 current transducer (toroid circle on wire, no connection ports).

    Decorative overlay placed on a wire; connection is made via
    :func:`ct_assembly` which adds a terminal box with real ports.

    Ports:
        (none)

    Returns:
        Symbol with no ports.

    Examples:
        >>> from schematika.electrical.symbols import ct
        >>> sym = ct()
        >>> sym.ports
        {}
    """
    style = standard_style()

    # Circle
    radius = GRID_SIZE / 2
    circle = Circle(Point(0, 0), radius, style)

    # Line from left edge to left
    line_length = GRID_SIZE
    line_start = Point(-radius, 0)
    line_end = Point(-radius - line_length, 0)
    line = Line(line_start, line_end, style)

    elements: list[Element] = [circle, line]

    # No ports
    ports: dict[str, Port] = {}

    return Symbol(elements, ports, label="")


def ct_assembly(label: str = "", pins: tuple[str, ...] = CT_ASSEMBLY_PINS) -> Symbol:
    """IEC 60617 CT assembly: toroid circle + terminal box to the left.

    Combines :func:`ct` (decorative circle) with :func:`terminal_box` (real
    ports). The origin is at the CT circle center so the assembly overlays
    a wire at the correct position.

    Ports:
        1, 2: terminal box output pins (upward-pointing).

    Args:
        label: Label for the terminal box, e.g. ``"T1"``.
        pins: Pin IDs for the terminal box, defaults to ``("1", "2")``.

    Returns:
        Symbol with ports from the terminal box (CT itself has none).

    Examples:
        >>> from schematika.electrical.symbols import ct_assembly
        >>> sym = ct_assembly(label="T1")
        >>> sorted(sym.ports.keys())
        ['1', '2']
    """
    # 1. Transducer (Origin 0,0)
    ct_sym = ct()

    # 2. Terminal Box
    box_sym = terminal_box(label=label, pins=pins)

    # Calculate Box Dimensions to determine offset
    from schematika.electrical.model.constants import DEFAULT_POLE_SPACING

    span = (len(pins) - 1) * DEFAULT_POLE_SPACING
    box_right_edge_x_local = span + (GRID_SIZE / 2)

    shift_x = (
        -7.5 - box_right_edge_x_local
    )  # -7.5 because line extends 5mm from -2.5 circle edge
    shift_y = -GRID_SIZE / 2  # -2.5

    box_placed = translate(box_sym, shift_x, shift_y)

    # Combine
    combined_elements = ct_sym.elements + box_placed.elements
    combined_ports = box_placed.ports  # Transducer has none

    return Symbol(combined_elements, combined_ports, label=label)
