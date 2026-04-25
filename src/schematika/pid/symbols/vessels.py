"""ISO 14617 vessel and heat exchanger symbol factories."""

from typing import TYPE_CHECKING

from schematika.core import Circle, Line, Point, Port, Style, Symbol, Vector
from schematika.core.parts import create_label_text
from schematika.pid.constants import (
    PID_EQUIPMENT_STROKE,
    PID_HX_RADIUS,
    PID_HX_TUBE_LENGTH_FACTOR,
    PID_HX_TUBE_OFFSET,
    PID_OPEN_TANK_DASH,
    PID_STUB_LENGTH,
    PID_TAG_OFFSET,
    PID_TANK_HALF_HEIGHT,
    PID_TANK_HALF_WIDTH,
    PID_TEXT_SIZE_TAG,
)
from schematika.pid.styles import BODY_STYLE, PIPE_STYLE

if TYPE_CHECKING:
    from schematika.core.geometry import Element

_DASH_STYLE = Style(
    stroke="black",
    stroke_width=PID_EQUIPMENT_STROKE,
    fill="none",
    stroke_dasharray=PID_OPEN_TANK_DASH,
)


def tank(label: str = "", kind: str = "open") -> Symbol:
    """ISO 14617 tank/vessel.

    Rectangle 30mm wide x 40mm tall.
    Open top (kind="open") uses a dashed top line.
    Closed top (kind="closed") uses a solid top line.

    Args:
        label: Component label/tag (e.g., "T-001").
        kind: "open" or "closed".

    Returns:
        Symbol with ports 'inlet' (top-left), 'outlet' (bottom-right),
        'drain' (bottom-center), 'vent' (top-center).
    """
    w = PID_TANK_HALF_WIDTH
    h = PID_TANK_HALF_HEIGHT

    # Body sides and bottom (always solid)
    left = Line(Point(-w, -h), Point(-w, h), BODY_STYLE)
    right = Line(Point(w, -h), Point(w, h), BODY_STYLE)
    bottom = Line(Point(-w, h), Point(w, h), BODY_STYLE)

    # Top line: dashed for open, solid for closed
    top_style = _DASH_STYLE if kind == "open" else BODY_STYLE
    top = Line(Point(-w, -h), Point(w, -h), top_style)

    # Inlet stub at top-left
    inlet_stub = Line(
        Point(-w, -h + PID_STUB_LENGTH),
        Point(-w - PID_STUB_LENGTH, -h + PID_STUB_LENGTH),
        PIPE_STYLE,
    )

    # Outlet stub at bottom-right
    outlet_stub = Line(
        Point(w, h - PID_STUB_LENGTH),
        Point(w + PID_STUB_LENGTH, h - PID_STUB_LENGTH),
        PIPE_STYLE,
    )

    # Drain stub at bottom-center
    drain_stub = Line(Point(0.0, h), Point(0.0, h + PID_STUB_LENGTH), PIPE_STYLE)

    # Vent stub at top-center
    vent_stub = Line(Point(0.0, -h), Point(0.0, -h - PID_STUB_LENGTH), PIPE_STYLE)

    elements: list[Element] = [
        left,
        right,
        bottom,
        top,
        inlet_stub,
        outlet_stub,
        drain_stub,
        vent_stub,
    ]

    if label:
        elements.append(
            create_label_text(
                label,
                Point(0.0, 0.0),
                PID_TEXT_SIZE_TAG,
                dominant_baseline="middle",
            )
        )

    ports = {
        "inlet": Port(
            "inlet", Point(-w - PID_STUB_LENGTH, -h + PID_STUB_LENGTH), Vector(-1, 0)
        ),
        "outlet": Port(
            "outlet", Point(w + PID_STUB_LENGTH, h - PID_STUB_LENGTH), Vector(1, 0)
        ),
        "drain": Port("drain", Point(0.0, h + PID_STUB_LENGTH), Vector(0, 1)),
        "vent": Port("vent", Point(0.0, -h - PID_STUB_LENGTH), Vector(0, -1)),
    }

    return Symbol(elements, ports, label=label)


def heat_exchanger(label: str = "", kind: str = "shell_tube") -> Symbol:  # noqa: ARG001
    """ISO 14617 shell-and-tube heat exchanger.

    Circle (~25mm diameter) with internal lines showing tube passes.

    Args:
        label: Component label/tag (e.g., "HX-001").
        kind: Currently only "shell_tube" is implemented.

    Returns:
        Symbol with ports 'shell_in' (left), 'shell_out' (right),
        'tube_in' (bottom), 'tube_out' (top).
    """
    radius = PID_HX_RADIUS

    body = Circle(center=Point(0.0, 0.0), radius=radius, style=BODY_STYLE)

    # Shell-side: horizontal stubs (left and right)
    shell_in_x = -radius - PID_STUB_LENGTH
    shell_out_x = radius + PID_STUB_LENGTH
    shell_in_line = Line(Point(shell_in_x, 0.0), Point(-radius, 0.0), PIPE_STYLE)
    shell_out_line = Line(Point(radius, 0.0), Point(shell_out_x, 0.0), PIPE_STYLE)

    # Tube-side: vertical stubs (top and bottom)
    tube_in_y = radius + PID_STUB_LENGTH
    tube_out_y = -radius - PID_STUB_LENGTH
    tube_in_line = Line(Point(0.0, radius), Point(0.0, tube_in_y), PIPE_STYLE)
    tube_out_line = Line(Point(0.0, -radius), Point(0.0, tube_out_y), PIPE_STYLE)

    # Internal tube pass indicator (two curved lines suggesting U-tube or two-pass)
    # Represented as two horizontal lines offset vertically inside the circle
    inner_offset = PID_HX_TUBE_OFFSET
    inner_len = radius * PID_HX_TUBE_LENGTH_FACTOR
    tube_pass_top = Line(
        Point(-inner_len, -inner_offset),
        Point(inner_len, -inner_offset),
        BODY_STYLE,
    )
    tube_pass_bot = Line(
        Point(-inner_len, inner_offset),
        Point(inner_len, inner_offset),
        BODY_STYLE,
    )
    # Connecting line on the right side (U-turn)
    tube_return = Line(
        Point(inner_len, -inner_offset),
        Point(inner_len, inner_offset),
        BODY_STYLE,
    )

    elements: list[Element] = [
        body,
        shell_in_line,
        shell_out_line,
        tube_in_line,
        tube_out_line,
        tube_pass_top,
        tube_pass_bot,
        tube_return,
    ]

    if label:
        elements.append(
            create_label_text(
                label,
                Point(0.0, radius + PID_STUB_LENGTH + PID_TAG_OFFSET),
                PID_TEXT_SIZE_TAG,
            )
        )

    ports = {
        "shell_in": Port("shell_in", Point(shell_in_x, 0.0), Vector(-1, 0)),
        "shell_out": Port("shell_out", Point(shell_out_x, 0.0), Vector(1, 0)),
        "tube_in": Port("tube_in", Point(0.0, tube_in_y), Vector(0, 1)),
        "tube_out": Port("tube_out", Point(0.0, tube_out_y), Vector(0, -1)),
    }

    return Symbol(elements, ports, label=label)
