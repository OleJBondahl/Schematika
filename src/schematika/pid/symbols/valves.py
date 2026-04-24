"""ISO 14617 valve symbol factories.

Valve symbols use a bowtie (two triangles meeting at tips) as the base shape.
Size: ~15mm x 15mm (VALVE_SIZE from constants).
"""

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
    PID_ACTUATOR_STEM_HEIGHT,
    PID_ACTUATOR_TRI_HEIGHT,
    PID_STUB_LENGTH,
    PID_TEXT_SIZE_TAG,
    PID_VALVE_BALL_RADIUS,
    PID_VALVE_CENTER_RADIUS,
    VALVE_SIZE,
)
from schematika.pid.styles import BODY_STYLE, FILL_STYLE, PIPE_STYLE

# Half-size for triangle geometry
_H = VALVE_SIZE / 2  # 5mm


def _bowtie_polygons(fill_left: bool = False, fill_right: bool = False):
    """Return the two triangle polygons forming a bowtie valve body."""
    # Left triangle: tip at center (0,0), base at left edge x=-H
    left_tri = Polygon(
        points=[
            Point(-_H, -_H),
            Point(-_H, _H),
            Point(0.0, 0.0),
        ],
        style=FILL_STYLE if fill_left else BODY_STYLE,
    )
    # Right triangle: tip at center (0,0), base at right edge x=+H
    right_tri = Polygon(
        points=[
            Point(_H, -_H),
            Point(_H, _H),
            Point(0.0, 0.0),
        ],
        style=FILL_STYLE if fill_right else BODY_STYLE,
    )
    return left_tri, right_tri


def _valve_ports():
    """Standard inlet/outlet ports for a horizontal valve."""
    return {
        "in": Port("in", Point(-_H - PID_STUB_LENGTH, 0.0), Vector(-1, 0)),
        "out": Port("out", Point(_H + PID_STUB_LENGTH, 0.0), Vector(1, 0)),
    }


def _pipe_stubs():
    """Pipe stubs connecting external ports to valve body edges."""
    left_stub = Line(Point(-_H - PID_STUB_LENGTH, 0.0), Point(-_H, 0.0), PIPE_STYLE)
    right_stub = Line(Point(_H, 0.0), Point(_H + PID_STUB_LENGTH, 0.0), PIPE_STYLE)
    return left_stub, right_stub


def _label_text(label: str, y_offset: float = _H + PID_STUB_LENGTH):
    return create_label_text(label, Point(0.0, y_offset), PID_TEXT_SIZE_TAG)


def gate_valve(label: str = "") -> Symbol:
    """ISO 14617 gate valve.

    Two triangles meeting at their tips (bowtie), open fill.

    Args:
        label: Component label/tag.

    Returns:
        Symbol with ports 'in' (left) and 'out' (right).
    """
    left_tri, right_tri = _bowtie_polygons()
    left_stub, right_stub = _pipe_stubs()

    elements = [left_tri, right_tri, left_stub, right_stub]
    if label:
        elements.append(_label_text(label))

    return Symbol(elements, _valve_ports(), label=label)


def globe_valve(label: str = "") -> Symbol:
    """ISO 14617 globe valve.

    Bowtie shape with a small circle at the center junction.

    Args:
        label: Component label/tag.

    Returns:
        Symbol with ports 'in' (left) and 'out' (right).
    """
    left_tri, right_tri = _bowtie_polygons()
    left_stub, right_stub = _pipe_stubs()

    center_circle = Circle(
        center=Point(0.0, 0.0),
        radius=PID_VALVE_CENTER_RADIUS,
        style=BODY_STYLE,
    )

    elements = [left_tri, right_tri, left_stub, right_stub, center_circle]
    if label:
        elements.append(_label_text(label))

    return Symbol(elements, _valve_ports(), label=label)


def control_valve(label: str = "") -> Symbol:
    """ISO 14617 control valve.

    Globe valve (bowtie + center circle) with a vertical actuator stem
    and a small triangle actuator symbol on top.

    Args:
        label: Component label/tag.

    Returns:
        Symbol with ports 'in' (left) and 'out' (right).
    """
    left_tri, right_tri = _bowtie_polygons()
    left_stub, right_stub = _pipe_stubs()

    center_circle = Circle(
        center=Point(0.0, 0.0), radius=PID_VALVE_CENTER_RADIUS, style=BODY_STYLE
    )

    # Actuator stem going up
    stem_top_y = -_H - PID_ACTUATOR_STEM_HEIGHT
    stem = Line(Point(0.0, 0.0), Point(0.0, stem_top_y), BODY_STYLE)

    # Actuator symbol: small inverted triangle at top of stem
    act_h = PID_ACTUATOR_TRI_HEIGHT
    actuator = Polygon(
        points=[
            Point(-act_h, stem_top_y - act_h),
            Point(act_h, stem_top_y - act_h),
            Point(0.0, stem_top_y),
        ],
        style=BODY_STYLE,
    )

    elements = [
        left_tri,
        right_tri,
        left_stub,
        right_stub,
        center_circle,
        stem,
        actuator,
    ]
    if label:
        elements.append(_label_text(label, y_offset=_H + PID_STUB_LENGTH))

    ports = _valve_ports()
    ports["actuator"] = Port(
        "actuator",
        Point(0.0, stem_top_y - act_h),
        Vector(0, -1),
    )

    return Symbol(elements, ports, label=label)


def check_valve(label: str = "") -> Symbol:
    """ISO 14617 check valve.

    Single triangle pointing in the flow direction (right), with a perpendicular
    seat bar at the tip.

    Args:
        label: Component label/tag.

    Returns:
        Symbol with ports 'in' (left) and 'out' (right).
    """
    # Triangle pointing right
    triangle = Polygon(
        points=[
            Point(-_H, -_H),
            Point(-_H, _H),
            Point(_H, 0.0),
        ],
        style=BODY_STYLE,
    )

    # Seat: vertical line at right tip
    seat = Line(Point(_H, -_H), Point(_H, _H), BODY_STYLE)

    left_stub, right_stub = _pipe_stubs()

    elements = [triangle, seat, left_stub, right_stub]
    if label:
        elements.append(_label_text(label))

    return Symbol(elements, _valve_ports(), label=label)


def ball_valve(label: str = "") -> Symbol:
    """ISO 14617 ball valve.

    Bowtie with a filled circle at the center (ball indicator).

    Args:
        label: Component label/tag.

    Returns:
        Symbol with ports 'in' (left) and 'out' (right).
    """
    left_tri, right_tri = _bowtie_polygons()
    left_stub, right_stub = _pipe_stubs()

    ball = Circle(
        center=Point(0.0, 0.0),
        radius=PID_VALVE_BALL_RADIUS,
        style=FILL_STYLE,
    )

    elements = [left_tri, right_tri, left_stub, right_stub, ball]
    if label:
        elements.append(_label_text(label))

    return Symbol(elements, _valve_ports(), label=label)


def three_way_valve(label: str = "") -> Symbol:
    """ISO 14617 three-way valve.

    T-junction valve: bowtie on horizontal axis plus a branch port going downward.

    Args:
        label: Component label/tag.

    Returns:
        Symbol with ports 'in' (left), 'out_a' (right), 'out_b' (bottom).
    """
    left_tri, right_tri = _bowtie_polygons()
    left_stub, right_stub = _pipe_stubs()

    # Branch stub going downward
    branch_stub = Line(Point(0.0, 0.0), Point(0.0, _H + PID_STUB_LENGTH), PIPE_STYLE)

    center_circle = Circle(
        center=Point(0.0, 0.0), radius=PID_VALVE_CENTER_RADIUS, style=BODY_STYLE
    )

    elements = [left_tri, right_tri, left_stub, right_stub, branch_stub, center_circle]
    if label:
        elements.append(_label_text(label))

    ports = {
        "in": Port("in", Point(-_H - PID_STUB_LENGTH, 0.0), Vector(-1, 0)),
        "out_a": Port("out_a", Point(_H + PID_STUB_LENGTH, 0.0), Vector(1, 0)),
        "out_b": Port("out_b", Point(0.0, _H + PID_STUB_LENGTH), Vector(0, 1)),
    }

    return Symbol(elements, ports, label=label)
