from schematika.electrical.model.constants import COIL_PINS, GRID_SIZE, GRID_SUBDIVISION
from schematika.electrical.model.core import Point, Port, Symbol, Vector
from schematika.electrical.model.parts import (
    box,
    create_pin_labels,
    standard_style,
    standard_text,
)
from schematika.electrical.model.primitives import Line

"""
IEC 60617 Coil Symbols.
"""


def coil(
    label: str = "", pins: tuple[str, ...] = COIL_PINS, show_terminals: bool = True
) -> Symbol:
    """IEC 60617 Coil symbol (Square).

    Args:
        label: Component tag (e.g. "-K1").
        pins: Pin numbers (e.g. ("A1", "A2")).
        show_terminals: Whether to draw leads and ports.

    Returns:
        Symbol: The coil symbol.
    """
    width = 2 * GRID_SIZE
    height = GRID_SIZE

    body = box(Point(0, 0), width, height)
    style = standard_style()

    elements = [body]
    ports = {}

    if show_terminals:
        # Pins
        pin_len = GRID_SUBDIVISION
        top_y_box = -height / 2
        bot_y_box = height / 2

        top_y_port = top_y_box - pin_len
        bot_y_port = bot_y_box + pin_len

        l1 = Line(Point(0, top_y_box), Point(0, top_y_port), style)
        l2 = Line(Point(0, bot_y_box), Point(0, bot_y_port), style)

        top_pin = pins[0]
        bot_pin = pins[1]
        ports = {
            top_pin: Port(top_pin, Point(0, top_y_port), Vector(0, -1)),
            bot_pin: Port(bot_pin, Point(0, bot_y_port), Vector(0, 1)),
        }
        elements.extend([l1, l2])

    if label:
        # Place label half grid more to the left because
        # coil is wider than other symbols
        elements.append(standard_text(label, Point(-GRID_SUBDIVISION, 0)))

    if pins and show_terminals:
        elements.extend(create_pin_labels(ports, pins))

    return Symbol(elements, ports, label=label)
