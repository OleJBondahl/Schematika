import pytest

from schematika.electrical.model.core import Symbol
from schematika.electrical.symbols.actuators import turn_actuator
from schematika.electrical.symbols.assemblies import contactor, turn_switch
from schematika.electrical.symbols.blocks import block, terminal_box
from schematika.electrical.symbols.breakers import breaker
from schematika.electrical.symbols.coils import coil
from schematika.electrical.symbols.contacts import nc_contact, no_contact, spdt_contact
from schematika.electrical.symbols.motors import motor
from schematika.electrical.symbols.protection import fuse, thermal_overload
from schematika.electrical.symbols.terminals import TerminalBlock, terminal
from schematika.electrical.symbols.transducers import ct, ct_assembly


class TestSymbolsUnit:
    def test_terminals(self):
        s = terminal("X1", pins=("1",))
        assert isinstance(s, Symbol)
        # Should have 2 ports (top and bottom)
        assert len(s.ports) >= 2

        s3 = terminal("X3", poles=3, pins=("1", "2", "3", "4", "5", "6"))
        assert isinstance(s3, Symbol)
        assert len(s3.ports) == 6

    def test_contacts(self):
        no = no_contact("-K1", pins=("13", "14"))
        assert isinstance(no, Symbol)
        assert len(no.elements) > 0
        assert "13" in no.ports  # Port keys use IEC pin labels
        assert "14" in no.ports

        nc = nc_contact("-K2", pins=("11", "12"))
        assert isinstance(nc, Symbol)

        no3 = no_contact("-Q1", poles=3, pins=("1", "2", "3", "4", "5", "6"))
        assert isinstance(no3, Symbol)
        # Should have 6 ports
        assert len(no3.ports) >= 6

    def test_coil(self):
        c = coil("-K1", ("A1", "A2"))
        assert isinstance(c, Symbol)
        assert len(c.ports) == 2
        assert list(c.ports.keys()) == ["A1", "A2"]

    def test_coil_inverted_pins(self):
        c = coil("-K1", ("A2", "A1"))
        assert list(c.ports.keys()) == ["A2", "A1"]
        assert c.ports["A2"].position.y < c.ports["A1"].position.y

    def test_protection(self):
        t = thermal_overload("-F1", poles=3, pins=("1", "2", "3", "4", "5", "6"))
        assert isinstance(t, Symbol)
        assert len(t.ports) == 6

    def test_assemblies_contactor(self):
        k = contactor("-K1", ("A1", "A2"), ("1", "2", "3", "4", "5", "6"))
        assert isinstance(k, Symbol)
        # Contactor has coil (2 ports) + 3 pole contact (6 ports) = 8 ports
        assert len(k.ports) == 8
        assert k.label == "-K1"

    def test_single_phase_motor(self):
        """Test single-phase motor symbol creation."""
        m = motor("-M1", pins=("1", "2"))
        assert isinstance(m, Symbol)
        assert len(m.ports) == 2
        assert "1" in m.ports
        assert "2" in m.ports
        assert m.label == "-M1"
        # Should have elements (circle, text, lines)
        assert len(m.elements) > 0

    def test_three_phase_motor(self):
        """Test three-phase motor symbol creation."""
        m3 = motor("-M1", poles=3, pins=("U", "V", "W", "PE"))
        assert isinstance(m3, Symbol)
        assert len(m3.ports) == 4
        assert "U" in m3.ports
        assert "V" in m3.ports
        assert "W" in m3.ports
        assert "PE" in m3.ports
        assert m3.label == "-M1"
        # Should have multiple elements (circle, text, terminal lines)
        assert len(m3.elements) > 0

    def test_three_phase_motor_positions(self):
        """Test three-phase motor symbol pin positions."""
        # Pins should populate left to right: U, V, W
        m3 = motor("-M1", poles=3, pins=("U", "V", "W", "PE"))

        u_pos = m3.ports["U"].position
        v_pos = m3.ports["V"].position
        w_pos = m3.ports["W"].position
        pe_pos = m3.ports["PE"].position

        # Verify relative X order
        assert u_pos.x < v_pos.x
        assert v_pos.x < w_pos.x

        # Verify specific offsets (based on DEFAULT_POLE_SPACING=10)
        # U: -10, V: 0, W: 10
        assert abs(u_pos.x - (-10.0)) < 0.001
        assert abs(v_pos.x - 0.0) < 0.001
        assert abs(w_pos.x - 10.0) < 0.001

        # PE should be to the right (at radius=20)
        assert pe_pos.x > w_pos.x
        assert abs(pe_pos.x - 20.0) < 0.001

    def test_turn_actuator_creation(self):
        """Test basic creation of turn switch actuator symbol."""
        sym = turn_actuator()
        assert sym is not None
        assert isinstance(sym, Symbol)
        assert len(sym.elements) == 3  # TOP, MID, BOT lines
        assert len(sym.ports) == 0  # Actuator symbols have no ports

    def test_turn_actuator_with_label(self):
        """Test turn switch actuator symbol with label."""
        sym = turn_actuator(label="-S1")
        assert sym is not None
        assert sym.label == "-S1"

    def test_turn_actuator_rotation(self):
        """Test rotation is applied."""
        sym = turn_actuator(rotation=180)
        assert sym is not None
        assert len(sym.elements) == 3
        # Elements should be transformed (rotation applied)

    def test_turn_switch_assembly_creation(self):
        """Test basic creation of turn switch assembly."""
        sym = turn_switch()
        assert sym is not None
        assert isinstance(sym, Symbol)
        # Assembly should have multiple elements: contact + linkage + actuator
        assert len(sym.elements) > 3

    def test_turn_switch_assembly_has_ports(self):
        """Assembly inherits ports from NO contact."""
        sym = turn_switch()
        assert "1" in sym.ports
        assert "2" in sym.ports
        assert len(sym.ports) == 2

    def test_turn_switch_assembly_custom_pins(self):
        """Test custom pin labels."""
        sym = turn_switch(label="-S1", pins=("A", "B"))
        assert sym.label == "-S1"
        # Port keys use pin labels
        assert "A" in sym.ports
        assert "B" in sym.ports


# ──────────────────────────────────────────────────────────────────────
#  Circuit Breaker Symbols (breakers.py)
# ──────────────────────────────────────────────────────────────────────


class TestCircuitBreakerSymbol:
    """Tests for breaker (single pole)."""

    def test_basic_creation(self):
        """Single-pole circuit breaker returns a Symbol with 2 ports."""
        sym = breaker(label="F1", pins=("1", "2"))
        assert isinstance(sym, Symbol)
        assert sym.label == "F1"
        assert "1" in sym.ports
        assert "2" in sym.ports
        assert len(sym.ports) == 2

    def test_elements_include_cross(self):
        """Circuit breaker should have more elements than a plain NO contact
        because of the cross (X) at the interruption point."""
        sym = breaker(label="F1", pins=("1", "2"))
        assert len(sym.elements) >= 5

    def test_port_positions_vertical(self):
        """Port 1 should be above port 2 (smaller Y value)."""
        sym = breaker()
        p1 = sym.ports["1"].position
        p2 = sym.ports["2"].position
        assert p1.y < p2.y
        # Both ports should be centered on x=0
        assert abs(p1.x) < 0.001
        assert abs(p2.x) < 0.001

    def test_port_directions(self):
        """Port 1 direction should point upward, port 2 downward."""
        sym = breaker()
        assert sym.ports["1"].direction.dy == -1
        assert sym.ports["2"].direction.dy == 1

    def test_label_present_in_elements(self):
        """When a label is provided, a text element should be among the elements."""
        sym_with = breaker(label="F1")
        sym_without = breaker(label="")
        assert len(sym_with.elements) > len(sym_without.elements)

    def test_no_label(self):
        """Empty label should produce a symbol with label=''."""
        sym = breaker()
        assert sym.label == ""

    def test_no_pins(self):
        """When pins are empty, no pin label elements are added."""
        sym_no_pins = breaker(label="F1", pins=())
        sym_with_pins = breaker(label="F1", pins=("1", "2"))
        assert len(sym_with_pins.elements) > len(sym_no_pins.elements)

    def test_pin_labels_added(self):
        """Providing pins should add pin label text elements."""
        sym = breaker(label="", pins=("3", "4"))
        # Without pins: 5 elements (2 leads + blade + 2 cross lines)
        sym_bare = breaker(label="", pins=())
        assert len(sym.elements) > len(sym_bare.elements)


class TestTwoPoleCircuitBreakerSymbol:
    """Tests for breaker(poles=2)."""

    def test_basic_creation(self):
        """Two-pole breaker returns a Symbol with 4 ports."""
        sym = breaker(label="F1", poles=2, pins=("1", "2", "3", "4"))
        assert isinstance(sym, Symbol)
        assert sym.label == "F1"
        assert len(sym.ports) == 4

    def test_has_expected_ports(self):
        """Should have ports 1-4 for two poles."""
        sym = breaker(poles=2)
        for port_id in ("1", "2", "3", "4"):
            assert port_id in sym.ports, f"Port '{port_id}' missing"

    def test_pole_spacing(self):
        """Second pole should be offset from first by DEFAULT_POLE_SPACING (10mm)."""
        sym = breaker(poles=2)
        p1_x = sym.ports["1"].position.x
        p3_x = sym.ports["3"].position.x
        assert abs(p3_x - p1_x - 10.0) < 0.001

    def test_no_label(self):
        sym = breaker(poles=2)
        assert sym.label == ""

    def test_elements_present(self):
        sym = breaker(label="F2", poles=2)
        assert len(sym.elements) > 0


class TestThreePoleCircuitBreakerSymbol:
    """Tests for breaker(poles=3)."""

    def test_basic_creation(self):
        """Three-pole breaker returns a Symbol with 6 ports."""
        sym = breaker(label="Q1", poles=3, pins=("1", "2", "3", "4", "5", "6"))
        assert isinstance(sym, Symbol)
        assert sym.label == "Q1"
        assert len(sym.ports) == 6

    def test_has_expected_ports(self):
        """Should have ports 1 through 6."""
        sym = breaker(poles=3)
        for port_id in ("1", "2", "3", "4", "5", "6"):
            assert port_id in sym.ports, f"Port '{port_id}' missing"

    def test_pole_spacing(self):
        """Poles should be spaced at DEFAULT_POLE_SPACING (10mm) intervals."""
        sym = breaker(poles=3)
        p1_x = sym.ports["1"].position.x
        p3_x = sym.ports["3"].position.x
        p5_x = sym.ports["5"].position.x
        assert abs(p3_x - p1_x - 10.0) < 0.001
        assert abs(p5_x - p3_x - 10.0) < 0.001

    def test_top_bottom_alignment(self):
        """Top ports (1,3,5) should be above bottom ports (2,4,6)."""
        sym = breaker(poles=3)
        for top, bot in [("1", "2"), ("3", "4"), ("5", "6")]:
            assert sym.ports[top].position.y < sym.ports[bot].position.y

    def test_no_label(self):
        sym = breaker(poles=3)
        assert sym.label == ""

    def test_elements_present(self):
        sym = breaker(label="Q1", poles=3)
        assert len(sym.elements) > 0


# ──────────────────────────────────────────────────────────────────────
#  Fuse Symbol (protection.py)
# ──────────────────────────────────────────────────────────────────────


class TestFuseSymbol:
    """Tests for fuse."""

    def test_basic_creation(self):
        """Fuse returns a Symbol with 2 ports."""
        sym = fuse(label="F1", pins=("1", "2"))
        assert isinstance(sym, Symbol)
        assert sym.label == "F1"
        assert "1" in sym.ports
        assert "2" in sym.ports
        assert len(sym.ports) == 2

    def test_port_positions_vertical(self):
        """Port 1 (top) should be above port 2 (bottom)."""
        sym = fuse()
        p1 = sym.ports["1"].position
        p2 = sym.ports["2"].position
        assert p1.y < p2.y
        # Both centered on x=0
        assert abs(p1.x) < 0.001
        assert abs(p2.x) < 0.001

    def test_port_directions(self):
        """Port 1 should point up, port 2 should point down."""
        sym = fuse()
        assert sym.ports["1"].direction.dy == -1
        assert sym.ports["2"].direction.dy == 1

    def test_has_elements(self):
        """Fuse should have at least a box and an internal line."""
        sym = fuse()
        assert len(sym.elements) >= 2

    def test_label_present_in_elements(self):
        """A label adds an element compared to no label."""
        sym_with = fuse(label="F1")
        sym_without = fuse(label="")
        assert len(sym_with.elements) > len(sym_without.elements)

    def test_no_label(self):
        """Empty label produces symbol with label=''."""
        sym = fuse()
        assert sym.label == ""

    def test_no_pins(self):
        """No pins means no pin label elements."""
        sym_no_pins = fuse(label="F1", pins=())
        sym_with_pins = fuse(label="F1", pins=("1", "2"))
        assert len(sym_with_pins.elements) > len(sym_no_pins.elements)

    def test_pin_labels_added(self):
        """Providing pins adds pin label text elements."""
        sym = fuse(label="", pins=("3", "4"))
        sym_bare = fuse(label="", pins=())
        assert len(sym.elements) > len(sym_bare.elements)


# ──────────────────────────────────────────────────────────────────────
#  SPDT Contact Symbols (contacts.py)
# ──────────────────────────────────────────────────────────────────────


class TestSpdtContactSymbol:
    """Tests for spdt_contact (single pole double throw)."""

    def test_basic_creation(self):
        """SPDT contact returns a Symbol with 3 ports."""
        sym = spdt_contact(label="-K1", pins=("11", "12", "14"))
        assert isinstance(sym, Symbol)
        assert sym.label == "-K1"
        assert len(sym.ports) == 3

    def test_port_ids(self):
        """Port keys match pin labels: '11' (common), '12' (NC), '14' (NO)."""
        sym = spdt_contact()
        assert "11" in sym.ports  # Common
        assert "12" in sym.ports  # NC
        assert "14" in sym.ports  # NO

    def test_standard_orientation_positions(self):
        """In standard orientation, common is bottom, NC/NO are top."""
        sym = spdt_contact(inverted=False)
        com_y = sym.ports["11"].position.y
        nc_y = sym.ports["12"].position.y
        no_y = sym.ports["14"].position.y
        # Common is at bottom (larger Y)
        assert com_y > nc_y
        assert com_y > no_y

    def test_inverted_orientation_positions(self):
        """In inverted orientation, common is top, NC/NO are bottom."""
        sym = spdt_contact(inverted=True)
        com_y = sym.ports["11"].position.y
        nc_y = sym.ports["12"].position.y
        no_y = sym.ports["14"].position.y
        # Common is at top (smaller Y)
        assert com_y < nc_y
        assert com_y < no_y

    def test_nc_left_no_right_standard(self):
        """In standard orientation, NC is left of NO."""
        sym = spdt_contact(inverted=False)
        nc_x = sym.ports["12"].position.x
        no_x = sym.ports["14"].position.x
        assert nc_x < no_x

    def test_nc_left_no_right_inverted(self):
        """In inverted orientation, NC is still left of NO."""
        sym = spdt_contact(inverted=True)
        nc_x = sym.ports["12"].position.x
        no_x = sym.ports["14"].position.x
        assert nc_x < no_x

    def test_label_present_in_elements(self):
        sym_with = spdt_contact(label="-K1")
        sym_without = spdt_contact(label="")
        assert len(sym_with.elements) > len(sym_without.elements)

    def test_no_label(self):
        sym = spdt_contact(label="")
        assert sym.label == ""

    def test_elements_present(self):
        sym = spdt_contact()
        # Should have at least: l_com, l_no, l_nc, seat_nc, blade = 5 elements
        assert len(sym.elements) >= 5

    def test_pin_labels_added(self):
        """Providing pins should add text elements for the pin labels."""
        sym_with = spdt_contact(pins=("11", "12", "14"))
        sym_without = spdt_contact(pins=())
        assert len(sym_with.elements) > len(sym_without.elements)

    def test_no_pins(self):
        """Empty pins tuple produces fewer elements."""
        sym = spdt_contact(pins=())
        # Only geometric elements + no pin labels
        assert len(sym.elements) >= 5


class TestMultiPoleSpdtSymbol:
    """Tests for spdt_contact with poles > 1."""

    def test_basic_three_pole(self):
        """Three-pole SPDT returns a Symbol with 9 ports (3 per pole)."""
        sym = spdt_contact(poles=3, label="-K1")
        assert isinstance(sym, Symbol)
        assert sym.label == "-K1"
        assert len(sym.ports) == 9

    def test_port_naming_convention(self):
        """Ports keyed by pin labels: 11, 12, 14, 21, 22, 24, etc."""
        sym = spdt_contact(poles=3)
        for pole in range(1, 4):
            assert f"{pole}1" in sym.ports
            assert f"{pole}2" in sym.ports
            assert f"{pole}4" in sym.ports

    def test_two_pole(self):
        """Two-pole SPDT should have 6 ports."""
        sym = spdt_contact(poles=2, label="-K2")
        assert len(sym.ports) == 6
        assert "11" in sym.ports
        assert "21" in sym.ports

    def test_single_pole(self):
        """Single-pole via spdt_contact(poles=1) should have 3 ports."""
        sym = spdt_contact(poles=1)
        assert len(sym.ports) == 3
        assert "11" in sym.ports
        assert "12" in sym.ports
        assert "14" in sym.ports

    def test_pole_horizontal_spacing(self):
        """Each successive pole should be offset by SPDT_POLE_SPACING (40mm)."""
        sym = spdt_contact(poles=3)
        x1 = sym.ports["11"].position.x
        x2 = sym.ports["21"].position.x
        x3 = sym.ports["31"].position.x
        assert abs(x2 - x1 - 40.0) < 0.001
        assert abs(x3 - x2 - 40.0) < 0.001

    def test_default_pins(self):
        """Default pins follow IEC numbering: 11,12,14, 21,22,24, 31,32,34."""
        sym = spdt_contact(poles=3)
        # Should not raise and should have 9 ports
        assert len(sym.ports) == 9

    def test_custom_pins(self):
        """Custom pin labels should be accepted."""
        pins = ("A", "B", "C", "D", "E", "F", "G", "H", "I")
        sym = spdt_contact(poles=3, pins=pins)
        assert len(sym.ports) == 9

    def test_no_label(self):
        sym = spdt_contact(poles=2)
        assert sym.label == ""

    def test_elements_present(self):
        sym = spdt_contact(poles=3, label="-K1")
        assert len(sym.elements) > 0

    def test_short_pins_padded(self):
        """If fewer pins than expected are provided, they should be padded."""
        # 3 poles need 9 pins; provide only 6
        sym = spdt_contact(poles=3, pins=("1", "2", "4", "5", "6", "7"))
        assert len(sym.ports) == 9


# ──────────────────────────────────────────────────────────────────────
#  Multi-Pole Terminal Symbol (terminals.py)
# ──────────────────────────────────────────────────────────────────────


class TestMultiPoleTerminalSymbol:
    """Tests for terminal with poles > 1."""

    def test_basic_two_pole(self):
        """Two-pole terminal returns a TerminalBlock with 4 ports."""
        sym = terminal(label="X1", pins=("1", "2"), poles=2)
        assert isinstance(sym, TerminalBlock)
        assert isinstance(sym, Symbol)
        assert sym.label == "X1"
        # 2 poles x 2 ports (top + bottom) = 4
        assert len(sym.ports) == 4

    def test_port_ids_sequential(self):
        """Ports should be numbered sequentially: 1,2,3,4 for 2 poles."""
        sym = terminal(pins=("A", "B"), poles=2)
        assert "1" in sym.ports  # pole 1 top
        assert "2" in sym.ports  # pole 1 bottom
        assert "3" in sym.ports  # pole 2 top
        assert "4" in sym.ports  # pole 2 bottom

    def test_four_pole(self):
        """Four-pole terminal should have 8 ports."""
        sym = terminal(label="X2", pins=("1", "2", "3", "4"), poles=4)
        assert len(sym.ports) == 8

    def test_pole_spacing(self):
        """Poles should be spaced at DEFAULT_POLE_SPACING (10mm)."""
        sym = terminal(pins=("1", "2", "3"), poles=3)
        # Ports 1, 3, 5 are the top ports of poles 1, 2, 3
        x1 = sym.ports["1"].position.x
        x3 = sym.ports["3"].position.x
        x5 = sym.ports["5"].position.x
        assert abs(x3 - x1 - 10.0) < 0.001
        assert abs(x5 - x3 - 10.0) < 0.001

    def test_no_label(self):
        sym = terminal(poles=2)
        assert sym.label == ""

    def test_elements_present(self):
        sym = terminal(label="X1", pins=("1", "2"), poles=2)
        assert len(sym.elements) > 0

    def test_pins_padded_if_short(self):
        """If fewer pins than poles are given, padding with empty strings."""
        sym = terminal(pins=("1",), poles=3)
        assert len(sym.ports) == 6  # 3 poles x 2 ports

    def test_invalid_poles_raises(self):
        """poles < 1 should raise ValueError."""
        with pytest.raises(ValueError, match="poles"):
            terminal(poles=0)

    def test_invalid_label_pos_raises(self):
        """Invalid label_pos should raise ValueError."""
        with pytest.raises(ValueError, match="label_pos"):
            terminal(poles=2, label_pos="center")

    def test_label_pos_right(self):
        """label_pos='right' should be accepted without error."""
        sym = terminal(label="X1", poles=2, label_pos="right")
        assert sym.label == "X1"

    def test_pin_label_pos_right(self):
        """pin_label_pos='right' should be accepted."""
        sym = terminal(label="X1", pins=("1", "2"), poles=2, pin_label_pos="right")
        assert len(sym.ports) == 4


class TestTerminalSymbolValidation:
    """Tests for input validation in terminal()."""

    def test_invalid_label_pos_raises(self):
        """terminal with invalid label_pos should raise ValueError."""
        with pytest.raises(ValueError, match="label_pos must be 'left' or 'right'"):
            terminal(label="X1", pins=("1",), label_pos="center")

    def test_invalid_label_pos_top_raises(self):
        """terminal with label_pos='top' should raise ValueError."""
        with pytest.raises(ValueError, match="label_pos must be 'left' or 'right'"):
            terminal(label="X1", label_pos="top")

    def test_valid_label_pos_left(self):
        """terminal with label_pos='left' should succeed."""
        sym = terminal(label="X1", pins=("1",), label_pos="left")
        assert sym.label == "X1"

    def test_valid_label_pos_right(self):
        """terminal with label_pos='right' should succeed."""
        sym = terminal(label="X1", pins=("1",), label_pos="right")
        assert sym.label == "X1"


# ──────────────────────────────────────────────────────────────────────
#  Terminal Box Symbol (blocks.py)
# ──────────────────────────────────────────────────────────────────────


class TestTerminalBoxSymbol:
    """Tests for terminal_box."""

    def test_basic_creation(self):
        """Terminal box with 3 pins returns a Symbol with 3 ports."""
        sym = terminal_box(label="TB1", num_pins=3)
        assert isinstance(sym, Symbol)
        assert sym.label == "TB1"
        assert len(sym.ports) == 3

    def test_port_ids_from_start_number(self):
        """Default pins should be numbered from start_pin_number."""
        sym = terminal_box(num_pins=3, start_pin_number=1)
        assert "1" in sym.ports
        assert "2" in sym.ports
        assert "3" in sym.ports

    def test_custom_start_pin_number(self):
        """Custom start_pin_number should shift the port IDs."""
        sym = terminal_box(num_pins=2, start_pin_number=5)
        assert "5" in sym.ports
        assert "6" in sym.ports

    def test_explicit_pins(self):
        """Explicit pins parameter overrides num_pins and start_pin_number."""
        sym = terminal_box(pins=("A", "B", "C"))
        assert len(sym.ports) == 3
        assert "A" in sym.ports
        assert "B" in sym.ports
        assert "C" in sym.ports

    def test_single_pin(self):
        """A single-pin terminal box should work."""
        sym = terminal_box(num_pins=1)
        assert len(sym.ports) == 1

    def test_ports_point_upward(self):
        """All ports should have direction pointing upward (dy=-1)."""
        sym = terminal_box(num_pins=3)
        for port in sym.ports.values():
            assert port.direction.dy == -1

    def test_pin_spacing(self):
        """Pins should be spaced at the given pin_spacing (default 10mm)."""
        sym = terminal_box(num_pins=3, pin_spacing=10.0)
        port_xs = sorted(p.position.x for p in sym.ports.values())
        assert abs(port_xs[1] - port_xs[0] - 10.0) < 0.001
        assert abs(port_xs[2] - port_xs[1] - 10.0) < 0.001

    def test_custom_pin_spacing(self):
        """Custom spacing should be respected."""
        sym = terminal_box(num_pins=2, pin_spacing=20.0)
        port_xs = sorted(p.position.x for p in sym.ports.values())
        assert abs(port_xs[1] - port_xs[0] - 20.0) < 0.001

    def test_label_present_in_elements(self):
        sym_with = terminal_box(label="TB1", num_pins=2)
        sym_without = terminal_box(label="", num_pins=2)
        assert len(sym_with.elements) > len(sym_without.elements)

    def test_no_label(self):
        sym = terminal_box(num_pins=2)
        assert sym.label == ""

    def test_elements_present(self):
        """Should have at least the box rectangle plus pin lines and labels."""
        sym = terminal_box(num_pins=3)
        # 1 rect + 3 pin lines + 3 pin labels = 7 minimum
        assert len(sym.elements) >= 7


# ──────────────────────────────────────────────────────────────────────
#  Dynamic Block Symbol (blocks.py)
# ──────────────────────────────────────────────────────────────────────


class TestDynamicBlockSymbol:
    """Tests for block."""

    def test_basic_creation(self):
        """Dynamic block with top and bottom pins returns correct ports."""
        sym = block(label="U1", top_pins=("L", "N", "PE"), bottom_pins=("24V", "GND"))
        assert isinstance(sym, Symbol)
        assert sym.label == "U1"

    def test_top_pin_ports(self):
        """Top pin labels should appear as port IDs."""
        sym = block(top_pins=("L", "N", "PE"))
        assert "L" in sym.ports
        assert "N" in sym.ports
        assert "PE" in sym.ports

    def test_bottom_pin_ports(self):
        """Bottom pin labels should appear as port IDs."""
        sym = block(bottom_pins=("24V", "GND"))
        assert "24V" in sym.ports
        assert "GND" in sym.ports

    def test_standard_aliases(self):
        """Standard numeric aliases should be created for top/bottom pins."""
        sym = block(top_pins=("L", "N", "PE"), bottom_pins=("24V", "GND"))
        # Top pins get odd aliases: 1, 3, 5
        assert "1" in sym.ports
        assert "3" in sym.ports
        assert "5" in sym.ports
        # Bottom pins get even aliases: 2, 4
        assert "2" in sym.ports
        assert "4" in sym.ports

    def test_top_pins_point_upward(self):
        """Top pin ports should point upward (dy=-1)."""
        sym = block(top_pins=("L", "N"))
        assert sym.ports["L"].direction.dy == -1
        assert sym.ports["N"].direction.dy == -1

    def test_bottom_pins_point_downward(self):
        """Bottom pin ports should point downward (dy=1)."""
        sym = block(bottom_pins=("24V", "GND"))
        assert sym.ports["24V"].direction.dy == 1
        assert sym.ports["GND"].direction.dy == 1

    def test_top_pin_above_bottom_pin(self):
        """Top pins should be above (smaller Y) than bottom pins."""
        sym = block(top_pins=("L",), bottom_pins=("24V",))
        top_y = sym.ports["L"].position.y
        bot_y = sym.ports["24V"].position.y
        assert top_y < bot_y

    def test_no_pins(self):
        """Block with no pins should still create a minimal symbol."""
        sym = block(label="U1")
        assert isinstance(sym, Symbol)
        assert len(sym.ports) == 0

    def test_only_top_pins(self):
        """Block with only top pins should work."""
        sym = block(top_pins=("A", "B"))
        assert "A" in sym.ports
        assert "B" in sym.ports
        assert len(sym.ports) >= 2

    def test_only_bottom_pins(self):
        """Block with only bottom pins should work."""
        sym = block(bottom_pins=("X", "Y"))
        assert "X" in sym.ports
        assert "Y" in sym.ports
        assert len(sym.ports) >= 2

    def test_pin_spacing(self):
        """Pins should be spaced at pin_spacing intervals."""
        sym = block(top_pins=("A", "B", "C"), pin_spacing=15.0)
        xa = sym.ports["A"].position.x
        xb = sym.ports["B"].position.x
        xc = sym.ports["C"].position.x
        assert abs(xb - xa - 15.0) < 0.001
        assert abs(xc - xb - 15.0) < 0.001

    def test_explicit_top_pin_positions(self):
        """Explicit pin positions override uniform spacing."""
        sym = block(top_pins=("A", "B", "C"), top_pin_positions=(0.0, 10.0, 30.0))
        assert abs(sym.ports["A"].position.x - 0.0) < 0.001
        assert abs(sym.ports["B"].position.x - 10.0) < 0.001
        assert abs(sym.ports["C"].position.x - 30.0) < 0.001

    def test_explicit_bottom_pin_positions(self):
        """Explicit bottom pin positions override uniform spacing."""
        sym = block(bottom_pins=("X", "Y"), bottom_pin_positions=(5.0, 25.0))
        assert abs(sym.ports["X"].position.x - 5.0) < 0.001
        assert abs(sym.ports["Y"].position.x - 25.0) < 0.001

    def test_mismatched_pin_positions_raises(self):
        """Mismatched top_pin_positions length should raise ValueError."""
        with pytest.raises(ValueError, match="top_pin_positions"):
            block(top_pins=("A", "B"), top_pin_positions=(0.0, 10.0, 20.0))

    def test_mismatched_bottom_pin_positions_raises(self):
        """Mismatched bottom_pin_positions length should raise ValueError."""
        with pytest.raises(ValueError, match="bottom_pin_positions"):
            block(bottom_pins=("X",), bottom_pin_positions=(0.0, 10.0))

    def test_no_label(self):
        sym = block(top_pins=("L",))
        assert sym.label == ""

    def test_label_present_in_elements(self):
        sym_with = block(label="U1", top_pins=("L",))
        sym_without = block(label="", top_pins=("L",))
        assert len(sym_with.elements) > len(sym_without.elements)

    def test_elements_present(self):
        sym = block(label="U1", top_pins=("L", "N"), bottom_pins=("24V",))
        assert len(sym.elements) > 0


# ──────────────────────────────────────────────────────────────────────
#  Current Transducer Symbols (transducers.py)
# ──────────────────────────────────────────────────────────────────────


class TestCurrentTransducerSymbol:
    """Tests for ct."""

    def test_basic_creation(self):
        """Current transducer returns a Symbol with no ports."""
        sym = ct()
        assert isinstance(sym, Symbol)
        assert len(sym.ports) == 0

    def test_label_empty(self):
        """Current transducer always has empty label."""
        sym = ct()
        assert sym.label == ""

    def test_has_elements(self):
        """Should have at least a circle and a line."""
        sym = ct()
        assert len(sym.elements) == 2


class TestCurrentTransducerAssemblySymbol:
    """Tests for ct_assembly."""

    def test_basic_creation(self):
        """Assembly returns a Symbol with ports from the terminal box."""
        sym = ct_assembly(label="CT1", pins=("1", "2"))
        assert isinstance(sym, Symbol)
        assert sym.label == "CT1"
        assert len(sym.ports) > 0

    def test_has_ports_from_terminal_box(self):
        """Ports should come from the terminal box (transducer has none)."""
        sym = ct_assembly(pins=("1", "2"))
        assert "1" in sym.ports
        assert "2" in sym.ports

    def test_combined_elements(self):
        """Assembly should have elements from both transducer and terminal box."""
        ct_sym = ct()
        box_sym = terminal_box(pins=("1", "2"))
        assembly = ct_assembly(pins=("1", "2"))
        # Assembly should have at least as many elements as both sub-symbols combined
        assert len(assembly.elements) >= len(ct_sym.elements) + len(box_sym.elements)

    def test_no_label(self):
        sym = ct_assembly()
        assert sym.label == ""

    def test_custom_pins(self):
        """Custom pins should be passed through to the terminal box."""
        sym = ct_assembly(pins=("A", "B", "C"))
        assert "A" in sym.ports
        assert "B" in sym.ports
        assert "C" in sym.ports

    def test_elements_present(self):
        sym = ct_assembly(label="CT1", pins=("1", "2"))
        assert len(sym.elements) > 0

    def test_port_positions_offset_left(self):
        """Terminal box ports should be to the left of the transducer origin."""
        sym = ct_assembly(pins=("1", "2"))
        for port in sym.ports.values():
            # All terminal box ports should be to the left of x=0
            # (transducer circle center)
            assert port.position.x < 0
