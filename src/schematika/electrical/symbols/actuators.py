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
    """Emergency Stop Head (Mushroom).

    Geometry (0 deg = Pointing Right):
    - Flat base on Y-axis (x=0).
    - Semi-circle bulging to + x.
    - Diameter: GRID_SIZE / 2 (Radius = GRID_SIZE / 4).

    Implemented as a Polygon to ensure compatibility with generic translation/rotation.
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
    """Turn Switch Actuator (Manual Rotary).

    Creates an S-shaped (step) symbol for a turn switch actuator.
    The vertical mid-section passes through (0,0) to connect with the linkage.

    Args:
        label: Component label (typically empty for actuator).
        rotation: Rotation in degrees (0 = default, 180 = for left-side assembly).

    Returns:
        Symbol: The turn switch actuator graphic.
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
