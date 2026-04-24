"""Pipe routing and rendering for P&ID diagrams.

Provides predefined pipe styles (``PipeStyle``), a Manhattan-routing
helper (``manhattan_route``), and rendering functions that convert
waypoint lists into ``Line`` / ``Polygon`` elements suitable for
adding to a ``PIDDiagram``.
"""

import math
from dataclasses import dataclass

from schematika.core.geometry import Element, Point, Style
from schematika.core.primitives import Line, Polygon, Text
from schematika.pid.errors import PIDRoutingError
from schematika.pid.constants import (
    PID_FLOW_ARROW_SIZE,
    PID_LABEL_PIPE_OFFSET,
    PID_LINE_WEIGHT,
    PID_PNEUMATIC_DASH,
    PID_SIGNAL_DASH,
    PID_SIGNAL_LINE_WEIGHT,
    PID_TEXT_SIZE_PIPE,
)


@dataclass(frozen=True)
class PipeStyle:
    """Visual style for a pipe or signal line.

    Attributes:
        stroke_width: Line width in mm.
        dash_pattern: SVG ``stroke-dasharray`` value, or ``None`` for solid.
        color: CSS stroke color string.
        show_flow_arrow: Whether to render a flow-direction arrow on the pipe.
    """

    stroke_width: float
    dash_pattern: str | None = None
    color: str = "black"
    show_flow_arrow: bool = False


# ---------------------------------------------------------------------------
# Predefined styles
# ---------------------------------------------------------------------------

PROCESS_PIPE = PipeStyle(stroke_width=PID_LINE_WEIGHT)
SIGNAL_LINE = PipeStyle(
    stroke_width=PID_SIGNAL_LINE_WEIGHT, dash_pattern=PID_SIGNAL_DASH
)
PNEUMATIC_LINE = PipeStyle(
    stroke_width=PID_SIGNAL_LINE_WEIGHT, dash_pattern=PID_PNEUMATIC_DASH
)


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


def manhattan_route(  # noqa: E501
    start: Point, end: Point, prefer: str = "horizontal"
) -> list[Point]:
    """Compute Manhattan (orthogonal) waypoints between two points.

    For a simple L-bend the result is ``[start, bend, end]``.  When start
    and end share an axis (same x or same y) the result is the straight
    segment ``[start, end]``.  When start equals end a single-element list
    ``[start]`` is returned.

    Args:
        start: Starting point.
        end: Ending point.
        prefer: ``"horizontal"`` routes horizontally first then vertically;
                ``"vertical"`` routes vertically first then horizontally.

    Returns:
        List of waypoints including start and end.
    """
    if start == end:
        return [start]

    same_x = abs(start.x - end.x) < 1e-9
    same_y = abs(start.y - end.y) < 1e-9

    if same_x or same_y:
        return [start, end]

    if prefer == "horizontal":
        bend = Point(end.x, start.y)
    else:
        bend = Point(start.x, end.y)

    return [start, bend, end]


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------


def _make_style(pipe_style: PipeStyle) -> Style:
    return Style(
        stroke=pipe_style.color,
        stroke_width=pipe_style.stroke_width,
        fill="none",
        stroke_dasharray=pipe_style.dash_pattern,
    )


def create_flow_arrow(
    point: Point, direction: str = "right", size: float = PID_FLOW_ARROW_SIZE
) -> Element:
    """Create a small filled triangular flow-direction arrow.

    The arrow is centred at *point* and points in the given cardinal direction.

    Args:
        point: Centre position of the arrow.
        direction: One of ``"right"``, ``"left"``, ``"up"``, ``"down"``.
        size: Half-length of the triangle base/height in mm.

    Returns:
        A filled ``Polygon`` element.
    """
    x, y = point.x, point.y
    half = size / 2.0

    arrow_style = Style(stroke="none", fill="black")

    direction_map: dict[str, list[Point]] = {
        "right": [
            Point(x + size, y),
            Point(x - half, y - half),
            Point(x - half, y + half),
        ],
        "left": [
            Point(x - size, y),
            Point(x + half, y - half),
            Point(x + half, y + half),
        ],
        "down": [
            Point(x, y + size),
            Point(x - half, y - half),
            Point(x + half, y - half),
        ],
        "up": [
            Point(x, y - size),
            Point(x - half, y + half),
            Point(x + half, y + half),
        ],
    }

    if direction not in direction_map:
        raise PIDRoutingError(
            f"direction must be one of 'right', 'left', 'up', 'down'; got {direction!r}"
        )

    return Polygon(points=direction_map[direction], style=arrow_style)


def _segment_direction(p1: Point, p2: Point) -> str:
    """Infer cardinal direction from p1 to p2."""
    dx = p2.x - p1.x
    dy = p2.y - p1.y
    if abs(dx) >= abs(dy):
        return "right" if dx >= 0 else "left"
    return "down" if dy >= 0 else "up"


def _longest_horizontal_segment(waypoints: list[Point]) -> tuple[int, float] | None:
    """Return (segment_index, length) of the longest horizontal segment."""
    best_idx: int | None = None
    best_len = 0.0
    for i in range(len(waypoints) - 1):
        p1, p2 = waypoints[i], waypoints[i + 1]
        if abs(p1.y - p2.y) < 1e-9:
            length = abs(p2.x - p1.x)
            if length > best_len:
                best_len = length
                best_idx = i
    if best_idx is None:
        return None
    return best_idx, best_len


def render_pipe(
    waypoints: list[Point],
    style: PipeStyle,
    label: str = "",
) -> list[Element]:
    """Convert waypoints into Line elements with appropriate styling.

    Also generates a flow arrow (small filled triangle) at the midpoint of
    the longest segment when ``style.show_flow_arrow`` is ``True``.

    If *label* is provided, a ``Text`` element is placed above the midpoint
    of the longest horizontal segment (or the first segment if none is
    horizontal).

    Args:
        waypoints: Ordered list of points defining the pipe path.
        style: Visual style to apply.
        label: Optional pipe tag/label string.

    Returns:
        List of ``Element`` objects (``Line``, optionally ``Polygon`` and
        ``Text``).
    """
    if len(waypoints) < 2:
        return []

    line_style = _make_style(style)
    elements: list[Element] = []

    for i in range(len(waypoints) - 1):
        elements.append(
            Line(start=waypoints[i], end=waypoints[i + 1], style=line_style)
        )

    # Flow arrow — place at midpoint of the longest segment.
    if style.show_flow_arrow and len(waypoints) >= 2:
        # Pick the longest segment by Euclidean length.
        best_i = 0
        best_len = 0.0
        for i in range(len(waypoints) - 1):
            p1, p2 = waypoints[i], waypoints[i + 1]
            seg_len = math.hypot(p2.x - p1.x, p2.y - p1.y)
            if seg_len > best_len:
                best_len = seg_len
                best_i = i

        p1, p2 = waypoints[best_i], waypoints[best_i + 1]
        mid = Point((p1.x + p2.x) / 2, (p1.y + p2.y) / 2)
        direction = _segment_direction(p1, p2)
        elements.append(create_flow_arrow(mid, direction))

    # Label — centre of longest horizontal segment, offset 2 mm above.
    if label:
        h_seg = _longest_horizontal_segment(waypoints)
        if h_seg is not None:
            idx, _ = h_seg
            p1, p2 = waypoints[idx], waypoints[idx + 1]
            lx = (p1.x + p2.x) / 2
            ly = p1.y - PID_LABEL_PIPE_OFFSET
        else:
            # Fall back to midpoint of the first segment.
            p1, p2 = waypoints[0], waypoints[1]
            lx = (p1.x + p2.x) / 2
            ly = (p1.y + p2.y) / 2 - PID_LABEL_PIPE_OFFSET

        label_style = Style(stroke="none", fill="black")
        elements.append(
            Text(
                content=label,
                position=Point(lx, ly),
                style=label_style,
                anchor="middle",
                font_size=PID_TEXT_SIZE_PIPE,
            )
        )

    return elements
