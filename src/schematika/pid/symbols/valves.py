"""ISO 14617 valve factories; base shape is a bowtie (VALVE_SIZE square)."""

from schematika.core import (
    Circle,
    Line,
    Point,
    Polygon,
    Port,
    Symbol,
    Vector,
)
from schematika.core.geometry import Element
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


def _bowtie_polygons(
    *, fill_left: bool = False, fill_right: bool = False
) -> tuple[Polygon, Polygon]:
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


def _valve_ports() -> dict[str, Port]:
    """Standard inlet/outlet ports for a horizontal valve."""
    return {
        "in": Port("in", Point(-_H - PID_STUB_LENGTH, 0.0), Vector(-1, 0)),
        "out": Port("out", Point(_H + PID_STUB_LENGTH, 0.0), Vector(1, 0)),
    }


def _pipe_stubs() -> tuple[Line, Line]:
    """Pipe stubs connecting external ports to valve body edges."""
    left_stub = Line(Point(-_H - PID_STUB_LENGTH, 0.0), Point(-_H, 0.0), PIPE_STYLE)
    right_stub = Line(Point(_H, 0.0), Point(_H + PID_STUB_LENGTH, 0.0), PIPE_STYLE)
    return left_stub, right_stub


def _label_text(label: str, y_offset: float = _H + PID_STUB_LENGTH) -> Element:
    return create_label_text(label, Point(0.0, y_offset), PID_TEXT_SIZE_TAG)


def gate_valve(label: str = "") -> Symbol:
    """Gate valve symbol per ISO 14617.

    Bowtie shape (two opposing open triangles, tips touching at center).

    Port IDs:
        ``"in"`` — pipe inlet (left, west).
        ``"out"`` — pipe outlet (right, east).

    Args:
        label: Optional valve tag, e.g. ``"GV-101"``.

    Returns:
        Symbol: Gate valve with two horizontal ports.

    Examples:
        >>> from schematika.pid import gate_valve
        >>> sym = gate_valve("GV-101")
        >>> sorted(sym.ports)
        ['in', 'out']
        >>> sym.label
        'GV-101'
    """
    left_tri, right_tri = _bowtie_polygons()
    left_stub, right_stub = _pipe_stubs()

    elements: list[Element] = [left_tri, right_tri, left_stub, right_stub]
    if label:
        elements.append(_label_text(label))

    return Symbol(elements, _valve_ports(), label=label)


def globe_valve(label: str = "") -> Symbol:
    """Globe valve symbol per ISO 14617.

    Bowtie with a small circle at the center indicating throttling capability.

    Port IDs:
        ``"in"`` — pipe inlet (left, west).
        ``"out"`` — pipe outlet (right, east).

    Args:
        label: Optional valve tag, e.g. ``"GLV-101"``.

    Returns:
        Symbol: Globe valve with two horizontal ports.

    Examples:
        >>> from schematika.pid import globe_valve
        >>> sym = globe_valve("GLV-101")
        >>> sorted(sym.ports)
        ['in', 'out']
        >>> sym.label
        'GLV-101'
    """
    left_tri, right_tri = _bowtie_polygons()
    left_stub, right_stub = _pipe_stubs()

    center_circle = Circle(
        center=Point(0.0, 0.0),
        radius=PID_VALVE_CENTER_RADIUS,
        style=BODY_STYLE,
    )

    elements: list[Element] = [
        left_tri,
        right_tri,
        left_stub,
        right_stub,
        center_circle,
    ]
    if label:
        elements.append(_label_text(label))

    return Symbol(elements, _valve_ports(), label=label)


def control_valve(label: str = "") -> Symbol:
    """Control valve symbol per ISO 14617.

    Globe valve body with an actuator stem and diaphragm triangle above the body.

    Port IDs:
        ``"in"`` — pipe inlet (left, west).
        ``"out"`` — pipe outlet (right, east).
        ``"actuator"`` — actuator signal connection (top, north).

    Args:
        label: Optional valve tag, e.g. ``"CV-101"``.

    Returns:
        Symbol: Control valve with two process ports and one actuator port.

    Examples:
        >>> from schematika.pid import control_valve
        >>> sym = control_valve("CV-101")
        >>> sorted(sym.ports)
        ['actuator', 'in', 'out']
        >>> sym.label
        'CV-101'
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

    elements: list[Element] = [
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
    """Check valve symbol per ISO 14617.

    Triangle pointing in the flow direction with a perpendicular seat bar at the
    downstream tip; flow passes left to right.

    Port IDs:
        ``"in"`` — pipe inlet (left, west).
        ``"out"`` — pipe outlet (right, east).

    Args:
        label: Optional valve tag, e.g. ``"CKV-101"``.

    Returns:
        Symbol: Check valve with two horizontal ports.

    Examples:
        >>> from schematika.pid import check_valve
        >>> sym = check_valve("CKV-101")
        >>> sorted(sym.ports)
        ['in', 'out']
        >>> sym.label
        'CKV-101'
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

    elements: list[Element] = [triangle, seat, left_stub, right_stub]
    if label:
        elements.append(_label_text(label))

    return Symbol(elements, _valve_ports(), label=label)


def ball_valve(label: str = "") -> Symbol:
    """Ball valve symbol per ISO 14617.

    Bowtie with a filled circle at the center indicating the ball element.

    Port IDs:
        ``"in"`` — pipe inlet (left, west).
        ``"out"`` — pipe outlet (right, east).

    Args:
        label: Optional valve tag, e.g. ``"BV-101"``.

    Returns:
        Symbol: Ball valve with two horizontal ports.

    Examples:
        >>> from schematika.pid import ball_valve
        >>> sym = ball_valve("BV-101")
        >>> sorted(sym.ports)
        ['in', 'out']
        >>> sym.label
        'BV-101'
    """
    left_tri, right_tri = _bowtie_polygons()
    left_stub, right_stub = _pipe_stubs()

    ball = Circle(
        center=Point(0.0, 0.0),
        radius=PID_VALVE_BALL_RADIUS,
        style=FILL_STYLE,
    )

    elements: list[Element] = [left_tri, right_tri, left_stub, right_stub, ball]
    if label:
        elements.append(_label_text(label))

    return Symbol(elements, _valve_ports(), label=label)


def three_way_valve(label: str = "") -> Symbol:
    """Three-way valve symbol per ISO 14617.

    Bowtie with a perpendicular downward branch port and a center circle.

    Port IDs:
        ``"in"`` — pipe inlet (left, west).
        ``"out_a"`` — primary outlet (right, east).
        ``"out_b"`` — branch outlet (bottom, south).

    Args:
        label: Optional valve tag, e.g. ``"3WV-101"``.

    Returns:
        Symbol: Three-way valve with one inlet and two outlet ports.

    Examples:
        >>> from schematika.pid import three_way_valve
        >>> sym = three_way_valve("3WV-101")
        >>> sorted(sym.ports)
        ['in', 'out_a', 'out_b']
        >>> sym.label
        '3WV-101'
    """
    left_tri, right_tri = _bowtie_polygons()
    left_stub, right_stub = _pipe_stubs()

    # Branch stub going downward
    branch_stub = Line(Point(0.0, 0.0), Point(0.0, _H + PID_STUB_LENGTH), PIPE_STYLE)

    center_circle = Circle(
        center=Point(0.0, 0.0), radius=PID_VALVE_CENTER_RADIUS, style=BODY_STYLE
    )

    elements: list[Element] = [
        left_tri,
        right_tri,
        left_stub,
        right_stub,
        branch_stub,
        center_circle,
    ]
    if label:
        elements.append(_label_text(label))

    ports = {
        "in": Port("in", Point(-_H - PID_STUB_LENGTH, 0.0), Vector(-1, 0)),
        "out_a": Port("out_a", Point(_H + PID_STUB_LENGTH, 0.0), Vector(1, 0)),
        "out_b": Port("out_b", Point(0.0, _H + PID_STUB_LENGTH), Vector(0, 1)),
    }

    return Symbol(elements, ports, label=label)
