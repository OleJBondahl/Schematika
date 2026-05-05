"""ConnectorBlock — a unified multi-pin connector symbol for PCB sheets."""

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
from schematika.pcb.layout_spec import LayoutSpec


def connector_block(
    ref: str,
    pins: Sequence[str],
    functional_label: str | None = None,
    *,
    layout: LayoutSpec | None = None,
) -> Symbol:
    """Composite multi-pin connector rendered as one block.

    Args:
        ref: Reference designator.
        pins: Pin identifiers in display order.
        functional_label: Optional human description rendered above the ref.
        layout: Layout spec for spacing. Defaults to LayoutSpec().

    Examples:
        >>> sym = connector_block(ref="J1", pins=("1", "2"))
        >>> sorted(sym.ports.keys())
        ['1', '2']
    """
    if len(pins) == 0:
        msg = "connector_block requires at least one pin"
        raise ValueError(msg)
    if layout is None:
        layout = LayoutSpec()

    pin_spacing = layout.pin_spacing_mm
    side_padding = layout.side_padding_mm
    block_height = layout.block_height_mm

    text_style = Style(stroke="none", fill="black", font_family=TEXT_FONT_FAMILY)
    block_width = side_padding + len(pins) * pin_spacing + side_padding

    elements: list[Element] = [
        box(Point(block_width / 2, block_height / 2), block_width, block_height)
    ]
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
        pin_x = side_padding + (index + 0.5) * pin_spacing
        elements.append(
            Text(
                content=str(pin_id),
                position=Point(pin_x, block_height - 0.2 * GRID_SIZE),
                anchor="middle",
                font_size=0.7 * GRID_SIZE,
                style=text_style,
            )
        )
        ports[str(pin_id)] = Port(
            str(pin_id),
            Point(pin_x, block_height),
            Vector(0, 1),
        )

    return Symbol(elements=elements, ports=ports, label=ref)
