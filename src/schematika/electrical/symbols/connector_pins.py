"""Square single-pin connector symbol, IEC-style — peer to terminals.py."""

from schematika.core.constants import (
    GRID_SIZE,
    TERMINAL_TEXT_OFFSET_X,
    TERMINAL_TEXT_OFFSET_X_CLOSE,
    TERMINAL_TEXT_SIZE,
    TEXT_FONT_FAMILY,
)
from schematika.core.geometry import Point, Style, Vector
from schematika.core.parts import box
from schematika.core.primitives import Text
from schematika.core.symbol import Port, Symbol

# Square side = 2 × GRID_SIZE = 10 mm  (≈ 2× the terminal circle diameter of 2.5 mm)
CONNECTOR_PIN_SIZE = 2 * GRID_SIZE  # 10.0 mm

# Port sits at the bottom edge of the square
_PORT_OFFSET_Y = CONNECTOR_PIN_SIZE / 2


def connector_pin(
    label: str = "",
    pin_label: str | None = None,
    label_pos: str = "left",
) -> Symbol:
    """Single-pin square connector symbol."""
    if label_pos not in ("left", "right"):
        raise ValueError(f"label_pos must be 'left' or 'right', got {label_pos!r}")

    elements = [box(Point(0, 0), CONNECTOR_PIN_SIZE, CONNECTOR_PIN_SIZE)]

    if label:
        offset = (
            TERMINAL_TEXT_OFFSET_X_CLOSE
            if pin_label is not None and pin_label != label_pos
            else TERMINAL_TEXT_OFFSET_X
        )
        if label_pos == "right":
            pos = Point(-offset, 0)
            anchor = "start"
        else:
            pos = Point(offset, 0)
            anchor = "end"
        elements.append(
            Text(
                content=label,
                position=pos,
                anchor=anchor,
                font_size=TERMINAL_TEXT_SIZE,
                style=Style(stroke="none", fill="black", font_family=TEXT_FONT_FAMILY),
            )
        )

    if pin_label:
        pin_x = (
            _PORT_OFFSET_Y + 0.3 * GRID_SIZE
            if label_pos == "left"
            else -(_PORT_OFFSET_Y + 0.3 * GRID_SIZE)
        )
        pin_anchor = "start" if label_pos == "left" else "end"
        elements.append(
            Text(
                content=pin_label,
                position=Point(pin_x, _PORT_OFFSET_Y),
                anchor=pin_anchor,
                font_size=0.7 * GRID_SIZE,
                style=Style(stroke="none", fill="black", font_family=TEXT_FONT_FAMILY),
            )
        )

    port = Port("1", Point(0, _PORT_OFFSET_Y), Vector(0, 1))
    return Symbol(elements=elements, ports={"1": port}, label=label)
