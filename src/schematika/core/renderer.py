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
def calculate_bounds(elements: list[Element]) -> tuple[float, float, float, float]:
    """Calculate the bounding box of a list of elements.

    Args:
        elements: List of elements.

    Returns:
        tuple[min_x, min_y, max_x, max_y]
    """
    min_x, min_y = float("inf"), float("inf")
    max_x, max_y = float("-inf"), float("-inf")

    def _expand(x: float, y: float) -> None:
        nonlocal min_x, min_y, max_x, max_y
        min_x = min(min_x, x)
        min_y = min(min_y, y)
        max_x = max(max_x, x)
        max_y = max(max_y, y)

    def process(elem: Element) -> None:
        if isinstance(elem, Line):
            _expand(elem.start.x, elem.start.y)
            _expand(elem.end.x, elem.end.y)
        elif isinstance(elem, Circle):
            _expand(elem.center.x - elem.radius, elem.center.y - elem.radius)
            _expand(elem.center.x + elem.radius, elem.center.y + elem.radius)
        elif isinstance(elem, Polygon):
            for p in elem.points:
                _expand(p.x, p.y)
        elif isinstance(elem, Text):
            # Text bounding box is approximate.
            _expand(elem.position.x, elem.position.y)
            _expand(elem.position.x + 10, elem.position.y + 5)
            _expand(elem.position.x - 10, elem.position.y - 5)
        elif isinstance(elem, (Group, Symbol)):
            for child in elem.elements:
                process(child)

    if not elements:
        return 0, 0, 100, 100

    for e in elements:
        process(e)

    if min_x == float("inf"):
        return 0, 0, 100, 100

    return min_x, min_y, max_x, max_y
