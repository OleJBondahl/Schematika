"""Factory functions for IEC 60617 coil symbols.

Provides symbol factories for relay and contactor coils. Imports constants
and core types from ``electrical/model/``.
"""

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
    label: str = "", pins: tuple[str, ...] = COIL_PINS, *, show_terminals: bool = True
) -> Symbol:
    """IEC 60617 relay/contactor coil (square body).

    Default pin IDs follow IEC 60947: ``"A1"`` (top) and ``"A2"`` (bottom).
    When ``show_terminals=False`` no ports are generated.

    Ports:
        A1: top terminal (supply side).
        A2: bottom terminal (return side).

    Args:
        label: Component tag, e.g. ``"-K1"``.
        pins: Pin IDs, defaults to ``("A1", "A2")``.
        show_terminals: Draw lead lines and expose ports; set to ``False`` when
            embedding inside a composite symbol like :func:`contactor`.

    Returns:
        Symbol with ``A1``/``A2`` ports (or none if ``show_terminals=False``).

    Examples:
        >>> from schematika.electrical.symbols import coil
        >>> sym = coil(label="-K1")
        >>> sorted(sym.ports.keys())
        ['A1', 'A2']
        >>> sym_no_term = coil(show_terminals=False)
        >>> sym_no_term.ports
        {}
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
