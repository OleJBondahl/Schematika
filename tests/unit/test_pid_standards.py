"""
Tests for P&ID standards compliance (ISA 5.1, ISO 14617, ISO 3098).

These tests verify that symbols, constants, and validation enforce the
rules documented in ``schematika.pid.constants``.
"""

import pytest

from schematika.core import Circle, Line, Polygon, Vector
from schematika.pid.constants import (
    GRID_SIZE,
    INSTRUMENT_BUBBLE_RADIUS,
    ISA_FIRST_LETTER,
    ISA_SUCCEEDING_LETTERS,
    PID_EQUIPMENT_STROKE,
    PID_LINE_WEIGHT,
    PID_MIN_EQUIPMENT_GAP,
    PID_MIN_LEG_SPACING,
    PID_PUMP_RADIUS,
    PID_SIGNAL_LINE_WEIGHT,
    PID_TEXT_SIZE_BUBBLE,
    PID_TEXT_SIZE_PIPE,
    PID_TEXT_SIZE_TAG,
    VALVE_SIZE,
    validate_isa_letters,
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
    positive_displacement_pump,
    tank,
    three_way_valve,
)

# ---------------------------------------------------------------------------
# ISA 5.1 letter code validation
# ---------------------------------------------------------------------------


class TestISALetterValidation:
    """ISA 5.1 Clause 4 — instrument identification letter codes."""

    def test_valid_simple_transmitter(self):
        assert validate_isa_letters("TT") == []

    def test_valid_flow_controller(self):
        assert validate_isa_letters("FIC") == []

    def test_valid_pressure_transmitter(self):
        assert validate_isa_letters("PT") == []

    def test_valid_level_alarm_high(self):
        assert validate_isa_letters("LAH") == []

    def test_valid_single_first_letter(self):
        assert validate_isa_letters("T") == []

    def test_invalid_empty(self):
        errors = validate_isa_letters("")
        assert len(errors) == 1
        assert "empty" in errors[0].lower()

    def test_invalid_first_letter(self):
        # '0' is not a valid ISA first letter
        errors = validate_isa_letters("0T")
        assert len(errors) == 1
        assert "First letter" in errors[0]

    def test_invalid_succeeding_letter(self):
        # 'Q' is a valid first letter but not a succeeding letter
        errors = validate_isa_letters("TQ")
        assert len(errors) == 1
        assert "Succeeding letter" in errors[0]
        assert "position 2" in errors[0]

    def test_all_first_letters_valid(self):
        """Every key in ISA_FIRST_LETTER must pass as a first letter."""
        for letter in ISA_FIRST_LETTER:
            assert validate_isa_letters(letter) == [], f"'{letter}' should be valid"

    def test_all_succeeding_letters_valid(self):
        """Every key in ISA_SUCCEEDING_LETTERS must pass as a succeeding letter."""
        for letter in ISA_SUCCEEDING_LETTERS:
            code = f"T{letter}"  # T is always valid as first letter
            assert validate_isa_letters(code) == [], f"'T{letter}' should be valid"

    def test_common_instrument_codes(self):
        """Common ISA instrument codes must all validate."""
        valid_codes = [
            "TT",
            "PT",
            "FT",
            "LT",
            "AT",  # transmitters
            "TI",
            "PI",
            "FI",
            "LI",  # indicators
            "TIC",
            "PIC",
            "FIC",
            "LIC",  # controllers
            "TE",
            "PE",
            "FE",
            "LE",  # elements
            "TSH",
            "PSL",
            "FSL",
            "LSH",  # switches (high/low)
            "TAH",
            "PAL",
            "FAH",
            "LAL",  # alarms (high/low)
            "TV",
            "PV",
            "FV",
            "LV",  # valves
            "TR",
            "PR",
            "FR",
            "LR",  # recorders
        ]
        for code in valid_codes:
            assert validate_isa_letters(code) == [], f"'{code}' should be valid"


# ---------------------------------------------------------------------------
# ISA 5.1 — instrument bubble dimensions
# ---------------------------------------------------------------------------


class TestISABubbleDimensions:
    """ISA 5.1 Clause 5.2 — instrument bubble symbol rules."""

    def test_bubble_diameter_is_12mm(self):
        """ISA 5.1: bubble diameter shall be 12 mm (±tolerance)."""
        assert pytest.approx(12.0, abs=1.0) == INSTRUMENT_BUBBLE_RADIUS * 2

    def test_bubble_is_circle(self):
        sym = instrument_bubble(letters="TT", location="field")
        circles = [e for e in sym.elements if isinstance(e, Circle)]
        assert len(circles) == 1
        assert circles[0].radius == INSTRUMENT_BUBBLE_RADIUS

    def test_field_location_no_divider_without_tag(self):
        """Field instrument without tag: no horizontal divider."""
        sym = instrument_bubble(letters="TT", location="field")
        lines = [e for e in sym.elements if isinstance(e, Line)]
        # Only process stub + signal stub = 2 lines
        assert len(lines) == 2

    def test_field_location_divider_with_tag(self):
        """Field instrument with tag: horizontal divider present."""
        sym = instrument_bubble(letters="TT", tag_number="101", location="field")
        lines = [e for e in sym.elements if isinstance(e, Line)]
        # Process stub + signal stub + divider = 3 lines
        assert len(lines) == 3

    def test_panel_location_has_divider(self):
        """Panel-mounted instrument always has horizontal divider."""
        sym = instrument_bubble(letters="TIC", location="panel")
        lines = [e for e in sym.elements if isinstance(e, Line)]
        assert len(lines) >= 3  # divider + 2 stubs

    def test_dcs_location_has_dashed_divider(self):
        """DCS instrument has dashed horizontal divider."""
        sym = instrument_bubble(letters="FIC", location="dcs")
        lines = [e for e in sym.elements if isinstance(e, Line)]
        dashed = [ln for ln in lines if ln.style.stroke_dasharray is not None]
        assert len(dashed) >= 1

    def test_process_port_direction_downward(self):
        """Process connection port points downward (toward pipe)."""
        sym = instrument_bubble(letters="TT", location="field")
        assert sym.ports["process"].direction == Vector(0, 1)

    def test_signal_port_direction_upward(self):
        """Signal output port points upward (toward panel/DCS)."""
        sym = instrument_bubble(letters="TT", location="field")
        assert sym.ports["signal_out"].direction == Vector(0, -1)


# ---------------------------------------------------------------------------
# ISO 14617 — line weight hierarchy
# ---------------------------------------------------------------------------


class TestLineWeightHierarchy:
    """ISO 14617 Part 1, Clause 4 — line weight rules."""

    def test_process_heavier_than_equipment(self):
        """Process pipe lines must be heavier than equipment body lines."""
        assert PID_LINE_WEIGHT > PID_EQUIPMENT_STROKE

    def test_equipment_heavier_than_signal(self):
        """Equipment body lines must be heavier than signal lines."""
        assert PID_EQUIPMENT_STROKE > PID_SIGNAL_LINE_WEIGHT

    def test_exactly_three_standard_weights(self):
        """Only three line weights are permitted on a P&ID."""
        weights = {PID_LINE_WEIGHT, PID_EQUIPMENT_STROKE, PID_SIGNAL_LINE_WEIGHT}
        assert len(weights) == 3

    def test_all_constants_grid_relative(self):
        """All dimensional constants must be expressible as GRID_SIZE * factor."""
        # These constants are defined as GRID_SIZE * something; verify
        # they are reasonable multiples of the grid
        for name, value in [
            ("PID_LINE_WEIGHT", PID_LINE_WEIGHT),
            ("PID_EQUIPMENT_STROKE", PID_EQUIPMENT_STROKE),
            ("INSTRUMENT_BUBBLE_RADIUS", INSTRUMENT_BUBBLE_RADIUS),
            ("VALVE_SIZE", VALVE_SIZE),
            ("PID_PUMP_RADIUS", PID_PUMP_RADIUS),
            ("PID_MIN_EQUIPMENT_GAP", PID_MIN_EQUIPMENT_GAP),
            ("PID_MIN_LEG_SPACING", PID_MIN_LEG_SPACING),
        ]:
            factor = value / GRID_SIZE
            assert factor > 0, f"{name} must be positive"
            # Factor should be a clean number (within float tolerance)
            assert abs(factor - round(factor, 2)) < 1e-9, (
                f"{name} = {value} is not a clean grid multiple (factor = {factor})"
            )


# ---------------------------------------------------------------------------
# ISO 14617 — valve symbols
# ---------------------------------------------------------------------------


class TestISO14617Valves:
    """ISO 14617 Part 8 — valve symbol geometry rules."""

    def test_gate_valve_bowtie_two_triangles(self):
        """Gate valve: two triangles forming a bowtie."""
        sym = gate_valve()
        polygons = [e for e in sym.elements if isinstance(e, Polygon)]
        assert len(polygons) == 2

    def test_globe_valve_bowtie_plus_circle(self):
        """Globe valve: bowtie + center circle."""
        sym = globe_valve()
        polygons = [e for e in sym.elements if isinstance(e, Polygon)]
        circles = [e for e in sym.elements if isinstance(e, Circle)]
        assert len(polygons) == 2
        assert len(circles) >= 1

    def test_check_valve_single_triangle_plus_seat(self):
        """Check valve: single triangle + perpendicular seat bar."""
        sym = check_valve()
        polygons = [e for e in sym.elements if isinstance(e, Polygon)]
        assert len(polygons) == 1
        # Seat bar is a Line
        lines = [e for e in sym.elements if isinstance(e, Line)]
        assert len(lines) >= 3  # seat + 2 stubs

    def test_ball_valve_bowtie_plus_filled_circle(self):
        """Ball valve: bowtie + filled center circle."""
        sym = ball_valve()
        circles = [e for e in sym.elements if isinstance(e, Circle)]
        filled = [c for c in circles if c.style.fill not in (None, "none")]
        assert len(filled) >= 1

    def test_three_way_valve_has_branch_port(self):
        """Three-way valve: bowtie + perpendicular branch port."""
        sym = three_way_valve()
        assert "in" in sym.ports
        assert "out_a" in sym.ports
        assert "out_b" in sym.ports
        # Branch port direction is downward
        assert sym.ports["out_b"].direction == Vector(0, 1)

    def test_control_valve_has_actuator(self):
        """Control valve: globe body + actuator stem + diaphragm."""
        sym = control_valve()
        assert "actuator" in sym.ports
        # Actuator port is above (negative y)
        assert sym.ports["actuator"].position.y < 0

    def test_all_valves_have_horizontal_flow(self):
        """All two-port valves have in (left) and out (right)."""
        for factory in [gate_valve, globe_valve, check_valve, ball_valve]:
            sym = factory()
            assert sym.ports["in"].direction == Vector(-1, 0), factory.__name__
            assert sym.ports["out"].direction == Vector(1, 0), factory.__name__
            assert sym.ports["in"].position.x < sym.ports["out"].position.x, (
                factory.__name__
            )


# ---------------------------------------------------------------------------
# ISO 14617 — process equipment symbols
# ---------------------------------------------------------------------------


class TestISO14617Equipment:
    """ISO 14617 Part 6 — process equipment symbol rules."""

    def test_centrifugal_pump_circular_body(self):
        """Centrifugal pump body is a circle."""
        sym = centrifugal_pump()
        circles = [e for e in sym.elements if isinstance(e, Circle)]
        assert len(circles) >= 1
        assert circles[0].radius == PID_PUMP_RADIUS

    def test_centrifugal_pump_flow_triangle(self):
        """Centrifugal pump has an internal filled triangle."""
        sym = centrifugal_pump()
        polygons = [e for e in sym.elements if isinstance(e, Polygon)]
        assert len(polygons) >= 1
        filled = [p for p in polygons if p.style.fill not in (None, "none")]
        assert len(filled) >= 1

    def test_centrifugal_pump_horizontal_flow(self):
        """Centrifugal pump: inlet left, outlet right, same height."""
        sym = centrifugal_pump()
        inlet = sym.ports["inlet"]
        outlet = sym.ports["outlet"]
        assert inlet.direction == Vector(-1, 0)
        assert outlet.direction == Vector(1, 0)
        assert inlet.position.y == pytest.approx(outlet.position.y)

    def test_pd_pump_same_convention(self):
        """PD pump follows same circle + triangle convention."""
        sym = positive_displacement_pump()
        circles = [e for e in sym.elements if isinstance(e, Circle)]
        polygons = [e for e in sym.elements if isinstance(e, Polygon)]
        assert len(circles) >= 1
        assert len(polygons) >= 1

    def test_tank_rectangular_body(self):
        """Tank body is rectangular (4+ lines)."""
        sym = tank()
        lines = [e for e in sym.elements if isinstance(e, Line)]
        assert len(lines) >= 4

    def test_tank_four_ports(self):
        """Tank has inlet, outlet, drain, and vent ports."""
        sym = tank()
        assert "inlet" in sym.ports
        assert "outlet" in sym.ports
        assert "drain" in sym.ports
        assert "vent" in sym.ports

    def test_heat_exchanger_circular_body(self):
        """Heat exchanger body is a circle."""
        sym = heat_exchanger()
        circles = [e for e in sym.elements if isinstance(e, Circle)]
        assert len(circles) >= 1


# ---------------------------------------------------------------------------
# ISO 3098 — text sizing
# ---------------------------------------------------------------------------


class TestISO3098TextSizing:
    """ISO 3098 — minimum text heights for technical drawings."""

    def test_text_sizes_at_least_2_5mm(self):
        """All P&ID text sizes must be at least 2.5 mm (ISO 3098 minimum)."""
        assert PID_TEXT_SIZE_BUBBLE >= 2.5
        assert PID_TEXT_SIZE_TAG >= 2.5
        assert PID_TEXT_SIZE_PIPE >= 2.5

    def test_text_sizes_grid_relative(self):
        """Text sizes are derived from GRID_SIZE."""
        assert pytest.approx(GRID_SIZE * 0.5) == PID_TEXT_SIZE_BUBBLE


# ---------------------------------------------------------------------------
# ISO 14617 — spacing rules
# ---------------------------------------------------------------------------


class TestSpacingRules:
    """ISO 14617 Part 1, Clause 5 — minimum spacing requirements."""

    def test_equipment_gap_positive(self):
        assert PID_MIN_EQUIPMENT_GAP > 0

    def test_leg_spacing_positive(self):
        assert PID_MIN_LEG_SPACING > 0

    def test_leg_spacing_greater_than_equipment_gap(self):
        """Parallel pipe legs need more space than adjacent equipment."""
        assert PID_MIN_LEG_SPACING > PID_MIN_EQUIPMENT_GAP


# ---------------------------------------------------------------------------
# Builder ISA validation integration
# ---------------------------------------------------------------------------


class TestBuilderISAEnforcement:
    """Builder enforces ISA 5.1 letter codes at instrument creation."""

    def test_builder_rejects_invalid_letters(self):
        from schematika.pid.builder import PIDBuilder
        from schematika.pid.symbols import centrifugal_pump as pump_factory

        b = PIDBuilder()
        b.add_equipment("pump", pump_factory, "P", x=50, y=50)
        with pytest.raises(ValueError, match="ISA 5.1"):
            b.add_instrument("bad", "QQ", on_equipment="pump")

    def test_builder_accepts_valid_letters(self):
        from schematika.pid.builder import PIDBuilder
        from schematika.pid.symbols import centrifugal_pump as pump_factory

        b = PIDBuilder()
        b.add_equipment("pump", pump_factory, "P", x=50, y=50)
        b.add_instrument("tt1", "TT", on_equipment="pump")
        assert "tt1" in b._instruments
