"""Geometry tests for PID symbol factories.

Each canonical instance is asserted against:
- exact port positions (Point) and directions (Vector)
- exact element counts by primitive type (Line / Circle / Polygon / Text)
- exact coordinates of at least one element to catch arithmetic mutations
"""

import pytest

from schematika.core.geometry import Point
from schematika.core.primitives import Circle, Line, Polygon, Text
from schematika.core.symbol import Symbol
from schematika.pid.constants import (
    INSTRUMENT_BUBBLE_RADIUS,
    PID_ACTUATOR_STEM_HEIGHT,
    PID_ACTUATOR_TRI_HEIGHT,
    PID_CAP_HALF_HEIGHT,
    PID_DEFAULT_PIPE_LENGTH,
    PID_HX_RADIUS,
    PID_PUMP_RADIUS,
    PID_REDUCER_INLET_HALF_H,
    PID_REDUCER_LENGTH,
    PID_REDUCER_OUTLET_HALF_H,
    PID_STUB_LENGTH,
    PID_TANK_HALF_HEIGHT,
    PID_TANK_HALF_WIDTH,
    PID_TEE_BRANCH_LENGTH,
    PID_TEE_HALF_LENGTH,
    PID_VALVE_BALL_RADIUS,
    PID_VALVE_CENTER_RADIUS,
    VALVE_SIZE,
)
from schematika.pid.symbols import (
    ball_valve,
    centrifugal_pump,
    check_valve,
    control_valve,
    gate_valve,
    globe_valve,
    heat_exchanger,
    instrument_bubble,
    pipe_cap,
    pipe_reducer,
    pipe_segment,
    pipe_tee,
    positive_displacement_pump,
    tank,
    three_way_valve,
)

_R = INSTRUMENT_BUBBLE_RADIUS  # 6mm
_VH = VALVE_SIZE / 2  # 5mm
_STUB = PID_STUB_LENGTH  # 5mm


def _by_type(sym: Symbol, cls):
    return [e for e in sym.elements if isinstance(e, cls)]


def _count(sym: Symbol, cls) -> int:
    return len(_by_type(sym, cls))


# ----------------------------------------------------------------------------
# Port positions and directions across every PID factory.
# ----------------------------------------------------------------------------

PORT_CASES: list[tuple[str, Symbol, dict[str, tuple[float, float, float, float]]]] = [
    (
        "instrument_bubble_field",
        instrument_bubble(letters="TT"),
        {
            "process": (0.0, _R + _STUB, 0.0, 1.0),
            "signal_out": (0.0, -_R - _STUB, 0.0, -1.0),
        },
    ),
    (
        "instrument_bubble_panel",
        instrument_bubble(letters="FIC", location="panel"),
        {
            "process": (0.0, _R + _STUB, 0.0, 1.0),
            "signal_out": (0.0, -_R - _STUB, 0.0, -1.0),
        },
    ),
    (
        "instrument_bubble_dcs_with_tag",
        instrument_bubble(letters="TT", location="dcs", tag_number="101"),
        {
            "process": (0.0, _R + _STUB, 0.0, 1.0),
            "signal_out": (0.0, -_R - _STUB, 0.0, -1.0),
        },
    ),
    (
        "pipe_segment_default",
        pipe_segment(),
        {
            "in": (-PID_DEFAULT_PIPE_LENGTH / 2, 0.0, -1.0, 0.0),
            "out": (PID_DEFAULT_PIPE_LENGTH / 2, 0.0, 1.0, 0.0),
        },
    ),
    (
        "pipe_tee",
        pipe_tee(),
        {
            "in": (-PID_TEE_HALF_LENGTH, 0.0, -1.0, 0.0),
            "out": (PID_TEE_HALF_LENGTH, 0.0, 1.0, 0.0),
            "branch": (0.0, PID_TEE_BRANCH_LENGTH, 0.0, 1.0),
        },
    ),
    (
        "pipe_reducer",
        pipe_reducer(),
        {
            "in": (-PID_REDUCER_LENGTH - _STUB, 0.0, -1.0, 0.0),
            "out": (PID_REDUCER_LENGTH + _STUB, 0.0, 1.0, 0.0),
        },
    ),
    (
        "pipe_cap",
        pipe_cap(),
        {"in": (-_STUB, 0.0, -1.0, 0.0)},
    ),
    (
        "centrifugal_pump",
        centrifugal_pump(),
        {
            "inlet": (-PID_PUMP_RADIUS - _STUB, 0.0, -1.0, 0.0),
            "outlet": (PID_PUMP_RADIUS + _STUB, 0.0, 1.0, 0.0),
        },
    ),
    (
        "positive_displacement_pump",
        positive_displacement_pump(),
        {
            "inlet": (-PID_PUMP_RADIUS - _STUB, 0.0, -1.0, 0.0),
            "outlet": (PID_PUMP_RADIUS + _STUB, 0.0, 1.0, 0.0),
        },
    ),
    (
        "gate_valve",
        gate_valve(),
        {
            "in": (-_VH - _STUB, 0.0, -1.0, 0.0),
            "out": (_VH + _STUB, 0.0, 1.0, 0.0),
        },
    ),
    (
        "globe_valve",
        globe_valve(),
        {
            "in": (-_VH - _STUB, 0.0, -1.0, 0.0),
            "out": (_VH + _STUB, 0.0, 1.0, 0.0),
        },
    ),
    (
        "ball_valve",
        ball_valve(),
        {
            "in": (-_VH - _STUB, 0.0, -1.0, 0.0),
            "out": (_VH + _STUB, 0.0, 1.0, 0.0),
        },
    ),
    (
        "check_valve",
        check_valve(),
        {
            "in": (-_VH - _STUB, 0.0, -1.0, 0.0),
            "out": (_VH + _STUB, 0.0, 1.0, 0.0),
        },
    ),
    (
        "control_valve",
        control_valve(),
        {
            "in": (-_VH - _STUB, 0.0, -1.0, 0.0),
            "out": (_VH + _STUB, 0.0, 1.0, 0.0),
            "actuator": (
                0.0,
                -_VH - PID_ACTUATOR_STEM_HEIGHT - PID_ACTUATOR_TRI_HEIGHT,
                0.0,
                -1.0,
            ),
        },
    ),
    (
        "three_way_valve",
        three_way_valve(),
        {
            "in": (-_VH - _STUB, 0.0, -1.0, 0.0),
            "out_a": (_VH + _STUB, 0.0, 1.0, 0.0),
            "out_b": (0.0, _VH + _STUB, 0.0, 1.0),
        },
    ),
    (
        "tank",
        tank(),
        {
            "inlet": (
                -PID_TANK_HALF_WIDTH - _STUB,
                -PID_TANK_HALF_HEIGHT + _STUB,
                -1.0,
                0.0,
            ),
            "outlet": (
                PID_TANK_HALF_WIDTH + _STUB,
                PID_TANK_HALF_HEIGHT - _STUB,
                1.0,
                0.0,
            ),
            "drain": (0.0, PID_TANK_HALF_HEIGHT + _STUB, 0.0, 1.0),
            "vent": (0.0, -PID_TANK_HALF_HEIGHT - _STUB, 0.0, -1.0),
        },
    ),
    (
        "heat_exchanger",
        heat_exchanger(),
        {
            "shell_in": (-PID_HX_RADIUS - _STUB, 0.0, -1.0, 0.0),
            "shell_out": (PID_HX_RADIUS + _STUB, 0.0, 1.0, 0.0),
            "tube_in": (0.0, PID_HX_RADIUS + _STUB, 0.0, 1.0),
            "tube_out": (0.0, -PID_HX_RADIUS - _STUB, 0.0, -1.0),
        },
    ),
]


@pytest.mark.parametrize(
    ("name", "sym", "expected"),
    PORT_CASES,
    ids=[c[0] for c in PORT_CASES],
)
def test_port_positions_and_directions(name, sym, expected):
    for pid, (x, y, dx, dy) in expected.items():
        assert pid in sym.ports, f"{name}: missing port {pid!r}"
        port = sym.ports[pid]
        assert port.position.x == pytest.approx(x), f"{name}.{pid}.x"
        assert port.position.y == pytest.approx(y), f"{name}.{pid}.y"
        assert port.direction.dx == pytest.approx(dx), f"{name}.{pid}.dx"
        assert port.direction.dy == pytest.approx(dy), f"{name}.{pid}.dy"


# ----------------------------------------------------------------------------
# Element counts by primitive type.
# ----------------------------------------------------------------------------

# (id, sym, lines, circles, polygons, texts)  # noqa: ERA001
COUNT_CASES = [
    # Field bubble, no tag, with letters: 1 circle + 2 stubs + 1 letter text.
    ("instr_field_letters", instrument_bubble(letters="TT"), 2, 1, 0, 1),
    # Field bubble, no letters, no tag.
    ("instr_field_blank", instrument_bubble(letters=""), 2, 1, 0, 0),
    # Panel: + divider line.
    ("instr_panel", instrument_bubble(letters="TT", location="panel"), 3, 1, 0, 1),
    # DCS with tag: divider + letters + tag → 3 lines (divider+2 stubs), 2 texts.
    (
        "instr_dcs_tagged",
        instrument_bubble(letters="TT", location="dcs", tag_number="101"),
        3,
        1,
        0,
        2,
    ),
    # Field with tag: divider + letters + tag.
    (
        "instr_field_tagged",
        instrument_bubble(letters="TT", tag_number="101"),
        3,
        1,
        0,
        2,
    ),
    # pipe_segment: 1 line.
    ("pipe_segment_no_label", pipe_segment(), 1, 0, 0, 0),
    ("pipe_segment_with_label", pipe_segment(label="L1"), 1, 0, 0, 1),
    # pipe_tee: 2 lines (horizontal + branch).
    ("pipe_tee", pipe_tee(), 2, 0, 0, 0),
    # pipe_reducer: 4 body lines + 2 stubs = 6 lines.
    ("pipe_reducer_no_label", pipe_reducer(), 6, 0, 0, 0),
    ("pipe_reducer_with_label", pipe_reducer(label="R1"), 6, 0, 0, 1),
    # pipe_cap: stub + cap = 2 lines.
    ("pipe_cap", pipe_cap(), 2, 0, 0, 0),
    # Centrifugal pump: 1 circle + 2 stubs + 1 triangle polygon.
    ("centrifugal_pump_no_label", centrifugal_pump(), 2, 1, 1, 0),
    ("centrifugal_pump_with_label", centrifugal_pump(label="P-1"), 2, 1, 1, 1),
    # Positive-displacement pump: same shape as centrifugal.
    ("pd_pump_no_label", positive_displacement_pump(), 2, 1, 1, 0),
    # gate_valve: 2 stubs + 2 polygons (bowtie).
    ("gate_valve_no_label", gate_valve(), 2, 0, 2, 0),
    ("gate_valve_with_label", gate_valve(label="V-1"), 2, 0, 2, 1),
    # globe_valve: gate + center circle.
    ("globe_valve_no_label", globe_valve(), 2, 1, 2, 0),
    # ball_valve: gate + center filled circle.
    ("ball_valve_no_label", ball_valve(), 2, 1, 2, 0),
    # check_valve: 1 polygon (triangle) + 1 seat line + 2 stubs.
    ("check_valve_no_label", check_valve(), 3, 0, 1, 0),
    # control_valve: gate + center circle + stem line + actuator polygon.
    ("control_valve_no_label", control_valve(), 3, 1, 3, 0),
    # three_way_valve: gate + branch stub + center circle.
    ("three_way_valve_no_label", three_way_valve(), 3, 1, 2, 0),
    # tank: 4 body sides + 4 stubs = 8 lines.
    ("tank_open_no_label", tank(), 8, 0, 0, 0),
    ("tank_open_with_label", tank(label="T-1"), 8, 0, 0, 1),
    ("tank_closed_no_label", tank(kind="closed"), 8, 0, 0, 0),
    # heat_exchanger: 1 body circle + 2 shell + 2 tube stubs + 3 internal = 7 lines.
    ("hx_no_label", heat_exchanger(), 7, 1, 0, 0),
    ("hx_with_label", heat_exchanger(label="HX-1"), 7, 1, 0, 1),
]


@pytest.mark.parametrize(
    ("name", "sym", "n_line", "n_circle", "n_polygon", "n_text"),
    COUNT_CASES,
    ids=[c[0] for c in COUNT_CASES],
)
def test_element_counts_by_type(name, sym, n_line, n_circle, n_polygon, n_text):
    assert _count(sym, Line) == n_line, f"{name}: Line count"
    assert _count(sym, Circle) == n_circle, f"{name}: Circle count"
    assert _count(sym, Polygon) == n_polygon, f"{name}: Polygon count"
    assert _count(sym, Text) == n_text, f"{name}: Text count"


# ----------------------------------------------------------------------------
# Exact-coordinate assertions per factory.
# ----------------------------------------------------------------------------


def test_instrument_bubble_circle_geometry():
    sym = instrument_bubble(letters="TT")
    circle = _by_type(sym, Circle)[0]
    assert circle.center == Point(0.0, 0.0)
    assert circle.radius == pytest.approx(_R)


def test_instrument_bubble_stubs():
    sym = instrument_bubble(letters="TT")
    lines = _by_type(sym, Line)
    # No tag/divider, only 2 stubs.
    assert len(lines) == 2
    # Process stub: from (0, R) up to (0, R+stub).
    assert lines[0].start == Point(0.0, _R)
    assert lines[0].end == Point(0.0, _R + _STUB)
    # Signal stub: from (0, -R) down to (0, -R-stub).
    assert lines[1].start == Point(0.0, -_R)
    assert lines[1].end == Point(0.0, -_R - _STUB)


def test_instrument_bubble_dcs_divider_dashed():
    sym = instrument_bubble(letters="TT", location="dcs", tag_number="1")
    lines = _by_type(sym, Line)
    # First line should be the divider (dashed).
    divider = lines[0]
    assert divider.start == Point(-_R, 0.0)
    assert divider.end == Point(_R, 0.0)
    assert divider.style.stroke_dasharray is not None


def test_instrument_bubble_panel_divider_solid():
    sym = instrument_bubble(letters="TT", location="panel")
    lines = _by_type(sym, Line)
    divider = lines[0]
    assert divider.start == Point(-_R, 0.0)
    assert divider.end == Point(_R, 0.0)
    assert divider.style.stroke_dasharray is None


def test_pipe_segment_default_length():
    sym = pipe_segment()
    line = _by_type(sym, Line)[0]
    half = PID_DEFAULT_PIPE_LENGTH / 2
    assert line.start == Point(-half, 0.0)
    assert line.end == Point(half, 0.0)


@pytest.mark.parametrize("length", [10.0, 25.0, 100.0])
def test_pipe_segment_custom_length(length):
    sym = pipe_segment(length=length)
    line = _by_type(sym, Line)[0]
    half = length / 2
    assert line.start == Point(-half, 0.0)
    assert line.end == Point(half, 0.0)
    assert sym.ports["in"].position == Point(-half, 0.0)
    assert sym.ports["out"].position == Point(half, 0.0)


def test_pipe_tee_horizontal_line_endpoints():
    sym = pipe_tee()
    lines = _by_type(sym, Line)
    horizontal = lines[0]
    assert horizontal.start == Point(-PID_TEE_HALF_LENGTH, 0.0)
    assert horizontal.end == Point(PID_TEE_HALF_LENGTH, 0.0)
    branch = lines[1]
    assert branch.start == Point(0.0, 0.0)
    assert branch.end == Point(0.0, PID_TEE_BRANCH_LENGTH)


def test_pipe_reducer_outline_endpoints():
    sym = pipe_reducer()
    lines = _by_type(sym, Line)
    h_in = PID_REDUCER_INLET_HALF_H
    h_out = PID_REDUCER_OUTLET_HALF_H
    length = PID_REDUCER_LENGTH
    # Body lines (top, bottom, left cap, right cap), then 2 stubs.
    assert lines[0].start == Point(-length, -h_in)
    assert lines[0].end == Point(length, -h_out)
    assert lines[1].start == Point(-length, h_in)
    assert lines[1].end == Point(length, h_out)
    assert lines[2].start == Point(-length, -h_in)
    assert lines[2].end == Point(-length, h_in)
    assert lines[3].start == Point(length, -h_out)
    assert lines[3].end == Point(length, h_out)


def test_pipe_cap_geometry():
    sym = pipe_cap()
    lines = _by_type(sym, Line)
    h = PID_CAP_HALF_HEIGHT
    # Stub: from (-stub, 0) to origin.
    assert lines[0].start == Point(-_STUB, 0.0)
    assert lines[0].end == Point(0.0, 0.0)
    # Cap: vertical bar at origin.
    assert lines[1].start == Point(0.0, -h)
    assert lines[1].end == Point(0.0, h)


def test_centrifugal_pump_circle():
    sym = centrifugal_pump()
    circle = _by_type(sym, Circle)[0]
    assert circle.center == Point(0.0, 0.0)
    assert circle.radius == pytest.approx(PID_PUMP_RADIUS)


def test_centrifugal_pump_triangle_geometry():
    sym = centrifugal_pump()
    tri = _by_type(sym, Polygon)[0]
    s = _STUB
    assert tri.points == [
        Point(-s * 0.5, -s * 0.5),
        Point(-s * 0.5, s * 0.5),
        Point(s * 0.5, 0.0),
    ]


def test_centrifugal_pump_stubs():
    sym = centrifugal_pump()
    lines = _by_type(sym, Line)
    inlet = lines[0]
    assert inlet.start == Point(-PID_PUMP_RADIUS - _STUB, 0.0)
    assert inlet.end == Point(-PID_PUMP_RADIUS, 0.0)
    outlet = lines[1]
    assert outlet.start == Point(PID_PUMP_RADIUS, 0.0)
    assert outlet.end == Point(PID_PUMP_RADIUS + _STUB, 0.0)


def test_gate_valve_bowtie_polygons():
    sym = gate_valve()
    polys = _by_type(sym, Polygon)
    left, right = polys
    assert left.points == [Point(-_VH, -_VH), Point(-_VH, _VH), Point(0.0, 0.0)]
    assert right.points == [Point(_VH, -_VH), Point(_VH, _VH), Point(0.0, 0.0)]


def test_globe_valve_center_circle():
    sym = globe_valve()
    circle = _by_type(sym, Circle)[0]
    assert circle.center == Point(0.0, 0.0)
    assert circle.radius == pytest.approx(PID_VALVE_CENTER_RADIUS)


def test_ball_valve_filled_center():
    sym = ball_valve()
    circle = _by_type(sym, Circle)[0]
    assert circle.radius == pytest.approx(PID_VALVE_BALL_RADIUS)
    # Ball valve uses FILL_STYLE → fill is black.
    assert circle.style.fill == "black"


def test_check_valve_triangle_points_right():
    sym = check_valve()
    tri = _by_type(sym, Polygon)[0]
    # Triangle base on the left, tip at +H.
    assert tri.points == [Point(-_VH, -_VH), Point(-_VH, _VH), Point(_VH, 0.0)]


def test_check_valve_seat_line():
    sym = check_valve()
    # Seat is the second line (after the triangle).
    lines = _by_type(sym, Line)
    seat = lines[
        0
    ]  # triangle, then seat as element index 1 — but Line filter strips polys.
    # Actually: elements order: triangle, seat, left_stub, right_stub.
    # So Lines order: seat, left_stub, right_stub.
    assert seat.start == Point(_VH, -_VH)
    assert seat.end == Point(_VH, _VH)


def test_control_valve_actuator_geometry():
    sym = control_valve()
    polys = _by_type(sym, Polygon)
    # 3 polygons: left tri, right tri, actuator triangle.
    actuator = polys[2]
    stem_top_y = -_VH - PID_ACTUATOR_STEM_HEIGHT
    act_h = PID_ACTUATOR_TRI_HEIGHT
    assert actuator.points == [
        Point(-act_h, stem_top_y - act_h),
        Point(act_h, stem_top_y - act_h),
        Point(0.0, stem_top_y),
    ]


def test_control_valve_stem_line():
    sym = control_valve()
    lines = _by_type(sym, Line)
    # lines: left_stub, right_stub, stem.
    stem = lines[2]
    stem_top_y = -_VH - PID_ACTUATOR_STEM_HEIGHT
    assert stem.start == Point(0.0, 0.0)
    assert stem.end == Point(0.0, stem_top_y)


def test_three_way_valve_branch_stub():
    sym = three_way_valve()
    lines = _by_type(sym, Line)
    # lines: left_stub, right_stub, branch_stub.
    branch = lines[2]
    assert branch.start == Point(0.0, 0.0)
    assert branch.end == Point(0.0, _VH + _STUB)


def test_tank_open_top_is_dashed():
    sym = tank()  # default kind="open"
    lines = _by_type(sym, Line)
    # element order: left, right, bottom, top, ...
    top = lines[3]
    assert top.style.stroke_dasharray is not None


def test_tank_closed_top_is_solid():
    sym = tank(kind="closed")
    lines = _by_type(sym, Line)
    top = lines[3]
    assert top.style.stroke_dasharray is None


def test_tank_body_endpoints():
    sym = tank()
    w = PID_TANK_HALF_WIDTH
    h = PID_TANK_HALF_HEIGHT
    lines = _by_type(sym, Line)
    left = lines[0]
    right = lines[1]
    bottom = lines[2]
    top = lines[3]
    assert left.start == Point(-w, -h)
    assert left.end == Point(-w, h)
    assert right.start == Point(w, -h)
    assert right.end == Point(w, h)
    assert bottom.start == Point(-w, h)
    assert bottom.end == Point(w, h)
    assert top.start == Point(-w, -h)
    assert top.end == Point(w, -h)


def test_tank_inlet_stub_geometry():
    sym = tank()
    w = PID_TANK_HALF_WIDTH
    h = PID_TANK_HALF_HEIGHT
    lines = _by_type(sym, Line)
    # element 4 = inlet stub.
    inlet = lines[4]
    assert inlet.start == Point(-w, -h + _STUB)
    assert inlet.end == Point(-w - _STUB, -h + _STUB)


def test_heat_exchanger_body_circle():
    sym = heat_exchanger()
    circle = _by_type(sym, Circle)[0]
    assert circle.center == Point(0.0, 0.0)
    assert circle.radius == pytest.approx(PID_HX_RADIUS)


def test_heat_exchanger_shell_stubs():
    sym = heat_exchanger()
    lines = _by_type(sym, Line)
    r = PID_HX_RADIUS
    # Order: shell_in, shell_out, tube_in, tube_out, inner top, inner bot, return.
    shell_in = lines[0]
    assert shell_in.start == Point(-r - _STUB, 0.0)
    assert shell_in.end == Point(-r, 0.0)
    shell_out = lines[1]
    assert shell_out.start == Point(r, 0.0)
    assert shell_out.end == Point(r + _STUB, 0.0)


# ----------------------------------------------------------------------------
# Style assertions: stroke widths must distinguish process pipes from
# instrument signals from equipment bodies. Style mutations otherwise pass.
# ----------------------------------------------------------------------------


def test_pipe_segment_uses_pipe_stroke_width():
    from schematika.pid.constants import PID_LINE_WEIGHT

    sym = pipe_segment()
    line = _by_type(sym, Line)[0]
    assert line.style.stroke_width == pytest.approx(PID_LINE_WEIGHT)


def test_tank_body_uses_equipment_stroke_width():
    from schematika.pid.constants import PID_EQUIPMENT_STROKE

    sym = tank()
    left = _by_type(sym, Line)[0]
    assert left.style.stroke_width == pytest.approx(PID_EQUIPMENT_STROKE)


def test_instrument_bubble_letter_position_above_center_when_tagged():
    """When a tag number is present, letters move into the upper half."""
    sym = instrument_bubble(letters="TT", tag_number="101")
    # Find the letters Text by content.
    texts = _by_type(sym, Text)
    letter = next(t for t in texts if t.content == "TT")
    tag = next(t for t in texts if t.content == "101")
    # Letters get a negative y (upper half), tag gets positive (lower half).
    assert letter.position.y < 0
    assert tag.position.y > 0


def test_instrument_bubble_letter_centered_when_no_tag():
    sym = instrument_bubble(letters="TT")
    texts = _by_type(sym, Text)
    letter = next(t for t in texts if t.content == "TT")
    assert letter.position == Point(0.0, 0.0)
