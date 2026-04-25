"""Factory functions for IEC 60617 protection device symbols.

Provides symbol factories for fuses and overload relays. Imports constants
and core types from ``electrical/model/``.
"""

from schematika.electrical.model.constants import (
    FUSE_1P_PINS,
    GRID_SIZE,
    GRID_SUBDIVISION,
    THERMAL_OVERLOAD_PINS,
)
from schematika.electrical.model.core import Element, Point, Port, Symbol, Vector
from schematika.electrical.model.parts import (
    box,
    create_pin_labels,
    multipole,
    standard_style,
    standard_text,
)
from schematika.electrical.model.primitives import Line


def _thermal_overload_single_pole(
    label: str = "", pins: tuple[str, ...] = THERMAL_OVERLOAD_PINS
) -> Symbol:
    """Single-pole thermal overload implementation."""
    # Grid subdiv
    hg = GRID_SUBDIVISION  # 2.5

    y_start = -1.5 * hg

    # Points
    p0 = Point(0, y_start)
    p1 = Point(0, y_start + hg)  # Down
    p2 = Point(-hg, y_start + hg)  # Left
    p3 = Point(-hg, y_start + 2 * hg)  # Down
    p4 = Point(0, y_start + 2 * hg)  # Right
    p5 = Point(0, y_start + 3 * hg)  # Down (End of pulse)

    top_port_y = -GRID_SIZE
    bot_port_y = GRID_SIZE

    style = standard_style()

    # Lead-in (Top)
    l_in = Line(Point(0, top_port_y), p0, style)

    # Pulse path
    s1 = Line(p0, p1, style)
    s2 = Line(p1, p2, style)
    s3 = Line(p2, p3, style)
    s4 = Line(p3, p4, style)
    s5 = Line(p4, p5, style)

    # Lead-out (Avg)  # noqa: ERA001
    l_out = Line(p5, Point(0, bot_port_y), style)

    elements: list[Element] = [l_in, s1, s2, s3, s4, s5, l_out]

    if label:
        elements.append(standard_text(label, Point(0, 0)))

    ports = {
        "1": Port("1", Point(0, top_port_y), Vector(0, -1)),
        "2": Port("2", Point(0, bot_port_y), Vector(0, 1)),
    }

    if pins:
        elements.extend(create_pin_labels(ports, pins))

    return Symbol(elements, ports, label=label)


def thermal_overload(
    label: str = "",
    poles: int = 1,
    pins: tuple[str, ...] | None = None,
) -> Symbol:
    """IEC 60617 Thermal Overload Protection.

    Args:
        label: Component tag.
        poles: Number of poles (1, 2, 3, ...).
        pins: Pin designations. Defaults to standard IEC pins for the given pole count.

    Returns:
        Symbol: The thermal overload symbol.
    """
    if pins is None:
        pins = tuple(str(i) for i in range(1, poles * 2 + 1))

    if poles == 1:
        return _thermal_overload_single_pole(label=label, pins=pins)

    factory = multipole(_thermal_overload_single_pole, poles)
    return factory(label=label, pins=pins)


def fuse(label: str = "", pins: tuple[str, ...] = FUSE_1P_PINS) -> Symbol:
    """IEC 60617 Fuse."""
    w = 2 * GRID_SIZE
    h = 5 * GRID_SIZE

    body = box(Point(0, 0), w, h)
    style = standard_style()

    # Internal continuity line
    line = Line(Point(0, -h / 2), Point(0, h / 2), style)

    elements: list[Element] = [body, line]
    if label:
        elements.append(standard_text(label, Point(0, 0)))

    ports = {
        "1": Port("1", Point(0, -h / 2), Vector(0, -1)),
        "2": Port("2", Point(0, h / 2), Vector(0, 1)),
    }

    if pins:
        elements.extend(create_pin_labels(ports, pins))

    return Symbol(elements, ports, label)
