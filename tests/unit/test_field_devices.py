"""
Unit tests for the field_devices module.

Tests cover the PinDef, DeviceTemplate, and generate_field_connections()
function with all three pin numbering modes: sequential, prefixed, and fixed.
"""

import pytest

from schematika.electrical.field_devices import (
    DeviceTemplate,
    FieldDevice,
    FixedPin,
    PinDef,
    PrefixedPin,
    SequentialPin,
    generate_field_connections,
)
from schematika.electrical.terminal import Terminal


def _fd(tag, template, terminal=None):
    """Shorthand for FieldDevice in tests."""
    return FieldDevice(tag, template, terminal=terminal)


# ---------------------------------------------------------------------------
# Fixtures: reusable terminals and templates
# ---------------------------------------------------------------------------


@pytest.fixture
def signal_terminal():
    return Terminal("X100", "Signal terminal")


@pytest.fixture
def power_terminal():
    return Terminal("X200", "Power terminal", pin_prefixes=("L1", "L2", "L3", "N"))


@pytest.fixture
def plc_ai():
    return Terminal("PLC:AI", "PLC Analog Input", reference=True)


@pytest.fixture
def plc_di():
    return Terminal("PLC:DI", "PLC Digital Input", reference=True)


@pytest.fixture
def ext_gnd():
    return Terminal("X300", "External GND")


# ---------------------------------------------------------------------------
# PinDef / DeviceTemplate construction
# ---------------------------------------------------------------------------


class TestPinDef:
    """Tests for the PinDef frozen dataclass."""

    def test_defaults(self):
        pin = PinDef("Sig+")
        assert pin.device_pin == "Sig+"
        assert pin.terminal is None
        assert pin.plc is None
        assert pin.terminal_pin == ""
        assert pin.pin_prefix == ""

    def test_with_terminal_and_plc(self, signal_terminal, plc_ai):
        pin = PinDef("Sig+", signal_terminal, plc_ai)
        assert pin.terminal is signal_terminal
        assert pin.plc is plc_ai

    def test_with_fixed_pin(self):
        pin = PinDef("U1", terminal_pin="L1")
        assert pin.terminal_pin == "L1"

    def test_with_prefix(self):
        pin = PinDef("L1", pin_prefix="L1")
        assert pin.pin_prefix == "L1"

    def test_frozen(self, signal_terminal):
        pin = PinDef("Sig+", signal_terminal)
        with pytest.raises(AttributeError):
            pin.device_pin = "GND"  # type: ignore[misc]


class TestDeviceTemplate:
    """Tests for the DeviceTemplate frozen dataclass."""

    def test_construction(self, signal_terminal, plc_ai):
        template = DeviceTemplate(
            mpn="4-20mA Sensor",
            pins=(
                PinDef("Sig+", signal_terminal, plc_ai),
                PinDef("GND", signal_terminal),
            ),
        )
        assert template.mpn == "4-20mA Sensor"
        assert len(template.pins) == 2
        assert template.pins[0].device_pin == "Sig+"
        assert template.pins[1].device_pin == "GND"

    def test_frozen(self, signal_terminal):
        template = DeviceTemplate(
            mpn="Test",
            pins=(PinDef("1", signal_terminal),),
        )
        with pytest.raises(AttributeError):
            template.mpn = "Other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# PinDef typed subclasses
# ---------------------------------------------------------------------------


class TestPinDefSubclasses:
    """Tests for SequentialPin, PrefixedPin, and FixedPin typed subclasses."""

    # SequentialPin

    def test_sequential_pin_valid_creation(self, signal_terminal):
        """SequentialPin can be created with just device_pin."""
        pin = SequentialPin("Sig+", signal_terminal)
        assert pin.device_pin == "Sig+"
        assert pin.pin_prefix == ""
        assert pin.terminal_pin == ""
        assert isinstance(pin, PinDef)

    def test_sequential_pin_rejects_pin_prefix(self, signal_terminal):
        """SequentialPin raises ValueError if pin_prefix is set."""
        with pytest.raises(ValueError, match="pin_prefix must be empty"):
            SequentialPin("Sig+", signal_terminal, pin_prefix="L1")

    def test_sequential_pin_rejects_terminal_pin(self, signal_terminal):
        """SequentialPin raises ValueError if terminal_pin is set."""
        with pytest.raises(ValueError, match="terminal_pin must be empty"):
            SequentialPin("Sig+", signal_terminal, terminal_pin="L1")

    # PrefixedPin

    def test_prefixed_pin_valid_creation(self, power_terminal):
        """PrefixedPin can be created with device_pin and pin_prefix."""
        pin = PrefixedPin("L1", power_terminal, pin_prefix="L1")
        assert pin.device_pin == "L1"
        assert pin.pin_prefix == "L1"
        assert pin.terminal_pin == ""
        assert isinstance(pin, PinDef)

    def test_prefixed_pin_requires_pin_prefix(self, power_terminal):
        """PrefixedPin raises ValueError if pin_prefix is empty."""
        with pytest.raises(ValueError, match="pin_prefix is required"):
            PrefixedPin("L1", power_terminal)

    def test_prefixed_pin_rejects_terminal_pin(self, power_terminal):
        """PrefixedPin raises ValueError if terminal_pin is set."""
        with pytest.raises(ValueError, match="terminal_pin must be empty"):
            PrefixedPin("L1", power_terminal, pin_prefix="L1", terminal_pin="L1")

    # FixedPin

    def test_fixed_pin_valid_creation(self, signal_terminal):
        """FixedPin can be created with device_pin and terminal_pin."""
        pin = FixedPin("U1", signal_terminal, terminal_pin="L1")
        assert pin.device_pin == "U1"
        assert pin.terminal_pin == "L1"
        assert pin.pin_prefix == ""
        assert isinstance(pin, PinDef)

    def test_fixed_pin_requires_terminal_pin(self, signal_terminal):
        """FixedPin raises ValueError if terminal_pin is empty."""
        with pytest.raises(ValueError, match="terminal_pin is required"):
            FixedPin("U1", signal_terminal)

    def test_fixed_pin_rejects_pin_prefix(self, signal_terminal):
        """FixedPin raises ValueError if pin_prefix is set."""
        with pytest.raises(ValueError, match="pin_prefix must be empty"):
            FixedPin("U1", signal_terminal, terminal_pin="L1", pin_prefix="L1")

    # Mixed template

    def test_subclasses_work_in_device_template(
        self, signal_terminal, power_terminal, plc_ai
    ):
        """DeviceTemplate mixing all three subclasses works with generate_field_connections."""  # noqa: E501
        template = DeviceTemplate(
            mpn="Complex Device",
            pins=(
                SequentialPin("Sig+", signal_terminal, plc_ai),
                SequentialPin("GND", signal_terminal),
                PrefixedPin("L1", power_terminal, pin_prefix="L1"),
                PrefixedPin("L2", power_terminal, pin_prefix="L2"),
                FixedPin("PE", power_terminal, terminal_pin="PE"),
            ),
        )
        rows = generate_field_connections([_fd("DEV-01", template)])

        assert len(rows) == 5
        # SequentialPin rows: auto-numbered on signal_terminal
        assert rows[0] == ("DEV-01", "Sig+", signal_terminal, "1", "PLC:AI", "")
        assert rows[1] == ("DEV-01", "GND", signal_terminal, "2", "", "")
        # PrefixedPin rows: group 1 on power_terminal
        assert rows[2] == ("DEV-01", "L1", power_terminal, "L1:1", "", "")
        assert rows[3] == ("DEV-01", "L2", power_terminal, "L2:1", "", "")
        # FixedPin row: literal "PE"
        assert rows[4] == ("DEV-01", "PE", power_terminal, "PE", "", "")


# ---------------------------------------------------------------------------
# Sequential pin numbering (default mode)
# ---------------------------------------------------------------------------


class TestSequentialPins:
    """Tests for auto-numbered sequential pins."""

    def test_single_device(self, signal_terminal, plc_ai):
        """Single device with two pins on same terminal auto-numbers 1, 2."""
        template = DeviceTemplate(
            mpn="4-20mA",
            pins=(
                PinDef("Sig+", signal_terminal, plc_ai),
                PinDef("GND", signal_terminal),
            ),
        )
        rows = generate_field_connections([_fd("PT-01", template)])

        assert len(rows) == 2
        # Row structure: (tag, device_pin, terminal, terminal_pin, plc_tag, "")
        assert rows[0] == ("PT-01", "Sig+", signal_terminal, "1", "PLC:AI", "")
        assert rows[1] == ("PT-01", "GND", signal_terminal, "2", "", "")

    def test_multiple_devices_same_terminal(self, signal_terminal, plc_ai):
        """Multiple devices on the same terminal continue numbering."""
        template = DeviceTemplate(
            mpn="4-20mA",
            pins=(
                PinDef("Sig+", signal_terminal, plc_ai),
                PinDef("GND", signal_terminal),
            ),
        )
        rows = generate_field_connections(
            [
                _fd("PT-01", template),
                _fd("PT-02", template),
            ]
        )

        assert len(rows) == 4
        # First device gets pins 1, 2
        assert rows[0][3] == "1"
        assert rows[1][3] == "2"
        # Second device continues with 3, 4
        assert rows[2][3] == "3"
        assert rows[3][3] == "4"

    def test_different_terminals(self, signal_terminal, ext_gnd, plc_di):
        """Pins on different terminals have independent counters."""
        template = DeviceTemplate(
            mpn="Level Switch",
            pins=(
                PinDef("1", signal_terminal, plc_di),
                PinDef("2", ext_gnd),
            ),
        )
        rows = generate_field_connections(
            [
                _fd("LS-01", template),
                _fd("LS-02", template),
            ]
        )

        assert len(rows) == 4
        # X100 pins: 1, 2 (from LS-01 pin "1" and LS-02 pin "1")
        assert rows[0][3] == "1"  # LS-01, X100
        assert rows[2][3] == "2"  # LS-02, X100
        # X300 pins: 1, 2 (independent counter)
        assert rows[1][3] == "1"  # LS-01, X300
        assert rows[3][3] == "2"  # LS-02, X300


# ---------------------------------------------------------------------------
# Prefixed pin numbering (pin_prefix mode)
# ---------------------------------------------------------------------------


class TestPrefixedPins:
    """Tests for prefix-based group numbering."""

    def test_single_device_prefixed(self):
        """Prefixed pins format as prefix:group_number."""
        terminal = Terminal("X200", "Power")
        template = DeviceTemplate(
            mpn="400V 3P+N",
            pins=(
                PinDef("L1", terminal, pin_prefix="L1"),
                PinDef("L2", terminal, pin_prefix="L2"),
                PinDef("L3", terminal, pin_prefix="L3"),
                PinDef("N", terminal, pin_prefix="N"),
            ),
        )
        rows = generate_field_connections([_fd("400V Main", template)])

        assert len(rows) == 4
        assert rows[0][3] == "L1:1"
        assert rows[1][3] == "L2:1"
        assert rows[2][3] == "L3:1"
        assert rows[3][3] == "N:1"

    def test_multiple_devices_prefixed(self):
        """Multiple devices with same prefixes increment the group number."""
        terminal = Terminal("X200", "Power")
        template = DeviceTemplate(
            mpn="230V 3P",
            pins=(
                PinDef("L1", terminal, pin_prefix="L1"),
                PinDef("L2", terminal, pin_prefix="L2"),
                PinDef("L3", terminal, pin_prefix="L3"),
            ),
        )
        rows = generate_field_connections(
            [
                _fd("Feed A", template),
                _fd("Feed B", template),
            ]
        )

        assert len(rows) == 6
        # First device: group 1
        assert rows[0][3] == "L1:1"
        assert rows[1][3] == "L2:1"
        assert rows[2][3] == "L3:1"
        # Second device: group 2
        assert rows[3][3] == "L1:2"
        assert rows[4][3] == "L2:2"
        assert rows[5][3] == "L3:2"

    def test_partial_prefix_overlap(self):
        """Devices using different subsets of prefixes on same terminal."""
        terminal = Terminal("X200", "Power")
        template_full = DeviceTemplate(
            mpn="400V 3P+N",
            pins=(
                PinDef("L1", terminal, pin_prefix="L1"),
                PinDef("L2", terminal, pin_prefix="L2"),
                PinDef("L3", terminal, pin_prefix="L3"),
                PinDef("N", terminal, pin_prefix="N"),
            ),
        )
        template_n_only = DeviceTemplate(
            mpn="N-only device",
            pins=(
                PinDef("A1", terminal, pin_prefix="N"),
                PinDef("A2", terminal, pin_prefix="L1"),
            ),
        )
        rows = generate_field_connections(
            [
                _fd("Dev A", template_full),
                _fd("Dev B", template_n_only),
            ]
        )

        # Dev A: all prefixes get group 1
        assert rows[0][3] == "L1:1"
        assert rows[1][3] == "L2:1"
        assert rows[2][3] == "L3:1"
        assert rows[3][3] == "N:1"
        # Dev B: uses N and L1, max(N=1, L1=1) + 1 = 2
        assert rows[4][3] == "N:2"
        assert rows[5][3] == "L1:2"


# ---------------------------------------------------------------------------
# Fixed pin numbering (terminal_pin mode)
# ---------------------------------------------------------------------------


class TestFixedPins:
    """Tests for fixed terminal pin names."""

    def test_fixed_pins(self):
        """Fixed terminal_pin values are used directly, not auto-numbered."""
        terminal = Terminal("X500", "Motor terminal")
        template = DeviceTemplate(
            mpn="Pump 3P",
            pins=(
                PinDef("U1", terminal, terminal_pin="L1"),
                PinDef("V1", terminal, terminal_pin="L2"),
                PinDef("W1", terminal, terminal_pin="L3"),
            ),
        )
        rows = generate_field_connections([_fd("PU-01", template)])

        assert len(rows) == 3
        assert rows[0][3] == "L1"
        assert rows[1][3] == "L2"
        assert rows[2][3] == "L3"

    def test_fixed_pins_do_not_affect_sequential(self, signal_terminal):
        """Fixed pins don't increment the sequential counter."""
        terminal = Terminal("X500", "Motor terminal")
        fixed_template = DeviceTemplate(
            mpn="Motor",
            pins=(PinDef("U1", terminal, terminal_pin="L1"),),
        )
        seq_template = DeviceTemplate(
            mpn="Sensor",
            pins=(PinDef("1", terminal),),
        )
        rows = generate_field_connections(
            [
                _fd("M-01", fixed_template),
                _fd("S-01", seq_template),
            ]
        )

        assert rows[0][3] == "L1"  # fixed
        assert rows[1][3] == "1"  # sequential starts at 1


# ---------------------------------------------------------------------------
# Terminal override
# ---------------------------------------------------------------------------


class TestTerminalOverride:
    """Tests for the terminal_override in DeviceEntry tuples."""

    def test_override_fills_missing_terminals(self):
        """PinDef without terminal uses the override from DeviceEntry."""
        override = Terminal("X400", "Override terminal")
        template = DeviceTemplate(
            mpn="Motor",
            pins=(
                PinDef("U1", terminal_pin="L1"),
                PinDef("V1", terminal_pin="L2"),
            ),
        )
        rows = generate_field_connections([_fd("M-01", template, override)])

        assert len(rows) == 2
        assert rows[0][2] is override
        assert rows[1][2] is override

    def test_pindef_terminal_takes_precedence(self):
        """PinDef terminal is used even when override is provided."""
        override = Terminal("X400", "Override")
        specific = Terminal("X500", "Specific")
        template = DeviceTemplate(
            mpn="Mixed",
            pins=(
                PinDef("1", specific),
                PinDef("2"),  # No terminal, will use override
            ),
        )
        rows = generate_field_connections([_fd("D-01", template, override)])

        assert rows[0][2] is specific
        assert rows[1][2] is override


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrors:
    """Tests for error conditions."""

    def test_missing_terminal_raises(self):
        """Raises ValueError when pin has no terminal and no override."""
        template = DeviceTemplate(
            mpn="Bad",
            pins=(PinDef("1"),),
        )
        with pytest.raises(ValueError, match="no terminal in template"):
            generate_field_connections([_fd("D-01", template)])


# ---------------------------------------------------------------------------
# PLC reference tagging
# ---------------------------------------------------------------------------


class TestPlcReferences:
    """Tests for PLC reference tags in connection rows."""

    def test_plc_tag_present(self, signal_terminal, plc_ai):
        template = DeviceTemplate(
            mpn="Sensor",
            pins=(PinDef("Sig+", signal_terminal, plc_ai),),
        )
        rows = generate_field_connections([_fd("PT-01", template)])
        assert rows[0][4] == "PLC:AI"

    def test_plc_tag_absent(self, signal_terminal):
        template = DeviceTemplate(
            mpn="Sensor",
            pins=(PinDef("GND", signal_terminal),),
        )
        rows = generate_field_connections([_fd("PT-01", template)])
        assert rows[0][4] == ""


# ---------------------------------------------------------------------------
# Reuse terminals
# ---------------------------------------------------------------------------


class TestReuseTerminals:
    """Tests for the reuse_terminals parameter."""

    def test_reuse_from_list(self, signal_terminal, plc_ai):
        """Reuse pins from an explicit list."""
        template = DeviceTemplate(
            mpn="4-20mA",
            pins=(
                PinDef("Sig+", signal_terminal, plc_ai),
                PinDef("GND", signal_terminal),
            ),
        )
        rows = generate_field_connections(
            [_fd("PT-01", template)],
            reuse_terminals={"X100": ["42", "43"]},
        )

        assert rows[0][3] == "42"
        assert rows[1][3] == "43"

    def test_reuse_does_not_affect_other_terminals(
        self, signal_terminal, ext_gnd, plc_di
    ):
        """Reuse on one terminal doesn't affect sequential on another."""
        template = DeviceTemplate(
            mpn="Level Switch",
            pins=(
                PinDef("1", signal_terminal, plc_di),
                PinDef("2", ext_gnd),
            ),
        )
        rows = generate_field_connections(
            [_fd("LS-01", template)],
            reuse_terminals={"X100": ["99"]},
        )

        assert rows[0][3] == "99"  # reused
        assert rows[1][3] == "1"  # sequential


# ---------------------------------------------------------------------------
# Mixed numbering modes in one template
# ---------------------------------------------------------------------------


class TestMixedModes:
    """Tests for templates with mixed pin numbering modes."""

    def test_mixed_fixed_and_sequential(self):
        """A template with both fixed and sequential pins."""
        terminal = Terminal("X600", "Mixed terminal")
        template = DeviceTemplate(
            mpn="Complex Valve",
            pins=(
                PinDef("A1", terminal, pin_prefix="N"),
                PinDef("A2", terminal, pin_prefix="L"),
                PinDef("B1", terminal),  # sequential
            ),
        )
        rows = generate_field_connections([_fd("XV-01", template)])

        assert rows[0][3] == "N:1"
        assert rows[1][3] == "L:1"
        assert rows[2][3] == "1"  # sequential counter starts at 1


# ---------------------------------------------------------------------------
# ConnectionRow structure
# ---------------------------------------------------------------------------


class TestConnectionRowStructure:
    """Tests for the ConnectionRow tuple structure."""

    def test_row_has_six_fields(self, signal_terminal):
        template = DeviceTemplate(
            mpn="Simple",
            pins=(PinDef("1", signal_terminal),),
        )
        rows = generate_field_connections([_fd("D-01", template)])
        assert len(rows) == 1
        assert len(rows[0]) == 6

    def test_row_fields_are_correct_types(self, signal_terminal, plc_ai):
        template = DeviceTemplate(
            mpn="Simple",
            pins=(PinDef("1", signal_terminal, plc_ai),),
        )
        rows = generate_field_connections([_fd("D-01", template)])
        row = rows[0]
        assert isinstance(row[0], str)  # tag
        assert isinstance(row[1], str)  # device_pin
        assert row[2] is signal_terminal  # terminal object
        assert isinstance(row[3], str)  # terminal_pin
        assert isinstance(row[4], str)  # plc_tag
        assert isinstance(row[5], str)  # reserved (empty)
        assert row[5] == ""


# ---------------------------------------------------------------------------
# Empty input
# ---------------------------------------------------------------------------


class TestEmptyInput:
    """Tests for edge cases with empty input."""

    def test_empty_device_list(self):
        rows = generate_field_connections([])
        assert rows == []


# ---------------------------------------------------------------------------
# Template-scoped terminal reuse
# ---------------------------------------------------------------------------


class TestTemplateReuse:
    """Tests for the template_reuse parameter on generate_field_connections."""

    def test_matched_devices_get_reused_pins(self):
        """Devices whose template matches get pins from the reuse source."""
        shared = Terminal("X13", "Shared I/O")
        fan_tmpl = DeviceTemplate(
            "Fan", pins=(PinDef("t1", shared), PinDef("t2", shared))
        )

        rows = generate_field_connections(
            [_fd("F-01", fan_tmpl), _fd("F-02", fan_tmpl)],
            template_reuse={fan_tmpl: {"X13": ["5", "6", "7", "8"]}},
        )

        assert rows[0][3] == "5"  # F-01 t1
        assert rows[1][3] == "6"  # F-01 t2
        assert rows[2][3] == "7"  # F-02 t1
        assert rows[3][3] == "8"  # F-02 t2

    def test_non_matched_devices_skip_reserved_pins(self):
        """Non-matching devices auto-number but skip reserved pin values."""
        shared = Terminal("X13", "Shared I/O")
        fan_tmpl = DeviceTemplate("Fan", pins=(PinDef("t1", shared),))
        switch_tmpl = DeviceTemplate("Switch", pins=(PinDef("1", shared),))

        rows = generate_field_connections(
            [
                _fd("S-01", switch_tmpl),  # auto: 1
                _fd("S-02", switch_tmpl),  # auto: 2 (3 reserved → skip)
                _fd("F-01", fan_tmpl),  # reused: 3
                _fd("S-03", switch_tmpl),  # auto: 4 (3 reserved → next is 4)
            ],
            template_reuse={fan_tmpl: {"X13": ["3"]}},
        )

        assert rows[0][3] == "1"  # S-01: auto, no skip
        assert rows[1][3] == "2"  # S-02: auto, no skip
        assert rows[2][3] == "3"  # F-01: reused
        assert rows[3][3] == "4"  # S-03: auto, skipped 3

    def test_template_reuse_with_global_reuse(self):
        """Template reuse and global reuse can coexist on different terminals."""
        io = Terminal("X13", "I/O")
        power = Terminal("X09", "Power")
        fan_tmpl = DeviceTemplate("Fan", pins=(PinDef("t1", io),))
        valve_tmpl = DeviceTemplate("Valve", pins=(PinDef("A1", power),))

        rows = generate_field_connections(
            [_fd("V-01", valve_tmpl), _fd("F-01", fan_tmpl)],
            reuse_terminals={"X09": ["42"]},
            template_reuse={fan_tmpl: {"X13": ["7"]}},
        )

        assert rows[0][3] == "42"  # V-01: global reuse on X09
        assert rows[1][3] == "7"  # F-01: template reuse on X13

    def test_template_reuse_does_not_affect_other_terminals(self):
        """Template reuse only applies to the specified terminal."""
        io = Terminal("X13", "I/O")
        other = Terminal("X14", "Other")
        tmpl = DeviceTemplate(
            "Fan",
            pins=(PinDef("t1", io), PinDef("s1", other)),
        )

        rows = generate_field_connections(
            [_fd("F-01", tmpl)],
            template_reuse={tmpl: {"X13": ["5"]}},
        )

        assert rows[0][3] == "5"  # X13: reused
        assert rows[1][3] == "1"  # X14: normal sequential

    def test_empty_template_reuse(self):
        """Empty template_reuse behaves like None."""
        shared = Terminal("X13", "I/O")
        tmpl = DeviceTemplate("Switch", pins=(PinDef("1", shared),))

        rows = generate_field_connections(
            [_fd("S-01", tmpl)],
            template_reuse={},
        )

        assert rows[0][3] == "1"

    def test_shared_iterator_across_templates(self):
        """Multiple templates referencing the same source share one iterator."""
        shared = Terminal("X13", "I/O")
        # Simulate fan_controll's 12 X13 pins
        reuse_pins = ["7", "8", "9", "10", "11", "12", "13", "14"]

        fan_tmpl = DeviceTemplate(
            "Fan", pins=(PinDef("t1", shared), PinDef("t2", shared))
        )
        switch_tmpl = DeviceTemplate("Switch (Fan)", pins=(PinDef("3", shared),))
        sensor_tmpl = DeviceTemplate("Sensor (Fan)", pins=(PinDef("10", shared),))

        rows = generate_field_connections(
            [
                _fd("F-01", fan_tmpl),  # t1→7, t2→8
                _fd("F-02", fan_tmpl),  # t1→9, t2→10
                _fd("S7", switch_tmpl),  # 3→11
                _fd("S8", switch_tmpl),  # 3→12
                _fd("G-01", sensor_tmpl),  # 10→13
                _fd("G-02", sensor_tmpl),  # 10→14
            ],
            template_reuse={
                fan_tmpl: {"X13": reuse_pins},
                switch_tmpl: {"X13": reuse_pins},
                sensor_tmpl: {"X13": reuse_pins},
            },
        )

        x13_pins = [r[3] for r in rows if str(r[2]) == "X13"]
        assert x13_pins == ["7", "8", "9", "10", "11", "12", "13", "14"]
