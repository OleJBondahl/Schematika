"""Global constants for the IEC Symbol Library.

All geometric and stylistic parameters should be defined here.
Contains library-level defaults including spacing, tags, and pin configurations.
Project-specific constants (terminal IDs, paths) should be defined in user projects.
"""

from typing import Literal

Position = Literal["below", "above", "left", "right"]
Side = Literal["top", "bottom"]
LabelPosition = Literal["left", "right"]

# Geometric/visual constants live in core/constants.py and are re-exported here
# so that all existing imports from model.constants continue to work unchanged.
from schematika.core.constants import (
    COLOR_BLACK,
    COLOR_WHITE,
    DEFAULT_DOC_HEIGHT,
    DEFAULT_DOC_WIDTH,
    DEFAULT_POLE_SPACING,
    GRID_SIZE,
    LINE_WIDTH_THIN,
    PIN_LABEL_OFFSET_X,
    PIN_LABEL_OFFSET_Y_ADJUST,
    TERMINAL_RADIUS,
    TERMINAL_TEXT_OFFSET_X,
    TERMINAL_TEXT_OFFSET_X_CLOSE,
    TERMINAL_TEXT_SIZE,
    TEXT_FONT_FAMILY,
    TEXT_FONT_FAMILY_AUX,
    TEXT_OFFSET_X,
    TEXT_SIZE_MAIN,
    TEXT_SIZE_PIN,
)

# Electrical-specific constants (not in core/)
GRID_SUBDIVISION = GRID_SIZE / 2  # 2.5mm, Half grid for smaller alignments

# Geometry (electrical-specific)  # noqa: ERA001
LINE_WIDTH_THICK = 0.1 * GRID_SIZE  # 0.5mm
LINKAGE_DASH_PATTERN = (
    f"{0.4 * GRID_SIZE}, {0.4 * GRID_SIZE}"  # "2.0, 2.0" Stippled/Dashed pattern
)

# Reference Symbol Geometry
REF_ARROW_LENGTH = 2 * GRID_SIZE  # 10.0mm
REF_ARROW_HEAD_LENGTH = 0.6 * GRID_SIZE  # 3.0mm
REF_ARROW_HEAD_WIDTH = 0.5 * GRID_SIZE  # 2.5mm

# Layout (electrical-specific)  # noqa: ERA001
SPDT_PIN_LABEL_OFFSET = 2.0  # 2.0mm, pin label offset for SPDT contacts
DEFAULT_WIRE_ALIGNMENT_TOLERANCE = 0.1  # 0.1mm strict tolerance for port matching
WIRE_LABEL_OFFSET_X = -GRID_SIZE / 2  # -2.5mm, horizontal offset for wire labels


class StandardTags:
    """Standard IEC component tag prefixes.

    Following IEC 61346-2 designation standards.
    """

    BREAKER = "F"  # Protective devices (Fuses, Circuit Breakers)
    CONTACTOR = "Q"  # Power switching devices
    RELAY = "K"  # Auxiliary relays and contactors
    SWITCH = "S"  # Control switches
    POWER_SUPPLY = "PSU"  # Generators and power supplies
    TRANSFORMER = "T"  # Transformers
    MOTOR = "M"  # Motors
    INDICATOR = "H"  # Indicator lamps
    BUTTON = "S"  # Push buttons (same as switches)
    SENSOR = "B"  # Sensors and transducers
    TERMINAL = "X"  # Terminal blocks


# Standard Pin Sets (IEC standard pins only — project-specific pins stay in projects)
COIL_PINS = ("A1", "A2")
NO_CONTACT_PINS = ("13", "14")
NC_CONTACT_PINS = ("11", "12")
CB_3P_PINS = ("1", "2", "3", "4", "5", "6")
CB_2P_PINS = ("1", "2", "3", "4")
CONTACTOR_3P_PINS = ("L1", "T1", "L2", "T2", "L3", "T3")
THERMAL_OVERLOAD_PINS = ("", "T1", "", "T2", "", "T3")
CB_1P_PINS = ("1", "2")
FUSE_1P_PINS = ("1", "2")
SPDT_1P_PINS = ("11", "12", "14")
SPDT_3P_PINS = ("11", "12", "14", "21", "22", "24", "31", "32", "34")
MOTOR_1P_PINS = ("1", "2")
MOTOR_3P_PINS = ("U", "V", "W", "PE")
ESTOP_PINS = ("1", "2")
TURN_SWITCH_PINS = ("1", "2")
CT_ASSEMBLY_PINS = ("1", "2")
TERMINAL_3P_PINS = ("1", "2", "3")


class PinPrefix:
    """Standard pin prefix tuples for terminal block declarations."""

    TN = ("L1", "L2", "L3", "N", "PE")
    IT = ("L1", "L2", "L3", "PE")
    SINGLEPHASE = ("L", "N", "PE")


class StandardCircuitKeys:
    """Standard logical keys for terminal mapping.

    These provide common abstractions for circuit connections.
    """

    # Power distribution
    MAIN = "MAIN"
    SUPPLY = "SUPPLY"
    OUTPUT = "OUTPUT"

    # Control power
    V24 = "V24"
    GND = "GND"

    # Generic I/O
    INPUT = "INPUT"
    INPUT_1 = "INPUT_1"
    INPUT_2 = "INPUT_2"
    OUTPUT_24V = "OUTPUT_24V"
    OUTPUT_GND = "OUTPUT_GND"


# =============================================================================
# Layout Constants
# =============================================================================
# These constants define geometric layout values used in standard circuit creation.
# They are derived from GRID_SIZE for consistency.


# Symbol / component spacing (ascending by value)
SPACING_COMPACT = 6 * GRID_SIZE  # 30mm — tight vertical layouts, feedback columns
SPACING_NARROW = 8 * GRID_SIZE  # 40mm — multi-pole SPDT / changeover pole spacing
SPACING_DEFAULT = 10 * GRID_SIZE  # 50mm — default builder symbol spacing
SPACING_STANDARD = 12 * GRID_SIZE  # 60mm — standard symbol / compact circuit spacing

# Circuit spacing (horizontal distance between circuit instances)
CIRCUIT_SPACING_NARROW = 15 * GRID_SIZE  # 75mm — single-pole / power-distribution
CIRCUIT_SPACING = 20 * GRID_SIZE  # 100mm — control / single-pole circuits
CIRCUIT_SPACING_WIDE = 30 * GRID_SIZE  # 150mm — motor / power circuits


# =============================================================================
# Wire Label Specifications (color + cross-section, IEC 60757)
# =============================================================================
from schematika.electrical.wire import wire as _wire


class WireLabels:
    """Predefined wire label constants for common colour/cross-section combinations."""

    RD_2_5 = _wire("RD", "2.5")
    BK_2_5 = _wire("BK", "2.5")
    RD_0_5 = _wire("RD", "0.5")
    BK_0_5 = _wire("BK", "0.5")
    WH_0_5 = _wire("WH", "0.5")
    BR_2_5 = _wire("BR", "2.5")
    GY_2_5 = _wire("GY", "2.5")
    BL_2_5 = _wire("BL", "2.5")
    GR_YE_2_5 = _wire("GR/YE", "2.5")
    BR_1_5 = _wire("BR", "1.5")
    BK_1_5 = _wire("BK", "1.5")
    GY_1_5 = _wire("GY", "1.5")
    BL_1_5 = _wire("BL", "1.5")
    EMPTY = _wire.EMPTY
