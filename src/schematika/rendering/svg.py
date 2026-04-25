"""SVG render shell: XML tree construction + file I/O. Not pure (lives outside core)."""

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


def _render_text(elem: Text, parent: ET.Element) -> None:
    """Render a Text element into *parent*; handles optional rotation."""
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


def _render_group(elem: Group, parent: ET.Element) -> None:
    """Render a Group element into *parent*; applies optional group style."""
    g = ET.SubElement(parent, "g")
    if elem.style:
        g.set("style", _style_to_str(elem.style))
    for child in elem.elements:
        _render_element(child, g)


def _render_element(elem: Element, parent: ET.Element) -> None:
    """Mutates *parent* in place; recurses into Group/Symbol."""
    match elem:
        case Line():
            e = ET.SubElement(parent, "line")
            e.set("x1", str(elem.start.x))
            e.set("y1", str(elem.start.y))
            e.set("x2", str(elem.end.x))
            e.set("y2", str(elem.end.y))
            e.set("style", _style_to_str(elem.style))
        case Circle():
            e = ET.SubElement(parent, "circle")
            e.set("cx", str(elem.center.x))
            e.set("cy", str(elem.center.y))
            e.set("r", str(elem.radius))
            e.set("style", _style_to_str(elem.style))
        case Text():
            _render_text(elem, parent)
        case Path():
            e = ET.SubElement(parent, "path")
            e.set("d", elem.d)
            e.set("style", _style_to_str(elem.style))
        case Group():
            _render_group(elem, parent)
        case Polygon():
            e = ET.SubElement(parent, "polygon")
            points_str = " ".join([f"{p.x},{p.y}" for p in elem.points])
            e.set("points", points_str)
            e.set("style", _style_to_str(elem.style))
        case Symbol():
            # Symbol is effectively a group
            g = ET.SubElement(parent, "g")
            g.set("class", "symbol")
            for child in elem.elements:
                _render_element(child, g)


def _resolve_dim(val: int | str, default: float, auto_value: float) -> float:
    """Return *auto_value* when *val* is ``"auto"``, else parse the dimension."""
    if val == "auto":
        return auto_value
    if isinstance(val, (int, float)):
        return val
    if isinstance(val, str):
        clean = val.replace("mm", "").strip()
        try:
            return float(clean)
        except ValueError:
            pass
    return default


def to_xml_element(
    elements: list[Element],
    width: int | str = DEFAULT_DOC_WIDTH,
    height: int | str = DEFAULT_DOC_HEIGHT,
) -> ET.Element:
    """Pass `"auto"` for either dimension to size from element bounds (with padding)."""
    root = ET.Element("svg")
    root.set("xmlns", "http://www.w3.org/2000/svg")

    # Calculate bounds if auto
    min_x, min_y, max_x, max_y = 0, 0, 0, 0
    content_w, content_h = 0.0, 0.0
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

    doc_w = _resolve_dim(width, 210, content_w)
    doc_h = _resolve_dim(height, 297, content_h)

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
    """Writes XML with `<?xml ?>` declaration to *filename*."""
    tree = ET.ElementTree(root)
    tree.write(filename, encoding="utf-8", xml_declaration=True)


def render_to_svg(
    elements: list[Element],
    filename: str,
    width: int | str = DEFAULT_DOC_WIDTH,
    height: int | str = DEFAULT_DOC_HEIGHT,
) -> None:
    """`to_xml_element` + `save_svg`."""
    root = to_xml_element(elements, width, height)
    save_svg(root, filename)
