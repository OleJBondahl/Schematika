"""
Block symbol factories for block diagrams.

Provides factory functions to create rectangular block symbols with
labelled ports, and a legend symbol for cable type identification.
"""

from __future__ import annotations

from schematika.block.constants import (
    BLOCK_DEFAULT_HEIGHT,
    BLOCK_DEFAULT_WIDTH,
    BLOCK_STROKE_WIDTH,
    BLOCK_TEXT_SIZE_LABEL,
    BLOCK_TEXT_SIZE_NOTE,
    LEGEND_ENTRY_HEIGHT,
    LEGEND_LINE_SAMPLE_LENGTH,
)
from schematika.block.model import BlockPort, CableStyle
from schematika.core.geometry import Element, Point, Style, Vector
from schematika.core.primitives import Line, Text
from schematika.core.symbol import Port, Symbol

__all__ = [
    "block_symbol",
    "legend_symbol",
]

# ---------------------------------------------------------------------------
# Default ports (center of each side)
# ---------------------------------------------------------------------------

_DEFAULT_PORTS = [
    BlockPort(id="left", side="left", position=0.5),
    BlockPort(id="right", side="right", position=0.5),
    BlockPort(id="top", side="top", position=0.5),
    BlockPort(id="bottom", side="bottom", position=0.5),
]

# Side → direction vector (outward from block)
_SIDE_DIRECTIONS: dict[str, Vector] = {
    "left": Vector(-1, 0),
    "right": Vector(1, 0),
    "top": Vector(0, -1),
    "bottom": Vector(0, 1),
}


def _port_position(side: str, position: float, half_w: float, half_h: float) -> Point:
    """Calculate absolute port position from side and fractional position."""
    if side == "left":
        return Point(-half_w, -half_h + position * (2 * half_h))
    elif side == "right":
        return Point(half_w, -half_h + position * (2 * half_h))
    elif side == "top":
        return Point(-half_w + position * (2 * half_w), -half_h)
    elif side == "bottom":
        return Point(-half_w + position * (2 * half_w), half_h)
    else:
        raise ValueError(
            f"side must be 'left', 'right', 'top', or 'bottom'; got {side!r}"
        )


# ---------------------------------------------------------------------------
# Block symbol
# ---------------------------------------------------------------------------


def block_symbol(
    label: str,
    width: float = BLOCK_DEFAULT_WIDTH,
    height: float = BLOCK_DEFAULT_HEIGHT,
    *,
    ports: list[BlockPort] | None = None,
    fill: str = "none",
    stroke_width: float = BLOCK_STROKE_WIDTH,
) -> Symbol:
    """Create a rectangular block symbol centred at the origin.

    The block is drawn as four lines forming a rectangle with a centred
    text label.  Ports default to the centre of each side but can be
    overridden via the *ports* parameter.

    Args:
        label: Text label displayed inside the block.
        width: Block width in mm.
        height: Block height in mm.
        ports: Custom port definitions.  If ``None``, default ports at
               the centre of each side are created.
        fill: CSS fill color for the rectangle interior.
        stroke_width: Stroke width for the rectangle outline.

    Returns:
        A ``Symbol`` centred at the origin.
    """
    half_w = width / 2
    half_h = height / 2

    rect_style = Style(stroke="black", stroke_width=stroke_width, fill=fill)

    # Rectangle as four lines
    tl = Point(-half_w, -half_h)
    tr = Point(half_w, -half_h)
    br = Point(half_w, half_h)
    bl = Point(-half_w, half_h)

    elements: list[Element] = [
        Line(start=tl, end=tr, style=rect_style),  # top
        Line(start=tr, end=br, style=rect_style),  # right
        Line(start=br, end=bl, style=rect_style),  # bottom
        Line(start=bl, end=tl, style=rect_style),  # left
    ]

    # Centre label
    label_style = Style(stroke="none", fill="black")
    elements.append(
        Text(
            content=label,
            position=Point(0, 0),
            style=label_style,
            anchor="middle",
            dominant_baseline="central",
            font_size=BLOCK_TEXT_SIZE_LABEL,
        )
    )

    # Build ports dict
    port_defs = ports if ports is not None else _DEFAULT_PORTS
    port_dict: dict[str, Port] = {}
    for bp in port_defs:
        pos = _port_position(bp.side, bp.position, half_w, half_h)
        direction = _SIDE_DIRECTIONS.get(bp.side, Vector(1, 0))
        port_dict[bp.id] = Port(id=bp.id, position=pos, direction=direction)

    return Symbol(elements=elements, ports=port_dict, label=label)


# ---------------------------------------------------------------------------
# Legend symbol
# ---------------------------------------------------------------------------


def legend_symbol(
    entries: list[tuple[str, CableStyle]],
    notes: list[str] | None = None,
) -> Symbol:
    """Create a legend box showing cable type samples and labels.

    Each entry renders a short line sample in the cable style followed by
    its label text.  Optional *notes* are appended below the entries.

    Args:
        entries: List of ``(label, CableStyle)`` tuples.
        notes: Optional list of note strings to display below the legend.

    Returns:
        A ``Symbol`` (no ports) positioned with top-left near the origin.
    """
    elements: list[Element] = []
    text_style = Style(stroke="none", fill="black")
    y = 0.0

    for entry_label, cable_style in entries:
        line_style = Style(
            stroke=cable_style.color,
            stroke_width=cable_style.stroke_width,
            fill="none",
            stroke_dasharray=cable_style.dash_pattern,
        )
        # Line sample
        elements.append(
            Line(
                start=Point(0, y),
                end=Point(LEGEND_LINE_SAMPLE_LENGTH, y),
                style=line_style,
            )
        )
        # Label text to the right of the sample
        elements.append(
            Text(
                content=entry_label,
                position=Point(LEGEND_LINE_SAMPLE_LENGTH + BLOCK_TEXT_SIZE_NOTE, y),
                style=text_style,
                anchor="start",
                dominant_baseline="central",
                font_size=BLOCK_TEXT_SIZE_NOTE,
            )
        )
        y += LEGEND_ENTRY_HEIGHT

    # Optional notes
    if notes:
        y += LEGEND_ENTRY_HEIGHT * 0.5  # extra gap before notes
        for note in notes:
            elements.append(
                Text(
                    content=note,
                    position=Point(0, y),
                    style=text_style,
                    anchor="start",
                    dominant_baseline="central",
                    font_size=BLOCK_TEXT_SIZE_NOTE,
                )
            )
            y += LEGEND_ENTRY_HEIGHT

    return Symbol(elements=elements, ports={}, label="legend")
