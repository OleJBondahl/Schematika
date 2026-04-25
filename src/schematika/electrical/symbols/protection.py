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
    """IEC 60617 thermal overload relay (bimetal zigzag per pole).

    Ports:
        1, 2: input/output for 1-pole.
        1-6: sequential input/output pairs for 3-pole (``1``/``2`` = T1, etc.).

    Args:
        label: Component tag, e.g. ``"F3"``.
        poles: Number of poles (1, 2, 3, ...).
        pins: Custom pin designations; defaults to sequential pairs per pole.

    Returns:
        Symbol with one port-pair per pole.

    Examples:
        >>> from schematika.electrical.symbols import thermal_overload
        >>> sym = thermal_overload()
        >>> sorted(sym.ports.keys())
        ['1', '2']
        >>> sym3 = thermal_overload(poles=3)
        >>> sorted(sym3.ports.keys())
        ['1', '2', '3', '4', '5', '6']
    """
    if pins is None:
        pins = tuple(str(i) for i in range(1, poles * 2 + 1))

    if poles == 1:
        return _thermal_overload_single_pole(label=label, pins=pins)

    factory = multipole(_thermal_overload_single_pole, poles)
    return factory(label=label, pins=pins)


def fuse(label: str = "", pins: tuple[str, ...] = FUSE_1P_PINS) -> Symbol:
    """IEC 60617 cartridge fuse (rectangle with internal continuity line).

    Ports:
        1: top terminal (input).
        2: bottom terminal (output).

    Args:
        label: Component tag, e.g. ``"F1"``.
        pins: Pin IDs, defaults to ``("1", "2")``.

    Returns:
        Symbol with ``1``/``2`` ports.

    Examples:
        >>> from schematika.electrical.symbols import fuse
        >>> sym = fuse(label="F1")
        >>> sorted(sym.ports.keys())
        ['1', '2']
    """
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
