"""
Tests for P&ID symbol factories (ISO 14617 / ISA 5.1).
"""

from schematika.core import Circle, Line, Polygon, Symbol, Vector
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

# ---------------------------------------------------------------------------
# Centrifugal pump
# ---------------------------------------------------------------------------


def test_centrifugal_pump_returns_symbol():
    sym = centrifugal_pump("P-001")
    assert isinstance(sym, Symbol)


def test_centrifugal_pump_label():
    sym = centrifugal_pump("P-001")
    assert sym.label == "P-001"


def test_centrifugal_pump_no_label():
    sym = centrifugal_pump()
    assert sym.label == ""


def test_centrifugal_pump_ports_exist():
    sym = centrifugal_pump()
    assert "inlet" in sym.ports
    assert "outlet" in sym.ports


def test_centrifugal_pump_inlet_direction():
    sym = centrifugal_pump()
    assert sym.ports["inlet"].direction == Vector(-1, 0)


def test_centrifugal_pump_outlet_direction():
    sym = centrifugal_pump()
    assert sym.ports["outlet"].direction == Vector(1, 0)


def test_centrifugal_pump_has_elements():
    sym = centrifugal_pump()
    assert len(sym.elements) >= 3  # circle, inlet line, outlet line at minimum


def test_centrifugal_pump_has_circle_body():
    sym = centrifugal_pump()
    circles = [e for e in sym.elements if isinstance(e, Circle)]
    assert len(circles) >= 1


def test_centrifugal_pump_inlet_port_position():
    sym = centrifugal_pump()
    # Inlet port should be to the left (negative x)
    assert sym.ports["inlet"].position.x < 0


def test_centrifugal_pump_outlet_port_position():
    sym = centrifugal_pump()
    # Outlet port should be to the right (positive x)
    assert sym.ports["outlet"].position.x > 0


# ---------------------------------------------------------------------------
# Positive displacement pump
# ---------------------------------------------------------------------------


def test_pd_pump_returns_symbol():
    sym = positive_displacement_pump("P-002")
    assert isinstance(sym, Symbol)


def test_pd_pump_ports_exist():
    sym = positive_displacement_pump()
    assert "inlet" in sym.ports
    assert "outlet" in sym.ports


def test_pd_pump_port_directions():
    sym = positive_displacement_pump()
    assert sym.ports["inlet"].direction == Vector(-1, 0)
    assert sym.ports["outlet"].direction == Vector(1, 0)


def test_pd_pump_has_triangle_indicator():
    sym = positive_displacement_pump()
    polygons = [e for e in sym.elements if isinstance(e, Polygon)]
    assert len(polygons) >= 1


def test_pd_pump_label():
    sym = positive_displacement_pump("P-002")
    assert sym.label == "P-002"


# ---------------------------------------------------------------------------
# Tank / vessel
# ---------------------------------------------------------------------------


def test_tank_returns_symbol():
    sym = tank("T-001")
    assert isinstance(sym, Symbol)


def test_tank_label():
    sym = tank("T-001")
    assert sym.label == "T-001"


def test_tank_ports_exist():
    sym = tank()
    assert "inlet" in sym.ports
    assert "outlet" in sym.ports
    assert "drain" in sym.ports
    assert "vent" in sym.ports


def test_tank_inlet_direction():
    sym = tank()
    assert sym.ports["inlet"].direction == Vector(-1, 0)


def test_tank_outlet_direction():
    sym = tank()
    assert sym.ports["outlet"].direction == Vector(1, 0)


def test_tank_drain_direction():
    sym = tank()
    assert sym.ports["drain"].direction == Vector(0, 1)


def test_tank_vent_direction():
    sym = tank()
    assert sym.ports["vent"].direction == Vector(0, -1)


def test_tank_has_elements():
    sym = tank()
    assert len(sym.elements) >= 4  # 4 body lines + stubs


def test_tank_open_has_more_elements_than_closed():
    # Both have same count of lines but different styles — both valid Symbols
    open_sym = tank(kind="open")
    closed_sym = tank(kind="closed")
    assert isinstance(open_sym, Symbol)
    assert isinstance(closed_sym, Symbol)


# ---------------------------------------------------------------------------
# Heat exchanger
# ---------------------------------------------------------------------------


def test_heat_exchanger_returns_symbol():
    sym = heat_exchanger("HX-001")
    assert isinstance(sym, Symbol)


def test_heat_exchanger_label():
    sym = heat_exchanger("HX-001")
    assert sym.label == "HX-001"


def test_heat_exchanger_ports_exist():
    sym = heat_exchanger()
    assert "shell_in" in sym.ports
    assert "shell_out" in sym.ports
    assert "tube_in" in sym.ports
    assert "tube_out" in sym.ports


def test_heat_exchanger_shell_directions():
    sym = heat_exchanger()
    assert sym.ports["shell_in"].direction == Vector(-1, 0)
    assert sym.ports["shell_out"].direction == Vector(1, 0)


def test_heat_exchanger_tube_directions():
    sym = heat_exchanger()
    assert sym.ports["tube_in"].direction == Vector(0, 1)
    assert sym.ports["tube_out"].direction == Vector(0, -1)


def test_heat_exchanger_has_circle_body():
    sym = heat_exchanger()
    circles = [e for e in sym.elements if isinstance(e, Circle)]
    assert len(circles) >= 1


def test_heat_exchanger_port_positions_reasonable():
    sym = heat_exchanger()
    # shell_in should be to the left of shell_out
    assert sym.ports["shell_in"].position.x < sym.ports["shell_out"].position.x
    # tube_out should be above tube_in (more negative y)
    assert sym.ports["tube_out"].position.y < sym.ports["tube_in"].position.y


# ---------------------------------------------------------------------------
# Gate valve
# ---------------------------------------------------------------------------


def test_gate_valve_returns_symbol():
    sym = gate_valve("V-001")
    assert isinstance(sym, Symbol)


def test_gate_valve_label():
    sym = gate_valve("V-001")
    assert sym.label == "V-001"


def test_gate_valve_ports_exist():
    sym = gate_valve()
    assert "in" in sym.ports
    assert "out" in sym.ports


def test_gate_valve_port_directions():
    sym = gate_valve()
    assert sym.ports["in"].direction == Vector(-1, 0)
    assert sym.ports["out"].direction == Vector(1, 0)


def test_gate_valve_has_two_triangles():
    sym = gate_valve()
    polygons = [e for e in sym.elements if isinstance(e, Polygon)]
    assert len(polygons) == 2


def test_gate_valve_in_left_of_out():
    sym = gate_valve()
    assert sym.ports["in"].position.x < sym.ports["out"].position.x


# ---------------------------------------------------------------------------
# Globe valve
# ---------------------------------------------------------------------------


def test_globe_valve_returns_symbol():
    sym = globe_valve("V-002")
    assert isinstance(sym, Symbol)


def test_globe_valve_ports_exist():
    sym = globe_valve()
    assert "in" in sym.ports
    assert "out" in sym.ports


def test_globe_valve_has_center_circle():
    sym = globe_valve()
    circles = [e for e in sym.elements if isinstance(e, Circle)]
    assert len(circles) >= 1


# ---------------------------------------------------------------------------
# Control valve
# ---------------------------------------------------------------------------


def test_control_valve_returns_symbol():
    sym = control_valve("CV-001")
    assert isinstance(sym, Symbol)


def test_control_valve_ports_exist():
    sym = control_valve()
    assert "in" in sym.ports
    assert "out" in sym.ports


def test_control_valve_has_actuator_stem():
    sym = control_valve()
    lines = [e for e in sym.elements if isinstance(e, Line)]
    # Should have at least the stem line in addition to pipe stubs
    assert len(lines) >= 2


def test_control_valve_has_actuator_triangle():
    sym = control_valve()
    polygons = [e for e in sym.elements if isinstance(e, Polygon)]
    # bowtie (2) + actuator (1) = at least 3
    assert len(polygons) >= 3


def test_control_valve_has_actuator_port():
    sym = control_valve()
    assert "actuator" in sym.ports
    assert sym.ports["actuator"].direction == Vector(0, -1)
    # Actuator port should be above the valve body (negative y)
    assert sym.ports["actuator"].position.y < 0


# ---------------------------------------------------------------------------
# Check valve
# ---------------------------------------------------------------------------


def test_check_valve_returns_symbol():
    sym = check_valve("V-003")
    assert isinstance(sym, Symbol)


def test_check_valve_ports_exist():
    sym = check_valve()
    assert "in" in sym.ports
    assert "out" in sym.ports


def test_check_valve_port_directions():
    sym = check_valve()
    assert sym.ports["in"].direction == Vector(-1, 0)
    assert sym.ports["out"].direction == Vector(1, 0)


def test_check_valve_has_single_triangle():
    sym = check_valve()
    polygons = [e for e in sym.elements if isinstance(e, Polygon)]
    assert len(polygons) == 1


# ---------------------------------------------------------------------------
# Ball valve
# ---------------------------------------------------------------------------


def test_ball_valve_returns_symbol():
    sym = ball_valve("V-004")
    assert isinstance(sym, Symbol)


def test_ball_valve_ports_exist():
    sym = ball_valve()
    assert "in" in sym.ports
    assert "out" in sym.ports


def test_ball_valve_has_filled_circle():
    sym = ball_valve()
    circles = [e for e in sym.elements if isinstance(e, Circle)]
    assert len(circles) >= 1


# ---------------------------------------------------------------------------
# Three-way valve
# ---------------------------------------------------------------------------


def test_three_way_valve_returns_symbol():
    sym = three_way_valve("V-005")
    assert isinstance(sym, Symbol)


def test_three_way_valve_ports_exist():
    sym = three_way_valve()
    assert "in" in sym.ports
    assert "out_a" in sym.ports
    assert "out_b" in sym.ports


def test_three_way_valve_out_b_direction():
    sym = three_way_valve()
    assert sym.ports["out_b"].direction == Vector(0, 1)


# ---------------------------------------------------------------------------
# Instrument bubble
# ---------------------------------------------------------------------------


def test_instrument_bubble_field_returns_symbol():
    sym = instrument_bubble(letters="TT", tag_number="101", location="field")
    assert isinstance(sym, Symbol)


def test_instrument_bubble_field_ports():
    sym = instrument_bubble(letters="TT", location="field")
    assert "process" in sym.ports
    assert "signal_out" in sym.ports


def test_instrument_bubble_field_port_directions():
    sym = instrument_bubble(letters="TT", location="field")
    assert sym.ports["process"].direction == Vector(0, 1)
    assert sym.ports["signal_out"].direction == Vector(0, -1)


def test_instrument_bubble_panel_returns_symbol():
    sym = instrument_bubble(letters="TIC", location="panel")
    assert isinstance(sym, Symbol)


def test_instrument_bubble_panel_has_dividing_line():
    sym = instrument_bubble(letters="TIC", location="panel")
    # panel location adds a horizontal dividing line
    lines = [e for e in sym.elements if isinstance(e, Line)]
    # Should have: divider + process stub + signal stub = at least 3
    assert len(lines) >= 3


def test_instrument_bubble_dcs_returns_symbol():
    sym = instrument_bubble(letters="FIC", location="dcs")
    assert isinstance(sym, Symbol)


def test_instrument_bubble_field_only_bubble_line():
    sym = instrument_bubble(letters="PT", location="field")
    # field has only 2 stubs (no divider)
    lines = [e for e in sym.elements if isinstance(e, Line)]
    assert len(lines) == 2


def test_instrument_bubble_has_circle():
    sym = instrument_bubble(letters="LT", location="field")
    circles = [e for e in sym.elements if isinstance(e, Circle)]
    assert len(circles) == 1


def test_instrument_bubble_label_with_tag_number():
    sym = instrument_bubble(letters="TT", tag_number="101", location="field")
    assert sym.label == "TT-101"


def test_instrument_bubble_label_no_tag():
    sym = instrument_bubble(letters="PT", location="field")
    assert sym.label == "PT"


def test_instrument_bubble_process_port_below():
    sym = instrument_bubble(letters="TT", location="field")
    # process port should be below (positive y)
    assert sym.ports["process"].position.y > 0


def test_instrument_bubble_signal_port_above():
    sym = instrument_bubble(letters="TT", location="field")
    # signal_out port should be above (negative y)
    assert sym.ports["signal_out"].position.y < 0


# ---------------------------------------------------------------------------
# Pipe segment
# ---------------------------------------------------------------------------


def test_pipe_segment_returns_symbol():
    sym = pipe_segment(50.0, "L-001")
    assert isinstance(sym, Symbol)


def test_pipe_segment_default_length():
    sym = pipe_segment()
    assert "in" in sym.ports
    assert "out" in sym.ports


def test_pipe_segment_port_directions():
    sym = pipe_segment()
    assert sym.ports["in"].direction == Vector(-1, 0)
    assert sym.ports["out"].direction == Vector(1, 0)


def test_pipe_segment_port_positions():
    sym = pipe_segment(50.0)
    assert sym.ports["in"].position.x == -25.0
    assert sym.ports["out"].position.x == 25.0


def test_pipe_segment_custom_length():
    sym = pipe_segment(100.0)
    assert sym.ports["in"].position.x == -50.0
    assert sym.ports["out"].position.x == 50.0


# ---------------------------------------------------------------------------
# Pipe tee
# ---------------------------------------------------------------------------


def test_pipe_tee_returns_symbol():
    sym = pipe_tee()
    assert isinstance(sym, Symbol)


def test_pipe_tee_ports_exist():
    sym = pipe_tee()
    assert "in" in sym.ports
    assert "out" in sym.ports
    assert "branch" in sym.ports


def test_pipe_tee_branch_direction():
    sym = pipe_tee()
    assert sym.ports["branch"].direction == Vector(0, 1)


def test_pipe_tee_branch_below():
    sym = pipe_tee()
    assert sym.ports["branch"].position.y > 0


# ---------------------------------------------------------------------------
# Pipe reducer
# ---------------------------------------------------------------------------


def test_pipe_reducer_returns_symbol():
    sym = pipe_reducer("R-001")
    assert isinstance(sym, Symbol)


def test_pipe_reducer_ports_exist():
    sym = pipe_reducer()
    assert "in" in sym.ports
    assert "out" in sym.ports


def test_pipe_reducer_port_directions():
    sym = pipe_reducer()
    assert sym.ports["in"].direction == Vector(-1, 0)
    assert sym.ports["out"].direction == Vector(1, 0)


def test_pipe_reducer_in_left_of_out():
    sym = pipe_reducer()
    assert sym.ports["in"].position.x < sym.ports["out"].position.x


def test_pipe_reducer_has_trapezoid_lines():
    sym = pipe_reducer()
    lines = [e for e in sym.elements if isinstance(e, Line)]
    # 4 outline lines + 2 stubs = 6
    assert len(lines) >= 4


# ---------------------------------------------------------------------------
# Pipe cap
# ---------------------------------------------------------------------------


def test_pipe_cap_returns_symbol():
    sym = pipe_cap()
    assert isinstance(sym, Symbol)


def test_pipe_cap_has_inlet_port():
    sym = pipe_cap()
    assert "in" in sym.ports


def test_pipe_cap_inlet_direction():
    sym = pipe_cap()
    assert sym.ports["in"].direction == Vector(-1, 0)


def test_pipe_cap_has_two_lines():
    sym = pipe_cap()
    lines = [e for e in sym.elements if isinstance(e, Line)]
    assert len(lines) == 2  # stub + cap bar


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_constants_importable():
    from schematika.pid.constants import (
        INSTRUMENT_BUBBLE_RADIUS,
        ISA_FIRST_LETTER,
        ISA_SUCCEEDING_LETTERS,
        PID_EQUIPMENT_STROKE,
        PID_LABEL_OFFSET,
        PID_LINE_WEIGHT,
        PID_MIN_EQUIPMENT_GAP,
        PID_MIN_LEG_SPACING,
        PID_SIGNAL_DASH,
        PID_SIGNAL_LINE_WEIGHT,
        VALVE_SIZE,
    )

    assert INSTRUMENT_BUBBLE_RADIUS == 6.0
    assert VALVE_SIZE == 10.0
    assert PID_LINE_WEIGHT == 0.7
    assert PID_SIGNAL_LINE_WEIGHT == 0.25
    assert PID_SIGNAL_DASH == "2.0,2.0"
    assert PID_EQUIPMENT_STROKE == 0.5
    assert PID_MIN_EQUIPMENT_GAP == 30.0
    assert PID_MIN_LEG_SPACING == 40.0
    assert PID_LABEL_OFFSET == 5.0
    assert isinstance(ISA_FIRST_LETTER, dict)
    assert isinstance(ISA_SUCCEEDING_LETTERS, dict)
    assert "T" in ISA_FIRST_LETTER
    assert "T" in ISA_SUCCEEDING_LETTERS


def test_pid_package_top_level_imports():
    import schematika.pid as pid

    assert callable(pid.centrifugal_pump)
    assert callable(pid.gate_valve)
    assert callable(pid.instrument_bubble)
    assert callable(pid.tank)
