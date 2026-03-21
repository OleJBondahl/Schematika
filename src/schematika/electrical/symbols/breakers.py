from schematika.electrical.model.constants import (
    CB_1P_PINS,
    GRID_SIZE,
    GRID_SUBDIVISION,
)
from schematika.electrical.model.core import Element, Point, Port, Symbol, Vector
from schematika.electrical.model.parts import (
    create_pin_labels,
    multipole,
    standard_style,
    standard_text,
)
from schematika.electrical.model.primitives import Line


def circuit_breaker_symbol(
    label: str = "", pins: tuple[str, ...] = CB_1P_PINS
) -> Symbol:
    """IEC 60617 Circuit Breaker (Single Pole).

    A circuit breaker is represented as a normally open contact with a cross (X)
    at the interruption point, indicating it can break current under load.

    Symbol:
        |
       /X
       |

    Args:
        label (str): Component label (e.g., "F1").
        pins (tuple): Pin designations (default: ("1", "2")).

    Returns:
        Symbol: Single pole circuit breaker symbol.
    """

    # Based on normally_open contact geometry
    h_half = GRID_SIZE  # 5.0
    top_y = -GRID_SIZE / 2  # -2.5
    bot_y = GRID_SIZE / 2  # 2.5

    style = standard_style()

    # Vertical lines (terminals)
    l1 = Line(Point(0, -h_half), Point(0, top_y), style)
    l2 = Line(Point(0, bot_y), Point(0, h_half), style)

    # Blade (same as NO contact)
    blade_start = Point(0, bot_y)
    blade_end = Point(-GRID_SIZE / 2, top_y)
    blade = Line(blade_start, blade_end, style)

    # Cross (X) at the interruption point
    # Place the cross at the bottom tip of the top pin (where it would arc)
    cross_size = GRID_SUBDIVISION  # 2.5mm cross
    cross_offset_y = top_y  # At the bottom of the top pin (-2.5)
    cross_offset_x = 0  # Centered on the pin

    # X is two diagonal lines crossing
    cross_line_1 = Line(
        Point(cross_offset_x - cross_size / 2, cross_offset_y - cross_size / 2),
        Point(cross_offset_x + cross_size / 2, cross_offset_y + cross_size / 2),
        style,
    )
    cross_line_2 = Line(
        Point(cross_offset_x - cross_size / 2, cross_offset_y + cross_size / 2),
        Point(cross_offset_x + cross_size / 2, cross_offset_y - cross_size / 2),
        style,
    )

    elements: list[Element] = [l1, l2, blade, cross_line_1, cross_line_2]

    if label:
        elements.append(standard_text(label, Point(0, 0)))

    ports = {
        "1": Port("1", Point(0, -h_half), Vector(0, -1)),
        "2": Port("2", Point(0, h_half), Vector(0, 1)),
    }

    if pins:
        elements.extend(create_pin_labels(ports, pins))

    return Symbol(elements, ports, label=label)


three_pole_circuit_breaker_symbol = multipole(circuit_breaker_symbol, poles=3)
two_pole_circuit_breaker_symbol = multipole(circuit_breaker_symbol, poles=2)
