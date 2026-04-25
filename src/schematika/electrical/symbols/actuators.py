"""Factory functions for IEC 60617 actuator symbols.

Provides symbol factories for solenoid valves and similar actuator devices.
Imports constants and core types from ``electrical/model/``.
"""

import math

from schematika.electrical.model.constants import GRID_SIZE
from schematika.electrical.model.core import Point, Symbol
from schematika.electrical.model.parts import standard_style
from schematika.electrical.model.primitives import Element, Line, Polygon
from schematika.electrical.utils.transform import rotate


def estop_button(label: str = "", rotation: float = 0.0) -> Symbol:
    """IEC 60617 emergency-stop mushroom-head actuator (graphic only, no ports).

    Semi-circle pointing right at ``rotation=0``. Used as part of
    :func:`~schematika.electrical.symbols.estop`; rarely placed standalone.

    Ports:
        (none — decorative actuator head only)

    Args:
        label: Unused; accepted for API consistency.
        rotation: Rotation in degrees (0 = pointing right, 180 = pointing left).

    Returns:
        Symbol with no ports.

    Examples:
        >>> from schematika.electrical.symbols import estop_button
        >>> sym = estop_button()
        >>> sym.ports
        {}
    """
    style = standard_style()

    # Dimensions
    r = GRID_SIZE / 4  # Radius (2.5mm / 2 = 1.25mm)

    # Generate points for semi-circle
    points = []

    # 1. Top of base
    points.append(Point(0, -r))

    # 2. Arc segments
    steps = 10
    for i in range(steps + 1):
        angle = -math.pi / 2 + (math.pi * i / steps)
        px = r * math.cos(angle)
        py = r * math.sin(angle)
        points.append(Point(px, py))

    head = Polygon(points=points, style=style)

    sym = Symbol([head], {}, label=label)

    # Apply rotation
    if rotation != 0:
        sym = rotate(sym, rotation)

    return sym


def turn_actuator(label: str = "", rotation: float = 0.0) -> Symbol:
    """IEC 60617 manual rotary actuator (S-step graphic, no ports).

    Used as part of :func:`~schematika.electrical.symbols.turn_switch`;
    rarely placed standalone.

    Ports:
        (none — decorative actuator head only)

    Args:
        label: Unused; accepted for API consistency.
        rotation: Rotation in degrees (0 = default, 180 = for left-side assembly).

    Returns:
        Symbol with no ports.

    Examples:
        >>> from schematika.electrical.symbols import turn_actuator
        >>> sym = turn_actuator()
        >>> sym.ports
        {}
    """
    style = standard_style()
    quarter_grid = GRID_SIZE / 4  # 1.25mm

    # TOP horizontal: left of center
    top_line = Line(
        Point(-quarter_grid, -quarter_grid),  # (-1.25, -1.25)
        Point(0, -quarter_grid),  # (0, -1.25)
        style,
    )

    # MID vertical: at center x=0
    mid_line = Line(
        Point(0, -quarter_grid),  # Top (0, -1.25)
        Point(0, quarter_grid),  # Bottom (0, 1.25)
        style,
    )

    # BOT horizontal: right of center
    bot_line = Line(
        Point(0, quarter_grid),  # (0, 1.25)
        Point(quarter_grid, quarter_grid),  # (1.25, 1.25)
        style,
    )

    elements: list[Element] = [top_line, mid_line, bot_line]
    sym = Symbol(elements, {}, label=label)

    if rotation != 0:
        sym = rotate(sym, rotation)

    return sym
