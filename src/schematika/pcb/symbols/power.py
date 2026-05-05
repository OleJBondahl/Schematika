"""PCB-style power-rail symbols: +24V (upward arrow + label)."""

from schematika.core.constants import (
    GRID_SIZE,
    TERMINAL_TEXT_SIZE,
    TEXT_FONT_FAMILY,
)
from schematika.core.geometry import Element, Point, Style, Vector
from schematika.core.primitives import Line, Text
from schematika.core.symbol import Port, Symbol

_TRI_HALF_WIDTH = 0.5 * GRID_SIZE  # 2.5 mm
_TRI_HEIGHT = 0.6 * GRID_SIZE  # 3.0 mm
_TEXT_GAP = 0.3 * GRID_SIZE  # 1.5 mm — space between text and triangle base


def power_24v(label: str = "+24V") -> Symbol:
    """PCB-style +24V power-rail symbol.

    Renders an upward-pointing triangle with the rail name as text below it.
    The single port sits at the triangle apex (bottom in symbol-local coords)
    and faces upward — chains enter from below.

    Args:
        label: Text rendered next to the symbol. Default ``"+24V"``.

    Returns:
        Symbol with one port ``"1"`` at the apex.

    Examples:
        >>> sym = power_24v()
        >>> list(sym.ports.keys())
        ['1']
    """
    apex = Point(0, 0)
    base_left = Point(-_TRI_HALF_WIDTH, -_TRI_HEIGHT)
    base_right = Point(_TRI_HALF_WIDTH, -_TRI_HEIGHT)

    stroke_style = Style(stroke="black", fill="none", stroke_width=0.25)
    text_style = Style(stroke="none", fill="black", font_family=TEXT_FONT_FAMILY)

    elements: list[Element] = [
        Line(apex, base_left, stroke_style),
        Line(base_left, base_right, stroke_style),
        Line(base_right, apex, stroke_style),
        Text(
            content=label,
            position=Point(0, -_TRI_HEIGHT - _TEXT_GAP),
            style=text_style,
            anchor="middle",
            font_size=TERMINAL_TEXT_SIZE,
        ),
    ]

    port = Port("1", apex, Vector(0, -1))
    return Symbol(elements=elements, ports={"1": port}, label=label)
