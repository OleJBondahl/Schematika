"""ConnectorBlock — a unified multi-pin connector symbol for PCB sheets.

Renders one wide horizontal rectangle with a ref designator above the body,
an optional functional label further above, and N pin sockets emerging from
the bottom edge facing downward. Used as the anchor of a connector-block in
the schematika.pcb layout algorithm — every walk starts from one of these.
Beneath each pin a vertical column of placed symbols stacks downward.
"""

from collections.abc import Sequence

from schematika.core.constants import (
    GRID_SIZE,
    TERMINAL_TEXT_SIZE,
    TEXT_FONT_FAMILY,
)
from schematika.core.geometry import Element, Point, Style, Vector
from schematika.core.parts import box
from schematika.core.primitives import Text
from schematika.core.symbol import Port, Symbol

_PIN_SPACING = 2 * GRID_SIZE  # 10 mm horizontal distance between pins
_SIDE_PADDING = GRID_SIZE  # 5 mm left/right padding so pins aren't flush to the edge
_BLOCK_HEIGHT = 2 * GRID_SIZE  # 10 mm — compact vertical extent of body


def connector_block(
    ref: str,
    pins: Sequence[str],
    functional_label: str | None = None,
) -> Symbol:
    """Composite multi-pin connector rendered as one block.

    Args:
        ref: Reference designator (e.g. ``"J1"``).
        pins: Pin identifiers in display order. Must be non-empty.
        functional_label: Optional human description rendered above the ref.

    Returns:
        Symbol with one port per pin id, all facing downward.

    Raises:
        ValueError: If ``pins`` is empty.

    Examples:
        >>> sym = connector_block(ref="J1", pins=("1", "2", "3", "4"))
        >>> sorted(sym.ports.keys())
        ['1', '2', '3', '4']
    """
    if len(pins) == 0:
        msg = "connector_block requires at least one pin"
        raise ValueError(msg)

    text_style = Style(stroke="none", fill="black", font_family=TEXT_FONT_FAMILY)

    block_width = _SIDE_PADDING + len(pins) * _PIN_SPACING + _SIDE_PADDING

    elements: list[Element] = [
        box(Point(block_width / 2, _BLOCK_HEIGHT / 2), block_width, _BLOCK_HEIGHT)
    ]

    # ref sits above the body (negative y = upward in SVG), centered horizontally.
    elements.append(
        Text(
            content=ref,
            position=Point(block_width / 2, -TERMINAL_TEXT_SIZE * 0.5),
            anchor="middle",
            font_size=TERMINAL_TEXT_SIZE,
            style=text_style,
        )
    )

    if functional_label:
        # functional_label sits further above the ref.
        elements.append(
            Text(
                content=functional_label,
                position=Point(block_width / 2, -TERMINAL_TEXT_SIZE * 1.7),
                anchor="middle",
                font_size=TERMINAL_TEXT_SIZE,
                style=text_style,
            )
        )

    ports: dict[str, Port] = {}
    for index, pin_id in enumerate(pins):
        pin_x = _SIDE_PADDING + (index + 0.5) * _PIN_SPACING
        # Pin number label just inside the top edge of the body.
        elements.append(
            Text(
                content=str(pin_id),
                position=Point(pin_x, _BLOCK_HEIGHT - 0.2 * GRID_SIZE),
                anchor="middle",
                font_size=0.7 * GRID_SIZE,
                style=text_style,
            )
        )
        # Port on the bottom edge, direction facing down (positive y in SVG).
        ports[str(pin_id)] = Port(
            str(pin_id),
            Point(pin_x, _BLOCK_HEIGHT),
            Vector(0, 1),
        )

    return Symbol(elements=elements, ports=ports, label=ref)
