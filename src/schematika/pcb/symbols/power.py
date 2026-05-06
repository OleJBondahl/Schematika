"""PCB-style power-rail symbols: +24V (upward arrow + label)."""

from schematika.core.constants import (
    GRID_SIZE,
    TERMINAL_TEXT_OFFSET_X,
    TERMINAL_TEXT_SIZE,
    TEXT_FONT_FAMILY,
)
from schematika.core.geometry import Element, Point, Style, Vector
from schematika.core.primitives import Line, Text
from schematika.core.symbol import Port, Symbol

_TRI_HALF_WIDTH = 0.5 * GRID_SIZE  # 2.5 mm
_TRI_HEIGHT = 0.6 * GRID_SIZE  # 3.0 mm


def power_24v(label: str = "+24V") -> Symbol:
    """PCB-style +24V power-rail symbol.

    Renders a horizontal line at the port row with the rail name as text below
    the line. The single port sits at (0, 0) and coincides with the line —
    chain wires enter from below and end exactly at the line.

    Args:
        label: Text rendered next to the symbol. Default ``"+24V"``.

    Returns:
        Symbol with one port ``"1"`` at the bottom-center.

    Examples:
        >>> sym = power_24v()
        >>> list(sym.ports.keys())
        ['1']
    """
    port_pt = Point(0, 0)
    line_left = Point(-_TRI_HALF_WIDTH, 0)
    line_right = Point(_TRI_HALF_WIDTH, 0)

    stroke_style = Style(stroke="black", fill="none", stroke_width=0.25)
    text_style = Style(stroke="none", fill="black", font_family=TEXT_FONT_FAMILY)

    elements: list[Element] = [
        Line(line_left, line_right, stroke_style),
        Text(
            content=label,
            position=Point(0, -TERMINAL_TEXT_OFFSET_X),
            style=text_style,
            anchor="middle",
            font_size=TERMINAL_TEXT_SIZE,
        ),
    ]

    port = Port("1", port_pt, Vector(0, -1))
    return Symbol(elements=elements, ports={"1": port}, label=label)


_GND_BAR_WIDTHS = (1.0 * GRID_SIZE, 0.6 * GRID_SIZE, 0.25 * GRID_SIZE)
_GND_BAR_SPACING = 0.18 * GRID_SIZE


def gnd(label: str = "GND") -> Symbol:
    """PCB-style earth-ground symbol.

    Renders three horizontal bars of decreasing width below the port. Port at
    the top, facing upward (wire enters from above).

    Args:
        label: Text rendered next to the symbol. Default ``"GND"``.

    Returns:
        Symbol with one port ``"1"`` at the top.

    Examples:
        >>> sym = gnd()
        >>> list(sym.ports.keys())
        ['1']
    """
    port_pt = Point(0, 0)
    style = Style(stroke="black", fill="none", stroke_width=0.25)

    elements: list[Element] = [
        Line(port_pt, Point(0, _GND_BAR_SPACING * 0.5), style),
    ]

    for i, width in enumerate(_GND_BAR_WIDTHS):
        y = _GND_BAR_SPACING * (0.5 + i)
        elements.append(
            Line(
                Point(-width / 2, y),
                Point(width / 2, y),
                style,
            )
        )

    elements.append(
        Text(
            content=label,
            position=Point(0, -TERMINAL_TEXT_OFFSET_X),
            anchor="middle",
            font_size=TERMINAL_TEXT_SIZE,
            style=Style(stroke="none", fill="black", font_family=TEXT_FONT_FAMILY),
        )
    )

    port = Port("1", port_pt, Vector(0, -1))
    return Symbol(elements=elements, ports={"1": port}, label=label)
