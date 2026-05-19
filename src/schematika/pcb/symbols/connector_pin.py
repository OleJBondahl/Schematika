"""Single-pin connector for PCB schematics.

Half the size of `electrical.symbols.connector_pin` due to PCB density.
Layer 2 isolation: pcb does not import from electrical, so this is a
separate copy with its own size constant.
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
CONNECTOR_PIN_SIZE = GRID_SIZE  # 5.0 mm
# Half the standard offset: PCB connector labels are closer to the body.
_LABEL_OFFSET_X = TERMINAL_TEXT_OFFSET_X / 2


def connector_pin(label: str = "", label_pos: str = "left") -> Symbol:
    """Single-pin connector for PCB schematics.

    Port ``"1"`` is at the top edge of the body (local y=0). Body extends
    downward from y=0 to y=CONNECTOR_PIN_SIZE. When placed at
    ``bottom_terminator_y_mm`` the port sits exactly at that y-coordinate and
    the body extends below it, keeping the incoming chain wire clear.

    Args:
        label: Pin tag, e.g. ``"J1:1"``.
        label_pos: ``"left"`` or ``"right"``.

    Returns:
        Symbol with one port ``"1"`` at the top edge (local y=0).

    Raises:
        CircuitValidationError: If ``label_pos`` is not ``"left"`` or ``"right"``.

    Examples:
        >>> sym = connector_pin(label="J1:1")
        >>> list(sym.ports.keys())
        ['1']
    """
    if label_pos not in ("left", "right"):
        msg = f"label_pos must be 'left' or 'right', got {label_pos!r}"
        raise CircuitValidationError(msg)

    half = CONNECTOR_PIN_SIZE / 2
    # Box centered at (0, half) so its top edge is at y=0 and bottom at y=SIZE.
    elements: list[Element] = [
        box(Point(0, half), CONNECTOR_PIN_SIZE, CONNECTOR_PIN_SIZE)
    ]

    if label:
        if label_pos == "right":
            pos = Point(-_LABEL_OFFSET_X, 0)
            anchor = "start"
        else:
            pos = Point(_LABEL_OFFSET_X, 0)
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

    # Port at top edge (y=0); direction Vector(0, -1) = incoming from above.
    port = Port("1", Point(0, 0), Vector(0, -1))
    return Symbol(elements=elements, ports={"1": port}, label=label)
