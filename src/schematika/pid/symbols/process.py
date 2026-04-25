"""ISO 14617 process equipment symbol factories."""

from typing import TYPE_CHECKING

from schematika.core import (
    Circle,
    Line,
    Point,
    Polygon,
    Port,
    Symbol,
    Vector,
)
from schematika.core.parts import create_label_text
from schematika.pid.constants import (
    PID_PUMP_RADIUS,
    PID_STUB_LENGTH,
    PID_TEXT_SIZE_TAG,
)
from schematika.pid.styles import BODY_STYLE, FILL_STYLE, PIPE_STYLE

if TYPE_CHECKING:
    from schematika.core.geometry import Element


def _pump_symbol(label: str, radius: float = PID_PUMP_RADIUS) -> Symbol:
    """Shared implementation for ISO 14617 pump symbols.

    Circle body with internal filled triangle (flow direction indicator).
    Horizontal flow-through: inlet on the left, outlet on the right.
    """
    body = Circle(center=Point(0.0, 0.0), radius=radius, style=BODY_STYLE)

    inlet_x = -radius - PID_STUB_LENGTH
    inlet_line = Line(
        start=Point(inlet_x, 0.0),
        end=Point(-radius, 0.0),
        style=PIPE_STYLE,
    )

    outlet_x = radius + PID_STUB_LENGTH
    outlet_line = Line(
        start=Point(radius, 0.0),
        end=Point(outlet_x, 0.0),
        style=PIPE_STYLE,
    )

    tri_size = PID_STUB_LENGTH
    triangle = Polygon(
        points=[
            Point(-tri_size * 0.5, -tri_size * 0.5),
            Point(-tri_size * 0.5, tri_size * 0.5),
            Point(tri_size * 0.5, 0.0),
        ],
        style=FILL_STYLE,
    )

    elements: list[Element] = [body, inlet_line, outlet_line, triangle]

    if label:
        elements.append(
            create_label_text(
                label, Point(0.0, radius + PID_STUB_LENGTH), PID_TEXT_SIZE_TAG
            )
        )

    ports = {
        "inlet": Port("inlet", Point(inlet_x, 0.0), Vector(-1, 0)),
        "outlet": Port("outlet", Point(outlet_x, 0.0), Vector(1, 0)),
    }

    return Symbol(elements, ports, label=label)


def centrifugal_pump(label: str = "") -> Symbol:
    """Centrifugal pump symbol per ISO 14617.

    Circle with an internal filled triangle indicating flow direction.
    Horizontal flow-through: inlet on the left, outlet on the right.

    Port IDs:
        ``"inlet"`` — process inlet (left, west).
        ``"outlet"`` — process outlet (right, east).

    Args:
        label: Component tag, e.g. ``"P-001"``.

    Returns:
        Symbol: Centrifugal pump with two horizontal ports.

    Examples:
        >>> from schematika.pid import centrifugal_pump
        >>> sym = centrifugal_pump("P-001")
        >>> sorted(sym.ports)
        ['inlet', 'outlet']
        >>> sym.label
        'P-001'
    """
    return _pump_symbol(label)


def positive_displacement_pump(label: str = "") -> Symbol:
    """Positive displacement pump symbol per ISO 14617.

    Circle (~20mm diameter) with an internal triangular arrow pointing rightward.

    Port IDs:
        ``"inlet"`` — process inlet (left, west).
        ``"outlet"`` — process outlet (right, east).

    Args:
        label: Component tag, e.g. ``"PD-001"``.

    Returns:
        Symbol: Positive displacement pump with two horizontal ports.

    Examples:
        >>> from schematika.pid import positive_displacement_pump
        >>> sym = positive_displacement_pump("PD-001")
        >>> sorted(sym.ports)
        ['inlet', 'outlet']
        >>> sym.label
        'PD-001'
    """
    return _pump_symbol(label)
