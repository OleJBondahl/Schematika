from schematika.electrical.model.constants import CT_ASSEMBLY_PINS, GRID_SIZE
from schematika.electrical.model.core import Point, Port, Symbol
from schematika.electrical.model.parts import standard_style
from schematika.electrical.model.primitives import Circle, Element, Line
from schematika.electrical.utils.transform import translate

from .blocks import terminal_box


def ct() -> Symbol:
    """Current Transducer Symbol.

    Visuals:
        - A circle centered on the wire (assumed origin 0,0).
        - A line extending to the left from the left edge of the circle.
        - No pin numbers.
        - No connections (ports).

    Returns:
        Symbol: The symbol.
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
    """Current Transducer Assembly.

    Combines:
    - A Current Transducer Symbol (Circle on wire).
    - A Rectangular Terminal Box (to the left).

    Args:
        label: Label for the box (or assembly).
        pins: Pin numbers for the terminal box.

    Returns:
        Symbol: The combined symbol. Origin at the Transducer center.
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
