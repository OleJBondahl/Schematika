"""
Cable routing and rendering for block diagrams.

Provides a cable-style conversion helper, and a rendering function that
converts waypoint lists into ``Line`` / ``Text`` elements suitable for
adding to a ``BlockDiagram``.

Reuses :func:`~schematika.pid.connections.manhattan_route` for orthogonal
routing — no duplication.
"""

from schematika.block.constants import BLOCK_TEXT_SIZE_CABLE
from schematika.block.model import CableStyle
from schematika.core.geometry import Element, Point, Style
from schematika.core.primitives import Line, Text
from schematika.pid.connections import manhattan_route

__all__ = [
    "manhattan_route",
    "render_cable",
]


# ---------------------------------------------------------------------------
# Style conversion
# ---------------------------------------------------------------------------


def _make_style(cable_style: CableStyle) -> Style:
    """Convert a ``CableStyle`` to a core ``Style``."""
    return Style(
        stroke=cable_style.color,
        stroke_width=cable_style.stroke_width,
        fill="none",
        stroke_dasharray=cable_style.dash_pattern,
    )


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------


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


def render_cable(
    waypoints: list[Point],
    style: CableStyle,
    label: str = "",
) -> list[Element]:
    """Convert waypoints into Line elements with cable styling.

    If *label* is provided, a ``Text`` element is placed above the midpoint
    of the longest horizontal segment (or the first segment if none is
    horizontal).

    Args:
        waypoints: Ordered list of points defining the cable path.
        style: Visual style to apply.
        label: Optional cable tag/label string.

    Returns:
        List of ``Element`` objects (``Line``, optionally ``Text``).
    """
    if len(waypoints) < 2:
        return []

    line_style = _make_style(style)
    elements: list[Element] = []

    for i in range(len(waypoints) - 1):
        elements.append(
            Line(start=waypoints[i], end=waypoints[i + 1], style=line_style)
        )

    # Label — centre of longest horizontal segment, offset above.
    if label:
        label_offset = BLOCK_TEXT_SIZE_CABLE  # offset above cable centerline
        h_seg = _longest_horizontal_segment(waypoints)
        if h_seg is not None:
            idx, _ = h_seg
            p1, p2 = waypoints[idx], waypoints[idx + 1]
            lx = (p1.x + p2.x) / 2
            ly = p1.y - label_offset
        else:
            # Fall back to midpoint of the first segment.
            p1, p2 = waypoints[0], waypoints[1]
            lx = (p1.x + p2.x) / 2
            ly = (p1.y + p2.y) / 2 - label_offset

        label_style = Style(stroke="none", fill="black")
        elements.append(
            Text(
                content=label,
                position=Point(lx, ly),
                style=label_style,
                anchor="middle",
                font_size=BLOCK_TEXT_SIZE_CABLE,
            )
        )

    return elements
