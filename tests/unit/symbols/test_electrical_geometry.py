"""Geometry tests for electrical symbol factories.

Each canonical instance is asserted against:
- exact port positions (Point) and directions (Vector)
- exact element counts by primitive type (Line / Circle / Polygon / Text)
- exact coordinates of at least one element to catch arithmetic mutations

The intent is to kill mutmut survivors that slip past structural-only tests
(port count, label text, "has the right keys").
"""

import math

import pytest

from schematika.core.constants import GRID_SIZE, TERMINAL_RADIUS
from schematika.core.geometry import Point, Vector
from schematika.core.primitives import Circle, Line, Polygon, Text
from schematika.core.symbol import Symbol
from schematika.electrical.symbols import (
    block,
    breaker,
    coil,
    connector_pin,
    contactor,
    ct,
    ct_assembly,
    estop,
    estop_button,
    fuse,
    motor,
    nc_contact,
    no_contact,
    psu,
    ref,
    spdt_contact,
    terminal,
    terminal_box,
    thermal_overload,
    turn_actuator,
    turn_switch,
)
from schematika.electrical.symbols.connector_pins import CONNECTOR_PIN_SIZE


def _by_type(sym: Symbol, cls):
    return [e for e in sym.elements if isinstance(e, cls)]


def _count(sym: Symbol, cls) -> int:
    return len(_by_type(sym, cls))


# ----------------------------------------------------------------------------
# Port positions and directions — one parametric test across all factories.
# ----------------------------------------------------------------------------

# Each entry: (id, factory_call, expected_ports)
#   expected_ports: dict[port_id, (x, y, dx, dy)]  # noqa: ERA001

_GRID = GRID_SIZE  # 5.0
_HALF = GRID_SIZE / 2  # 2.5


PORT_CASES: list[tuple[str, Symbol, dict[str, tuple[float, float, float, float]]]] = [
    (
        "no_contact",
        no_contact(),
        {
            "13": (0.0, -_GRID, 0.0, -1.0),
            "14": (0.0, _GRID, 0.0, 1.0),
        },
    ),
    (
        "nc_contact",
        nc_contact(),
        {
            "11": (0.0, -_GRID, 0.0, -1.0),
            "12": (0.0, _GRID, 0.0, 1.0),
        },
    ),
    (
        "spdt_contact",
        spdt_contact(),
        {
            "11": (_HALF, _GRID, 0.0, 1.0),
            "12": (-_HALF, -_GRID, 0.0, -1.0),
            "14": (_HALF, -_GRID, 0.0, -1.0),
        },
    ),
    (
        "spdt_contact_inverted",
        spdt_contact(inverted=True),
        {
            "11": (_HALF, -_GRID, 0.0, -1.0),
            "12": (-_HALF, _GRID, 0.0, 1.0),
            "14": (_HALF, _GRID, 0.0, 1.0),
        },
    ),
    (
        "breaker",
        breaker(),
        {
            "1": (0.0, -_GRID, 0.0, -1.0),
            "2": (0.0, _GRID, 0.0, 1.0),
        },
    ),
    (
        "thermal_overload",
        thermal_overload(),
        {
            "1": (0.0, -_GRID, 0.0, -1.0),
            "2": (0.0, _GRID, 0.0, 1.0),
        },
    ),
    (
        "fuse",
        fuse(),
        {
            "1": (0.0, -1.25 * _GRID, 0.0, -1.0),
            "2": (0.0, 1.25 * _GRID, 0.0, 1.0),
        },
    ),
    (
        "coil",
        coil(),
        {
            "A1": (0.0, -_GRID, 0.0, -1.0),
            "A2": (0.0, _GRID, 0.0, 1.0),
        },
    ),
    (
        "motor_1p",
        motor(poles=1),
        {
            # radius = 1.5*GRID_SIZE = 7.5, terminal_length = GRID_SIZE = 5.0
            "1": (0.0, -12.5, 0.0, -1.0),
            "2": (0.0, 12.5, 0.0, 1.0),
        },
    ),
    (
        "ref_up",
        ref(label="X"),
        {"2": (0.0, 10.0, 0.0, 1.0)},
    ),
    (
        "ref_down",
        ref(label="X", direction="down"),
        {"1": (0.0, -10.0, 0.0, -1.0)},
    ),
    (
        "connector_pin",
        connector_pin(),
        {"1": (0.0, CONNECTOR_PIN_SIZE / 2, 0.0, 1.0)},
    ),
    (
        "terminal_single",
        terminal(),
        {
            "1": (0.0, 0.0, 0.0, -1.0),
            "2": (0.0, 0.0, 0.0, 1.0),
            "top": (0.0, 0.0, 0.0, -1.0),
            "bottom": (0.0, 0.0, 0.0, 1.0),
        },
    ),
]


@pytest.mark.parametrize(
    ("name", "sym", "expected"),
    PORT_CASES,
    ids=[c[0] for c in PORT_CASES],
)
def test_port_positions_and_directions(name, sym, expected):
    """Every listed port must exist with the exact (x,y,dx,dy) tuple."""
    for pid, (x, y, dx, dy) in expected.items():
        assert pid in sym.ports, f"{name}: missing port {pid!r}"
        port = sym.ports[pid]
        assert port.position.x == pytest.approx(x), f"{name}.{pid}.x"
        assert port.position.y == pytest.approx(y), f"{name}.{pid}.y"
        assert port.direction.dx == pytest.approx(dx), f"{name}.{pid}.dx"
        assert port.direction.dy == pytest.approx(dy), f"{name}.{pid}.dy"


# ----------------------------------------------------------------------------
# Three-phase motor: more interesting geometry (radius-derived port positions).
# ----------------------------------------------------------------------------


def test_motor_3p_port_geometry():
    sym = motor(poles=3)
    pin_spacing = 10.0  # DEFAULT_POLE_SPACING = 2 * GRID_SIZE
    radius = 2 * pin_spacing  # 20mm
    terminal_length = pin_spacing  # 10mm
    # U at -pin_spacing (left), V at 0 (top of circle), W at +pin_spacing.
    expected = {
        "U": (
            -pin_spacing,
            -math.sqrt(radius**2 - pin_spacing**2) - terminal_length,
            0.0,
            -1.0,
        ),
        "V": (0.0, -radius - terminal_length, 0.0, -1.0),
        "W": (
            pin_spacing,
            -math.sqrt(radius**2 - pin_spacing**2) - terminal_length,
            0.0,
            -1.0,
        ),
        "PE": (radius, -terminal_length, 0.0, -1.0),
    }
    for pid, (x, y, dx, dy) in expected.items():
        assert pid in sym.ports
        p = sym.ports[pid]
        assert p.position.x == pytest.approx(x)
        assert p.position.y == pytest.approx(y)
        assert p.direction.dx == pytest.approx(dx)
        assert p.direction.dy == pytest.approx(dy)


# ----------------------------------------------------------------------------
# Element counts by primitive type — kills mutations that swap one shape for
# another, drop a line, or duplicate a label.
# ----------------------------------------------------------------------------

# (id, sym, lines, circles, polygons, texts)  # noqa: ERA001
COUNT_CASES = [
    # no_contact: 2 leads + 1 blade = 3 lines, 2 pin labels = 2 texts.
    ("no_contact_no_label", no_contact(), 3, 0, 0, 2),
    # +1 standard_text label.
    ("no_contact_with_label", no_contact(label="K1"), 3, 0, 0, 3),
    # nc_contact: 2 leads + 1 seat + 1 blade = 4 lines, 2 pin labels.
    ("nc_contact_no_label", nc_contact(), 4, 0, 0, 2),
    ("nc_contact_with_label", nc_contact(label="K1"), 4, 0, 0, 3),
    # spdt: 3 leads + 1 seat + 1 blade = 5 lines, 3 pin labels.
    ("spdt_contact_no_label", spdt_contact(), 5, 0, 0, 3),
    ("spdt_contact_with_label", spdt_contact(label="K1"), 5, 0, 0, 4),
    # breaker: 2 leads + 1 blade + 2 cross lines = 5 lines, 2 pin labels.
    ("breaker_no_label", breaker(), 5, 0, 0, 2),
    ("breaker_with_label", breaker(label="F1"), 5, 0, 0, 3),
    # thermal_overload: lead-in + 5 segments + lead-out = 7 lines.
    # Public thermal_overload() with poles=1 generates pins=("1","2") → 2 pin labels.
    ("thermal_overload_no_label", thermal_overload(), 7, 0, 0, 2),
    ("thermal_overload_with_label", thermal_overload(label="F1"), 7, 0, 0, 3),
    # fuse: 1 box (Polygon) + 1 internal line + 0 pin labels (empty default).
    ("fuse_no_label", fuse(), 1, 0, 1, 0),
    ("fuse_with_label", fuse(label="F1"), 1, 0, 1, 1),
    # coil: 1 box + 2 leads + 2 pin labels.
    ("coil_no_label", coil(), 2, 0, 1, 2),
    ("coil_with_label", coil(label="K1"), 2, 0, 1, 3),
    # coil with terminals hidden.
    ("coil_no_terminals", coil(show_terminals=False), 0, 0, 1, 0),
    # motor 1p: 1 circle + 1 "M" text + 2 leads + 2 pin labels.
    ("motor_1p_no_label", motor(poles=1), 2, 1, 0, 3),
    ("motor_1p_with_label", motor(poles=1, label="M1"), 2, 1, 0, 4),
    # motor 3p: 1 circle + 4 leads (U,V,W,PE) + 4 pin labels.
    ("motor_3p_no_label", motor(poles=3), 4, 1, 0, 4),
    # +1 main label inside circle.
    ("motor_3p_with_label", motor(poles=3, label="M1"), 4, 1, 0, 5),
    # ref up: 1 line + 1 polygon (head) + 1 text label.
    ("ref_up", ref(label="A1"), 1, 0, 1, 1),
    ("ref_down", ref(label="A1", direction="down"), 1, 0, 1, 1),
    # connector_pin: 1 box (Polygon).
    ("connector_pin_no_label", connector_pin(), 0, 0, 1, 0),
    ("connector_pin_with_label", connector_pin(label="J1"), 0, 0, 1, 1),
    # terminal_single: 1 circle (terminal_circle), 0 lines.
    ("terminal_single_no_label", terminal(), 0, 1, 0, 0),
    ("terminal_single_with_label", terminal(label="X1"), 0, 1, 0, 1),
    ("terminal_single_with_pin", terminal(pins=("1",)), 0, 1, 0, 1),
    # ct: 1 circle + 1 line.
    ("ct", ct(), 1, 1, 0, 0),
    # estop_button: 1 polygon (semicircle).
    ("estop_button", estop_button(), 0, 0, 1, 0),
    # turn_actuator: 3 lines.
    ("turn_actuator", turn_actuator(), 3, 0, 0, 0),
    # terminal_box (1 pin default): 1 polygon (rect) + 1 line + 1 text.
    ("terminal_box_default", terminal_box(), 1, 0, 1, 1),
    # 3 pins: 1 polygon + 3 pin lines + 3 pin texts.
    ("terminal_box_3pin", terminal_box(num_pins=3), 3, 0, 1, 3),
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
# Exact-coordinate assertions per factory — kill arithmetic mutations.
# ----------------------------------------------------------------------------


def test_no_contact_blade_endpoints():
    sym = no_contact()
    blade = _by_type(sym, Line)[2]  # third line is the blade
    assert blade.start == Point(0.0, _HALF)
    assert blade.end == Point(-_HALF, -_HALF)


def test_no_contact_lead_endpoints():
    sym = no_contact()
    lines = _by_type(sym, Line)
    assert lines[0].start == Point(0.0, -_GRID)
    assert lines[0].end == Point(0.0, -_HALF)
    assert lines[1].start == Point(0.0, _HALF)
    assert lines[1].end == Point(0.0, _GRID)


def test_nc_contact_seat_coordinates():
    sym = nc_contact()
    # leads, seat, blade order in source.
    seat = _by_type(sym, Line)[2]
    assert seat.start == Point(0.0, -_HALF)
    assert seat.end == Point(_HALF, -_HALF)


def test_spdt_blade_target_is_top_center():
    sym = spdt_contact()
    # element order: l_com, l_no, l_nc, seat_nc, blade.
    blade = _by_type(sym, Line)[4]
    assert blade.start == Point(_HALF, _HALF)
    # Blade extended past target Point(0, -_HALF). Just check direction sign.
    # End must be on the line through start and target, beyond target.
    assert blade.end.x < 0.0
    assert blade.end.y < -_HALF


def test_breaker_cross_geometry():
    sym = breaker()
    lines = _by_type(sym, Line)
    # cross_line_1: bottom-left to top-right around point (0, -_HALF).
    cross1 = lines[3]
    cross2 = lines[4]
    half_cross = GRID_SIZE / 4  # cross_size/2 = 1.25
    assert cross1.start == Point(-half_cross, -_HALF - half_cross)
    assert cross1.end == Point(half_cross, -_HALF + half_cross)
    assert cross2.start == Point(-half_cross, -_HALF + half_cross)
    assert cross2.end == Point(half_cross, -_HALF - half_cross)


def test_thermal_overload_pulse_path():
    sym = thermal_overload()
    lines = _by_type(sym, Line)
    # Lead-in goes from (0, -_GRID) to (0, -1.5*_HALF).
    hg = _HALF
    y_start = -1.5 * hg
    assert lines[0].start == Point(0.0, -_GRID)
    assert lines[0].end == Point(0.0, y_start)
    # First pulse step: down by hg.
    assert lines[1].start == Point(0.0, y_start)
    assert lines[1].end == Point(0.0, y_start + hg)
    # Pulse step left.
    assert lines[2].start == Point(0.0, y_start + hg)
    assert lines[2].end == Point(-hg, y_start + hg)


def test_fuse_box_dimensions():
    sym = fuse()
    polygons = _by_type(sym, Polygon)
    assert len(polygons) == 1
    # box(center=(0,0), w=GRID, h=2.5*GRID) → corners.
    pts = {(p.x, p.y) for p in polygons[0].points}
    assert pts == {
        (-0.5 * _GRID, -1.25 * _GRID),
        (0.5 * _GRID, -1.25 * _GRID),
        (0.5 * _GRID, 1.25 * _GRID),
        (-0.5 * _GRID, 1.25 * _GRID),
    }


def test_fuse_internal_line():
    sym = fuse()
    line = _by_type(sym, Line)[0]
    assert line.start == Point(0.0, -1.25 * _GRID)
    assert line.end == Point(0.0, 1.25 * _GRID)


def test_fuse_explicit_pin_numbers_visible():
    """Callers can still pass explicit pin numbers; they appear as Text elements."""
    sym = fuse(pins=("1", "2"))
    texts = _by_type(sym, Text)
    contents = {t.content for t in texts}
    assert "1" in contents
    assert "2" in contents


def test_coil_box_dimensions():
    sym = coil()
    poly = _by_type(sym, Polygon)[0]
    pts = {(p.x, p.y) for p in poly.points}
    # width=2*GRID, height=GRID, centered at (0,0).
    assert pts == {
        (-_GRID, -_HALF),
        (_GRID, -_HALF),
        (_GRID, _HALF),
        (-_GRID, _HALF),
    }


def test_coil_lead_lengths():
    sym = coil()
    lines = _by_type(sym, Line)
    # GRID_SUBDIVISION = GRID/2 = 2.5 lead length.
    assert lines[0].start == Point(0.0, -_HALF)
    assert lines[0].end == Point(0.0, -_GRID)
    assert lines[1].start == Point(0.0, _HALF)
    assert lines[1].end == Point(0.0, _GRID)


def test_motor_1p_circle_radius():
    sym = motor(poles=1)
    circle = _by_type(sym, Circle)[0]
    assert circle.center == Point(0.0, 0.0)
    assert circle.radius == pytest.approx(1.5 * _GRID)  # 7.5mm


def test_motor_3p_circle_radius():
    sym = motor(poles=3)
    circle = _by_type(sym, Circle)[0]
    assert circle.center == Point(0.0, 0.0)
    # radius = 2 * DEFAULT_POLE_SPACING = 2 * 10mm = 20mm.
    assert circle.radius == pytest.approx(20.0)


def test_motor_3p_v_terminal_y_at_top_of_circle():
    sym = motor(poles=3)
    # V port sits at top of circle (-radius) minus terminal_length (=pin_spacing=10mm).
    p = sym.ports["V"]
    assert p.position == Point(0.0, -30.0)


def test_ref_up_arrowhead_geometry():
    sym = ref(label="X")
    poly = _by_type(sym, Polygon)[0]
    # Up arrow: tip at origin, head base above tip.
    pts = poly.points
    assert pts[1] == Point(0.0, 0.0)  # tip
    head_base_y = 3.0  # REF_ARROW_HEAD_LENGTH = 3mm
    head_w_half = 1.25  # REF_ARROW_HEAD_WIDTH/2
    assert pts[0] == Point(-head_w_half, head_base_y)
    assert pts[2] == Point(head_w_half, head_base_y)


def test_ref_down_arrowhead_geometry():
    sym = ref(label="X", direction="down")
    poly = _by_type(sym, Polygon)[0]
    pts = poly.points
    assert pts[1] == Point(0.0, 0.0)
    head_base_y = -3.0
    head_w_half = 1.25
    assert pts[0] == Point(-head_w_half, head_base_y)
    assert pts[2] == Point(head_w_half, head_base_y)


def test_ref_invalid_direction_raises():
    from schematika.core.exceptions import CircuitValidationError

    with pytest.raises(CircuitValidationError, match="direction"):
        ref(direction="left")


def test_ct_dimensions():
    sym = ct()
    circle = _by_type(sym, Circle)[0]
    assert circle.center == Point(0.0, 0.0)
    assert circle.radius == pytest.approx(_HALF)  # 2.5mm
    line = _by_type(sym, Line)[0]
    # Line from left edge to left, length GRID_SIZE.
    assert line.start == Point(-_HALF, 0.0)
    assert line.end == Point(-_HALF - _GRID, 0.0)


def test_connector_pin_box_size():
    sym = connector_pin()
    poly = _by_type(sym, Polygon)[0]
    half = CONNECTOR_PIN_SIZE / 2  # 5mm
    pts = {(p.x, p.y) for p in poly.points}
    assert pts == {(-half, -half), (half, -half), (half, half), (-half, half)}


def test_connector_pin_size_constant():
    assert pytest.approx(2 * GRID_SIZE) == CONNECTOR_PIN_SIZE
    # Sanity: bigger than terminal diameter so the visual is distinguishable.
    assert CONNECTOR_PIN_SIZE > 2 * TERMINAL_RADIUS


def test_terminal_single_circle_at_origin():
    sym = terminal()
    circle = _by_type(sym, Circle)[0]
    assert circle.center == Point(0.0, 0.0)
    assert circle.radius == pytest.approx(TERMINAL_RADIUS)


def test_terminal_invalid_label_pos_raises():
    from schematika.core.exceptions import CircuitValidationError

    with pytest.raises(CircuitValidationError, match="label_pos"):
        terminal(label_pos="top")


def test_terminal_invalid_poles_raises():
    from schematika.core.exceptions import CircuitValidationError

    with pytest.raises(CircuitValidationError, match="poles"):
        terminal(poles=0)


def test_estop_button_polygon_has_curve_points():
    sym = estop_button()
    poly = _by_type(sym, Polygon)[0]
    r = GRID_SIZE / 4  # 1.25
    # First point is the top of the base.
    assert poly.points[0] == Point(0.0, -r)
    # At i=0 of arc loop (angle = -pi/2), point ≈ (0, -r).
    assert poly.points[1].x == pytest.approx(0.0, abs=1e-9)
    assert poly.points[1].y == pytest.approx(-r, abs=1e-9)
    # 12 points total: 1 base + (steps+1=11) arc.
    assert len(poly.points) == 12


def test_turn_actuator_segments():
    sym = turn_actuator()
    lines = _by_type(sym, Line)
    q = GRID_SIZE / 4  # 1.25
    # Top horizontal: from (-q, -q) to (0, -q).
    assert lines[0].start == Point(-q, -q)
    assert lines[0].end == Point(0.0, -q)
    # Mid vertical: from (0, -q) to (0, q).
    assert lines[1].start == Point(0.0, -q)
    assert lines[1].end == Point(0.0, q)
    # Bottom horizontal: from (0, q) to (q, q).
    assert lines[2].start == Point(0.0, q)
    assert lines[2].end == Point(q, q)


def test_terminal_box_default_box_geometry():
    sym = terminal_box()
    poly = _by_type(sym, Polygon)[0]
    # num_pins=1 → span=0, box_width=GRID_SIZE (2*padding), box_height=10mm.
    pts = {(p.x, p.y) for p in poly.points}
    assert pts == {
        (-_HALF, 0.0),
        (_HALF, 0.0),
        (_HALF, _GRID * 2),
        (-_HALF, _GRID * 2),
    }
    # Single pin line: from (0,0) up to (0, -2.5).
    line = _by_type(sym, Line)[0]
    assert line.start == Point(0.0, 0.0)
    assert line.end == Point(0.0, -_HALF)


def test_terminal_box_port_at_pin_tip():
    sym = terminal_box(num_pins=3)
    # Pins live at x=0, GRID_SIZE*2, GRID_SIZE*4 (10, 20mm spacing).
    assert sym.ports["1"].position == Point(0.0, -_HALF)
    assert sym.ports["2"].position == Point(_GRID * 2, -_HALF)
    assert sym.ports["3"].position == Point(_GRID * 4, -_HALF)
    for port in sym.ports.values():
        assert port.direction == Vector(0, -1)


# ----------------------------------------------------------------------------
# Composite assemblies — exercise that the composition produced expected
# port set and that the linkage line exists.
# ----------------------------------------------------------------------------


def test_contactor_has_3p_contact_ports_only_when_coil_pins_none():
    sym = contactor(label="K1")
    # multipole remaps to sequential "1".."6" port IDs.
    expected_keys = {"1", "2", "3", "4", "5", "6"}
    assert expected_keys.issubset(sym.ports.keys())
    # Coil terminals hidden when coil_pins is None → no A1/A2 ports.
    assert "A1" not in sym.ports
    assert "A2" not in sym.ports


def test_contactor_with_coil_pins_includes_coil_ports():
    sym = contactor(label="K1", coil_pins=("A1", "A2"))
    assert "A1" in sym.ports
    assert "A2" in sym.ports


def test_contactor_includes_dashed_linkage_line():
    sym = contactor(label="K1")
    dashed = [
        e
        for e in sym.elements
        if isinstance(e, Line) and e.style.stroke_dasharray is not None
    ]
    assert len(dashed) == 1


def test_estop_assembly_has_nc_contact_ports():
    sym = estop(label="S1")
    # ESTOP_PINS = ("1", "2") — nc_contact remaps to those.
    assert set(sym.ports.keys()) == {"1", "2"}
    # Includes a dashed linkage line.
    dashed = [
        e
        for e in sym.elements
        if isinstance(e, Line) and e.style.stroke_dasharray is not None
    ]
    assert len(dashed) == 1


def test_turn_switch_assembly_has_no_contact_ports():
    sym = turn_switch(label="S2")
    assert set(sym.ports.keys()) == {"1", "2"}
    dashed = [
        e
        for e in sym.elements
        if isinstance(e, Line) and e.style.stroke_dasharray is not None
    ]
    assert len(dashed) == 1


def test_psu_has_top_and_bottom_pin_ports():
    sym = psu(label="U1")
    for pin in ("L", "N", "PE", "24V", "GND"):
        assert pin in sym.ports
    # Top pins point UP (-1), bottom pins point DOWN (+1).
    assert sym.ports["L"].direction == Vector(0, -1)
    assert sym.ports["GND"].direction == Vector(0, 1)


def test_psu_includes_diagonal_line_and_ac_dc_text():
    sym = psu(label="U1")
    texts = _by_type(sym, Text)
    contents = {t.content for t in texts}
    assert "AC" in contents
    assert "DC" in contents


def test_block_default_has_no_pins():
    sym = block(label="U1")
    assert sym.ports == {}


def test_block_with_top_and_bottom_pins():
    sym = block(label="U1", top_pins=("L", "N"), bottom_pins=("24V", "GND"))
    # Top pins point UP, bottom pins point DOWN.
    assert sym.ports["L"].direction == Vector(0, -1)
    assert sym.ports["N"].direction == Vector(0, -1)
    assert sym.ports["24V"].direction == Vector(0, 1)
    assert sym.ports["GND"].direction == Vector(0, 1)
    # Standard ID aliases.
    assert sym.ports["1"].position == sym.ports["L"].position
    assert sym.ports["3"].position == sym.ports["N"].position
    assert sym.ports["2"].position == sym.ports["24V"].position
    assert sym.ports["4"].position == sym.ports["GND"].position


def test_block_explicit_top_positions_used():
    sym = block(label="U1", top_pins=("A", "B"), top_pin_positions=(0.0, 30.0))
    assert sym.ports["A"].position == Point(0.0, -2.5)
    assert sym.ports["B"].position == Point(30.0, -2.5)


def test_block_mismatched_positions_raises():
    from schematika.core.exceptions import CircuitValidationError

    with pytest.raises(CircuitValidationError, match="top_pin_positions"):
        block(top_pins=("A", "B"), top_pin_positions=(0.0,))


def test_ct_assembly_has_terminal_box_ports():
    sym = ct_assembly(label="X1")
    # CT_ASSEMBLY_PINS = ("1", "2") → terminal_box yields ports "1" and "2".
    assert set(sym.ports.keys()) == {"1", "2"}


# ----------------------------------------------------------------------------
# Multi-pole behavior: count ports.
# ----------------------------------------------------------------------------


@pytest.mark.parametrize("poles", [2, 3])
def test_no_contact_multi_pole_port_count(poles):
    sym = no_contact(poles=poles)
    # 2 ports per pole.
    assert len(sym.ports) == 2 * poles


@pytest.mark.parametrize("poles", [2, 3])
def test_breaker_multi_pole_port_count(poles):
    sym = breaker(poles=poles)
    assert len(sym.ports) == 2 * poles


@pytest.mark.parametrize("poles", [2, 3])
def test_terminal_block_port_count(poles):
    sym = terminal(poles=poles, pins=tuple(str(i) for i in range(1, poles + 1)))
    # Multi-pole TerminalBlock: 2 ports per pole (in/out).
    assert len(sym.ports) == 2 * poles
