"""Half-size square connector-pin symbol — for PCB-style schematics.

Half the side length of schematika.electrical.symbols.connector_pin to keep
PCB sheets visually denser. Layer 2 isolation: pcb does not import from
electrical, so this is a separate copy with its own size constant.
"""

from schematika.core.constants import (
    GRID_SIZE,
    TERMINAL_TEXT_OFFSET_X,
    TERMINAL_TEXT_SIZE,
    TEXT_FONT_FAMILY,
)
from schematika.core.exceptions import CircuitValidationError
from schematika.core.geometry import Element, Point, Style, Vector
from schematika.core.parts import box
from schematika.core.primitives import Text
from schematika.core.symbol import Port, Symbol

# Half of the electrical connector_pin (which is 2 * GRID_SIZE).
CONNECTOR_PIN_SMALL_SIZE = GRID_SIZE  # 5.0 mm
_PORT_OFFSET_Y = CONNECTOR_PIN_SMALL_SIZE / 2


def connector_pin_small(label: str = "", label_pos: str = "left") -> Symbol:
    """Half-size square single-pin connector for PCB schematics.

    Args:
        label: Pin tag, e.g. ``"J1:1"``.
        label_pos: ``"left"`` or ``"right"``.

    Returns:
        Symbol with one port ``"1"`` at the bottom edge.

    Raises:
        CircuitValidationError: If ``label_pos`` is not ``"left"`` or ``"right"``.

    Examples:
        >>> sym = connector_pin_small(label="J1:1")
        >>> list(sym.ports.keys())
        ['1']
    """
    if label_pos not in ("left", "right"):
        msg = f"label_pos must be 'left' or 'right', got {label_pos!r}"
        raise CircuitValidationError(msg)

    elements: list[Element] = [
        box(Point(0, 0), CONNECTOR_PIN_SMALL_SIZE, CONNECTOR_PIN_SMALL_SIZE)
    ]

    if label:
        if label_pos == "right":
            pos = Point(-TERMINAL_TEXT_OFFSET_X, 0)
            anchor = "start"
        else:
            pos = Point(TERMINAL_TEXT_OFFSET_X, 0)
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

    port = Port("1", Point(0, _PORT_OFFSET_Y), Vector(0, 1))
    return Symbol(elements=elements, ports={"1": port}, label=label)
