"""SVG rendering shell: XML tree construction and file I/O.

These functions are **not pure** — they mutate `xml.etree.ElementTree`
state and/or write to disk. They live outside `core/` on purpose so the
purity gate (and the core-is-I/O-free invariant) stay honest.

Pure geometry helpers (`calculate_bounds`, `_style_to_str`) still live
in `schematika.core.renderer`.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from schematika.core.constants import (
    COLOR_WHITE,
    DEFAULT_DOC_HEIGHT,
    DEFAULT_DOC_WIDTH,
)
from schematika.core.primitives import (
    Circle,
    Element,
    Group,
    Line,
    Path,
    Polygon,
    Text,
)
from schematika.core.renderer import _style_to_str, calculate_bounds
from schematika.core.symbol import Symbol


def _render_element(elem: Element, parent: ET.Element) -> None:
    """Recursively render elements to the XML tree.

    Args:
        elem (Element): The element to render.
        parent (ET.Element): The parent XML element to append to.
    """
    if isinstance(elem, Line):
        e = ET.SubElement(parent, "line")
        e.set("x1", str(elem.start.x))
        e.set("y1", str(elem.start.y))
        e.set("x2", str(elem.end.x))
        e.set("y2", str(elem.end.y))
        e.set("style", _style_to_str(elem.style))

    elif isinstance(elem, Circle):
        e = ET.SubElement(parent, "circle")
        e.set("cx", str(elem.center.x))
        e.set("cy", str(elem.center.y))
        e.set("r", str(elem.radius))
        e.set("style", _style_to_str(elem.style))

    elif isinstance(elem, Text):
        e = ET.SubElement(parent, "text")
        e.set("x", str(elem.position.x))
        e.set("y", str(elem.position.y))
        e.set("text-anchor", elem.anchor)
        e.set("dominant-baseline", elem.dominant_baseline)
        e.set("font-size", str(elem.font_size))
        if elem.rotation != 0:
            e.set(
                "transform",
                f"rotate({elem.rotation}, {elem.position.x}, {elem.position.y})",
            )
        e.text = elem.content
        e.set("style", _style_to_str(elem.style))  # Fill usually needed for text

    elif isinstance(elem, Path):
        e = ET.SubElement(parent, "path")
        e.set("d", elem.d)
        e.set("style", _style_to_str(elem.style))

    elif isinstance(elem, Group):
        g = ET.SubElement(parent, "g")
        if elem.style:
            g.set("style", _style_to_str(elem.style))
        for child in elem.elements:
            _render_element(child, g)

    elif isinstance(elem, Polygon):
        e = ET.SubElement(parent, "polygon")
        points_str = " ".join([f"{p.x},{p.y}" for p in elem.points])
        e.set("points", points_str)
        e.set("style", _style_to_str(elem.style))

    elif isinstance(elem, Symbol):
        # Symbol is effectively a group
        g = ET.SubElement(parent, "g")
        g.set("class", "symbol")
        for child in elem.elements:
            _render_element(child, g)


def to_xml_element(
    elements: list[Element],
    width: int | str = DEFAULT_DOC_WIDTH,
    height: int | str = DEFAULT_DOC_HEIGHT,
) -> ET.Element:
    """Convert a list of Elements into an SVG header/root ElementTree Element.

    Args:
        elements (list[Element]): List of elements to render.
        width (int | str): document width. Pass "auto" for autosize.
        height (int | str): document height. Pass "auto" for autosize.

    Returns:
        ET.Element: The root SVG element.
    """
    root = ET.Element("svg")
    root.set("xmlns", "http://www.w3.org/2000/svg")

    # Calculate bounds if auto
    min_x, min_y, max_x, max_y = 0, 0, 0, 0
    if width == "auto" or height == "auto":
        min_x, min_y, max_x, max_y = calculate_bounds(elements)
        # Add padding
        padding = 20
        min_x -= padding
        min_y -= padding
        max_x += padding
        max_y += padding

        content_w = max_x - min_x
        content_h = max_y - min_y

    # Determine Width/Height strings and ViewBox

    # helper
    def _parse_dim(val: int | str, default: float) -> float | None:
        if val == "auto":
            return None
        if isinstance(val, (int, float)):
            return val
        if isinstance(val, str):
            clean = val.replace("mm", "").strip()
            try:
                return float(clean)
            except ValueError:
                pass
        return default

    doc_w = _parse_dim(width, 210)
    doc_h = _parse_dim(height, 297)

    if width == "auto":
        doc_w = content_w

    if height == "auto":
        doc_h = content_h

    root.set("width", f"{doc_w}mm")
    root.set("height", f"{doc_h}mm")

    # ViewBox
    if width == "auto" or height == "auto":
        root.set("viewBox", f"{min_x} {min_y} {doc_w} {doc_h}")
    else:
        root.set("viewBox", f"0 0 {doc_w} {doc_h}")

    # Background for visibility
    bg = ET.SubElement(root, "rect")
    if width == "auto" or height == "auto":
        bg.set("x", str(min_x))
        bg.set("y", str(min_y))
        bg.set("width", str(doc_w))
        bg.set("height", str(doc_h))
    else:
        bg.set("width", "100%")
        bg.set("height", "100%")

    bg.set("fill", COLOR_WHITE)

    # Main group
    main_g = ET.SubElement(root, "g")

    for elem in elements:
        _render_element(elem, main_g)

    return root


def save_svg(root: ET.Element, filename: str) -> None:
    """Save an XML tree to a file.

    Args:
        root (ET.Element): The root element.
        filename (str): The destination path.
    """
    tree = ET.ElementTree(root)
    tree.write(filename, encoding="utf-8", xml_declaration=True)


def render_to_svg(
    elements: list[Element],
    filename: str,
    width: int | str = DEFAULT_DOC_WIDTH,
    height: int | str = DEFAULT_DOC_HEIGHT,
) -> None:
    """High-level function to render elements to an SVG file.

    Args:
        elements (list[Element]): Elements to render.
        filename (str): Output filename.
        width (int | str): Document width.
        height (int | str): Document height.
    """
    root = to_xml_element(elements, width, height)
    save_svg(root, filename)
