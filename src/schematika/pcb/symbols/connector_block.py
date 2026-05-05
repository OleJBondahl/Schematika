"""ConnectorBlock — a unified multi-pin connector symbol for PCB sheets.

Renders one tall rectangle with a ref designator at the top, an optional
functional label above the ref, and N pin sockets emerging from the right
edge. Used as the anchor of a connector-block in the schematika.pcb layout
algorithm — every walk starts from one of these.
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

_BLOCK_WIDTH = 2 * GRID_SIZE  # 10 mm — same as electrical connector_pin width
_PIN_SPACING = 2 * GRID_SIZE  # 10 mm vertical between pins
_TOP_PADDING = GRID_SIZE  # 5 mm above first pin (for ref + functional label)


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
        Symbol with one port per pin id, all facing right.

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

    block_height = _TOP_PADDING + len(pins) * _PIN_SPACING

    elements: list[Element] = [
        box(Point(0, block_height / 2), _BLOCK_WIDTH, block_height)
    ]

    # ref sits above the body (negative y = upward in SVG). functional_label
    # sits inside the top padding region, clearly below the ref.
    elements.append(
        Text(
            content=ref,
            position=Point(0, -TERMINAL_TEXT_SIZE * 0.5),
            anchor="middle",
            font_size=TERMINAL_TEXT_SIZE,
            style=text_style,
        )
    )

    if functional_label:
        elements.append(
            Text(
                content=functional_label,
                position=Point(0, _TOP_PADDING * 0.5),
                anchor="middle",
                font_size=TERMINAL_TEXT_SIZE,
                style=text_style,
            )
        )

    ports: dict[str, Port] = {}
    for index, pin_id in enumerate(pins):
        pin_y = _TOP_PADDING + (index + 0.5) * _PIN_SPACING
        elements.append(
            Text(
                content=str(pin_id),
                position=Point(_BLOCK_WIDTH / 2 - 0.2 * GRID_SIZE, pin_y),
                anchor="end",
                font_size=0.7 * GRID_SIZE,
                style=text_style,
            )
        )
        ports[str(pin_id)] = Port(
            str(pin_id),
            Point(_BLOCK_WIDTH / 2, pin_y),
            Vector(1, 0),
        )

    return Symbol(elements=elements, ports=ports, label=ref)
