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


def _breaker_single_pole(label: str = "", pins: tuple[str, ...] = CB_1P_PINS) -> Symbol:
    """Single-pole circuit breaker implementation."""
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


def breaker(
    label: str = "",
    poles: int = 1,
    pins: tuple[str, ...] | None = None,
) -> Symbol:
    """IEC 60617 Circuit Breaker.

    Args:
        label: Component label (e.g. "F1").
        poles: Number of poles (1, 2, 3, ...).
        pins: Pin designations. Defaults to standard IEC pins for the given pole count.

    Returns:
        Symbol: The circuit breaker symbol.
    """
    if pins is None:
        pins = tuple(str(i) for i in range(1, poles * 2 + 1))

    if poles == 1:
        return _breaker_single_pole(label=label, pins=pins)

    factory = multipole(_breaker_single_pole, poles)
    return factory(label=label, pins=pins)
