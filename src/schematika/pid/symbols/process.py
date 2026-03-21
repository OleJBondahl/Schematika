"""
ISO 14617 process equipment symbol factories.
"""

from schematika.core import (
    Circle,
    Line,
    Point,
    Polygon,
    Port,
    Style,
    Symbol,
    Text,
    Vector,
)
from schematika.core.constants import TEXT_FONT_FAMILY
from schematika.core.geometry import Element
from schematika.pid.constants import (
    PID_EQUIPMENT_STROKE,
    PID_LINE_WEIGHT,
    PID_PUMP_RADIUS,
    PID_STUB_LENGTH,
    PID_TEXT_SIZE_TAG,
)

_PIPE_STYLE = Style(stroke="black", stroke_width=PID_LINE_WEIGHT, fill="none")
_BODY_STYLE = Style(stroke="black", stroke_width=PID_EQUIPMENT_STROKE, fill="none")
_FILL_STYLE = Style(stroke="black", stroke_width=PID_EQUIPMENT_STROKE, fill="black")
_TEXT_STYLE = Style(stroke="none", fill="black", font_family=TEXT_FONT_FAMILY)


def centrifugal_pump(label: str = "") -> Symbol:
    """ISO 14617 centrifugal pump symbol.

    A circle with an internal filled triangle (flow direction indicator).
    Horizontal flow-through: inlet on the left, outlet on the right.

    Args:
        label: Component label/tag (e.g., "P-001").

    Returns:
        Symbol with ports 'inlet' (left) and 'outlet' (right).
    """
    radius = PID_PUMP_RADIUS

    body = Circle(center=Point(0.0, 0.0), radius=radius, style=_BODY_STYLE)

    inlet_x = -radius - PID_STUB_LENGTH
    inlet_line = Line(
        start=Point(inlet_x, 0.0),
        end=Point(-radius, 0.0),
        style=_PIPE_STYLE,
    )

    outlet_x = radius + PID_STUB_LENGTH
    outlet_line = Line(
        start=Point(radius, 0.0),
        end=Point(outlet_x, 0.0),
        style=_PIPE_STYLE,
    )

    # Internal filled triangle pointing right (flow direction indicator)
    tri_size = PID_STUB_LENGTH
    triangle = Polygon(
        points=[
            Point(-tri_size * 0.5, -tri_size * 0.5),
            Point(-tri_size * 0.5, tri_size * 0.5),
            Point(tri_size * 0.5, 0.0),
        ],
        style=_FILL_STYLE,
    )

    elements: list[Element] = [body, inlet_line, outlet_line, triangle]

    if label:
        elements.append(
            Text(
                content=label,
                position=Point(0.0, radius + PID_STUB_LENGTH),
                style=_TEXT_STYLE,
                anchor="middle",
                dominant_baseline="auto",
                font_size=PID_TEXT_SIZE_TAG,
            )
        )

    ports = {
        "inlet": Port("inlet", Point(inlet_x, 0.0), Vector(-1, 0)),
        "outlet": Port("outlet", Point(outlet_x, 0.0), Vector(1, 0)),
    }

    return Symbol(elements, ports, label=label)


def positive_displacement_pump(label: str = "") -> Symbol:
    """ISO 14617 positive displacement pump.

    Circle (~20mm diameter) with an internal triangular arrow pointing rightward.

    Args:
        label: Component label/tag.

    Returns:
        Symbol with ports 'inlet' (left) and 'outlet' (right).
    """
    radius = PID_PUMP_RADIUS

    body = Circle(center=Point(0.0, 0.0), radius=radius, style=_BODY_STYLE)

    # Inlet stub
    inlet_x = -radius - PID_STUB_LENGTH
    inlet_line = Line(
        start=Point(inlet_x, 0.0),
        end=Point(-radius, 0.0),
        style=_PIPE_STYLE,
    )

    # Outlet stub
    outlet_x = radius + PID_STUB_LENGTH
    outlet_line = Line(
        start=Point(radius, 0.0),
        end=Point(outlet_x, 0.0),
        style=_PIPE_STYLE,
    )

    # Internal triangle pointing right (flow direction indicator)
    tri_size = PID_STUB_LENGTH
    triangle = Polygon(
        points=[
            Point(-tri_size * 0.5, -tri_size * 0.5),
            Point(-tri_size * 0.5, tri_size * 0.5),
            Point(tri_size * 0.5, 0.0),
        ],
        style=_FILL_STYLE,
    )

    elements: list[Element] = [body, inlet_line, outlet_line, triangle]

    if label:
        elements.append(
            Text(
                content=label,
                position=Point(0.0, radius + PID_STUB_LENGTH),
                style=_TEXT_STYLE,
                anchor="middle",
                dominant_baseline="auto",
                font_size=PID_TEXT_SIZE_TAG,
            )
        )

    ports = {
        "inlet": Port("inlet", Point(inlet_x, 0.0), Vector(-1, 0)),
        "outlet": Port("outlet", Point(outlet_x, 0.0), Vector(1, 0)),
    }

    return Symbol(elements, ports, label=label)
