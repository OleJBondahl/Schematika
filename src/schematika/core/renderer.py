"""Pure geometry helpers for SVG rendering.

The actual XML-tree builders and file writers (``to_xml_element``,
``save_svg``, ``render_to_svg``, ``_render_element``) live in
``schematika.rendering.svg`` — they touch ``xml.etree`` state and
perform disk I/O, so they stay out of ``core/``.
"""

import deal

from schematika.core.geometry import Style
from schematika.core.primitives import (
    Circle,
    Element,
    Group,
    Line,
    Polygon,
    Text,
)
from schematika.core.symbol import Symbol


@deal.pure
def _style_to_str(style: Style) -> str:
    """Evaluate style object to SVG style string.

    Args:
        style (Style): The style object to convert.

    Returns:
        str: The CSS style string.
    """
    items = []
    if style.stroke:
        items.append(f"stroke:{style.stroke}")
    if style.stroke_width:
        items.append(f"stroke-width:{style.stroke_width}")
    if style.fill:
        items.append(f"fill:{style.fill}")
    if style.stroke_dasharray:
        items.append(f"stroke-dasharray:{style.stroke_dasharray}")
    if style.font_family:
        items.append(f"font-family:{style.font_family}")
    return ";".join(items)


@deal.pure
def _bounds_for_element(
    elem: Element,
) -> list[tuple[float, float]]:
    """Recurse into Group/Symbol children; return empty list for unknown types."""
    match elem:
        case Line():
            return [(elem.start.x, elem.start.y), (elem.end.x, elem.end.y)]
        case Circle():
            cx, cy, r = elem.center.x, elem.center.y, elem.radius
            return [(cx - r, cy - r), (cx + r, cy + r)]
        case Polygon():
            return [(p.x, p.y) for p in elem.points]
        case Text():
            # Text bounding box is approximate.
            px, py = elem.position.x, elem.position.y
            return [(px, py), (px + 10, py + 5), (px - 10, py - 5)]
        case Group() | Symbol():
            return [pt for child in elem.elements for pt in _bounds_for_element(child)]
        case _:
            return []


@deal.pure
def calculate_bounds(elements: list[Element]) -> tuple[float, float, float, float]:
    """Calculate the bounding box of a list of elements.

    Args:
        elements: List of elements.

    Returns:
        tuple[min_x, min_y, max_x, max_y]
    """
    if not elements:
        return 0, 0, 100, 100

    points = [pt for e in elements for pt in _bounds_for_element(e)]

    if not points:
        return 0, 0, 100, 100

    min_x = min(p[0] for p in points)
    min_y = min(p[1] for p in points)
    max_x = max(p[0] for p in points)
    max_y = max(p[1] for p in points)
    return min_x, min_y, max_x, max_y
