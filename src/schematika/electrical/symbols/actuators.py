import math

from schematika.electrical.model.constants import GRID_SIZE
from schematika.electrical.model.core import Point, Symbol
from schematika.electrical.model.parts import standard_style
from schematika.electrical.model.primitives import Element, Line, Polygon
from schematika.electrical.utils.transform import rotate


def emergency_stop_button_symbol(label: str = "", rotation: float = 0.0) -> Symbol:
    """
    Emergency Stop Head (Mushroom).

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
    # Angles from -90 (Top) to 90 (Bottom) drawing the arc on the Right (+x)
    points = []

    # 1. Top of base
    points.append(Point(0, -r))

    # 2. Arc segments
    steps = 10
    for i in range(steps + 1):
        # angle goes from -pi/2 to pi/2
        angle = -math.pi / 2 + (math.pi * i / steps)
        px = r * math.cos(angle)
        py = r * math.sin(angle)
        points.append(Point(px, py))

    # 3. Bottom of base is effectively included in loop (at pi/2)
    # Polygon auto-closes to start (0, -r)

    head = Polygon(points=points, style=style)

    sym = Symbol([head], {}, label=label)

    # Apply rotation
    if rotation != 0:
        sym = rotate(sym, rotation)

    return sym


def turn_switch_symbol(label: str = "", rotation: float = 0.0) -> Symbol:
    """
    Turn Switch Actuator (Manual Rotary).

    Creates an S-shaped (step) symbol for a turn switch actuator.
    The vertical mid-section passes through (0,0) to connect with the linkage.

    Geometry at 0° (before rotation):
    (-1.25, -1.25) ──── (0, -1.25) ← TOP: horizontal
                        |
                        |              ← MID: vertical passes through (0,0)
                        |
                (0, 1.25) ──── (1.25, 1.25) ← BOT: horizontal

    - TOP: horizontal from (-1.25, -1.25) to (0, -1.25)
    - MID: vertical from (0, -1.25) to (0, 1.25) [at x=0]
    - BOT: horizontal from (0, 1.25) to (1.25, 1.25)

    When rotated 180 for assembly: flips to create proper
    visual connection to the linkage.

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
    # Connects TOP at (0, -1.25) to BOT at (0, 1.25)
    # Passes through (0,0) where linkage connects
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
