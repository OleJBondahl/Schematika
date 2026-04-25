"""P&ID constants — ISO 14617, ISA 5.1, and ISO 3098 compliance.

All dimensional constants are derived from :data:`GRID_SIZE` (5 mm) so that
proportions remain consistent with the electrical schematic module.

Standards Reference
-------------------

**ISO 14617 — Graphical symbols for diagrams**

*   *Line weight hierarchy* (Part 1, Clause 4):
    - Process pipe lines are the heaviest weight (``PID_LINE_WEIGHT`` 0.7 mm).
    - Equipment body outlines use a medium weight (``PID_EQUIPMENT_STROKE``
      0.5 mm).
    - Signal/instrument lines use the thinnest weight
      (``PID_SIGNAL_LINE_WEIGHT`` 0.25 mm).
    - Only these three weights should appear on a P&ID.  The validator
      (:func:`~schematika.pid.validation.validate_pid`) warns on any line
      that uses a non-standard weight.

*   *Valve symbols* (Part 8):
    - Gate valve: bowtie (two opposing triangles, tips touching).
    - Globe valve: bowtie with a small circle at the center.
    - Check valve: single triangle in flow direction with a perpendicular
      seat bar at the downstream tip.
    - Ball valve: bowtie with a filled circle at the center.
    - Three-way valve: bowtie with a perpendicular branch port; small circle
      at center.
    - Control valve: globe valve body plus an actuator stem and diaphragm
      triangle above.

*   *Process equipment* (Part 6):
    - Centrifugal pump: circle with an internal filled triangle pointing in
      the flow direction.  Horizontal flow-through (inlet left, outlet
      right).
    - Positive displacement pump: same circle + triangle convention.
    - Tank/vessel: rectangle; open-top tanks use a dashed top edge.
    - Heat exchanger: circle with crossed internal tubes.

*   *Piping elements*:
    - Pipe segment: straight line between two ports.
    - Pipe tee: horizontal line with a perpendicular branch.
    - Pipe reducer: trapezoid tapering from inlet to outlet.
    - Pipe cap: stub ending with a perpendicular bar.

*   *Spacing & layout* (Part 1, Clause 5):
    - Minimum gap between adjacent equipment symbols:
      ``PID_MIN_EQUIPMENT_GAP`` (30 mm).
    - Minimum vertical spacing between parallel pipe legs:
      ``PID_MIN_LEG_SPACING`` (40 mm).

**ISA 5.1 — Instrumentation Symbols and Identification**

*   *Instrument bubble* (Clause 5.2):
    - A circle of diameter 12 mm (``INSTRUMENT_BUBBLE_RADIUS`` = 6 mm).
    - Interior divided by a horizontal line when a tag number is shown:
      ISA letter codes in the upper half, tag number in the lower half.
    - Location variants: *field* (plain circle), *panel* (solid dividing
      line), *DCS/shared display* (dashed dividing line).

*   *ISA letter codes* (Clause 4):
    - First letter identifies the measured variable (e.g. T = Temperature,
      P = Pressure, F = Flow).  See :data:`ISA_FIRST_LETTER`.
    - Succeeding letters identify the function (e.g. T = Transmitter,
      I = Indicator, C = Controller).  See :data:`ISA_SUCCEEDING_LETTERS`.
    - The ``letters`` argument on :func:`instrument_bubble` must start with
      a valid first letter and may contain valid succeeding letters.
      :func:`validate_isa_letters` enforces this.

*   *Signal line dash pattern* (Clause 5.4):
    - Electrical signal: evenly dashed (``PID_SIGNAL_DASH``).
    - Pneumatic signal: dash-dot (``PID_PNEUMATIC_DASH``).

**ISO 3098 — Technical product documentation — Lettering**

*   *Minimum text height* (Clause 4.1):
    - 2.5 mm for A3/A4 drawing sizes.  All text constants
      (``PID_TEXT_SIZE_BUBBLE``, ``PID_TEXT_SIZE_TAG``, ``PID_TEXT_SIZE_PIPE``)
      default to 2.5 mm.

Design Rules (enforced by validation and builder)
--------------------------------------------------

1. **Line weight rule** — every ``Line`` element must use one of the three
   standard stroke widths.
2. **No overlap rule** — equipment bounding boxes must not intersect.
3. **Page boundary rule** — all equipment must fit within the page minus
   a 10 mm margin.
4. **ISA letter rule** — instrument bubble letter codes must be valid ISA 5.1
   first + succeeding letters.
5. **Port direction rule** — pipes leaving a port route in the port's
   direction first (vertical ports route vertically first, horizontal
   ports route horizontally first).
"""

from schematika.core.constants import (
    GRID_SIZE,
    LINE_WIDTH_THIN,
    TEXT_FONT_FAMILY,
    TEXT_SIZE_MAIN,
)

__all__ = [
    "GRID_SIZE",
    "INSTRUMENT_BUBBLE_RADIUS",
    "ISA_FIRST_LETTER",
    "ISA_SUCCEEDING_LETTERS",
    "LINE_WIDTH_THIN",
    "PID_ACTUATOR_STEM_HEIGHT",
    "PID_ACTUATOR_TRI_HEIGHT",
    "PID_CAP_HALF_HEIGHT",
    "PID_DEFAULT_PIPE_LENGTH",
    "PID_EQUIPMENT_STROKE",
    "PID_FLOW_ARROW_SIZE",
    "PID_HX_RADIUS",
    "PID_HX_TUBE_LENGTH_FACTOR",
    "PID_HX_TUBE_OFFSET",
    "PID_LABEL_OFFSET",
    "PID_LABEL_PIPE_OFFSET",
    "PID_LINE_WEIGHT",
    "PID_MIN_EQUIPMENT_GAP",
    "PID_MIN_LEG_SPACING",
    "PID_OPEN_TANK_DASH",
    "PID_PNEUMATIC_DASH",
    "PID_PUMP_RADIUS",
    "PID_REDUCER_INLET_HALF_H",
    "PID_REDUCER_LENGTH",
    "PID_REDUCER_OUTLET_HALF_H",
    "PID_SIGNAL_DASH",
    "PID_SIGNAL_LINE_WEIGHT",
    "PID_STUB_LENGTH",
    "PID_TAG_OFFSET",
    "PID_TANK_HALF_HEIGHT",
    "PID_TANK_HALF_WIDTH",
    "PID_TEE_BRANCH_LENGTH",
    "PID_TEE_HALF_LENGTH",
    "PID_TEXT_SIZE_BUBBLE",
    "PID_TEXT_SIZE_PIPE",
    "PID_TEXT_SIZE_TAG",
    "PID_VALVE_BALL_RADIUS",
    "PID_VALVE_CENTER_RADIUS",
    "TEXT_FONT_FAMILY",
    "TEXT_SIZE_MAIN",
    "VALVE_SIZE",
    "validate_isa_letters",
]

# Line weights (mm)
PID_EQUIPMENT_STROKE = GRID_SIZE * 0.1  # 0.5mm — valve bodies, pump circles, tanks
PID_LINE_WEIGHT = GRID_SIZE * 7 / 50  # 0.7mm — process pipes
PID_SIGNAL_LINE_WEIGHT = LINE_WIDTH_THIN  # 0.25mm — signal/instrument lines

# Dash patterns (grid-relative)
PID_SIGNAL_DASH = f"{GRID_SIZE * 0.4},{GRID_SIZE * 0.4}"
PID_PNEUMATIC_DASH = (
    f"{GRID_SIZE * 0.2},{GRID_SIZE * 0.6},{GRID_SIZE},{GRID_SIZE * 0.6}"
)
PID_OPEN_TANK_DASH = f"{GRID_SIZE * 0.6},{GRID_SIZE * 0.4}"

# Symbol dimensions (mm) — ISA 5.1 / ISO 14617 compliant
INSTRUMENT_BUBBLE_RADIUS = GRID_SIZE * 1.2  # 6mm radius → 12mm diameter (ISA 5.1)
VALVE_SIZE = GRID_SIZE * 2  # 10mm valve triangle size
PID_STUB_LENGTH = GRID_SIZE  # 5mm pipe stub connecting ports to body
PID_PUMP_RADIUS = GRID_SIZE * 2  # 10mm pump circle radius (20mm diameter)
PID_TANK_HALF_WIDTH = GRID_SIZE * 3  # 15mm (30mm total tank width)
PID_TANK_HALF_HEIGHT = GRID_SIZE * 4  # 20mm (40mm total tank height)
PID_HX_RADIUS = GRID_SIZE * 2.5  # 12.5mm heat exchanger radius

# Valve sub-component dimensions
PID_VALVE_CENTER_RADIUS = GRID_SIZE * 0.3  # 1.5mm globe/control center circle
PID_VALVE_BALL_RADIUS = GRID_SIZE * 0.5  # 2.5mm ball valve indicator
PID_ACTUATOR_STEM_HEIGHT = GRID_SIZE * 1.6  # 8mm actuator stem
PID_ACTUATOR_TRI_HEIGHT = GRID_SIZE * 0.8  # 4mm actuator triangle

# Text sizes (mm) — ISA 5.1 / ISO 3098
PID_TEXT_SIZE_BUBBLE = GRID_SIZE * 0.5  # 2.5mm letters inside instrument bubbles
PID_TEXT_SIZE_TAG = GRID_SIZE * 0.5  # 2.5mm equipment/instrument tags
PID_TEXT_SIZE_PIPE = GRID_SIZE * 0.5  # 2.5mm pipe labels

# Text/label offsets
PID_TAG_OFFSET = GRID_SIZE * 0.8  # 4mm tag number below bubble
PID_LABEL_PIPE_OFFSET = GRID_SIZE * 0.4  # 2mm label above pipe centerline

# Piping element dimensions
PID_TEE_HALF_LENGTH = GRID_SIZE * 2  # 10mm tee horizontal half-span
PID_TEE_BRANCH_LENGTH = GRID_SIZE * 2  # 10mm tee branch length
PID_REDUCER_LENGTH = GRID_SIZE * 2  # 10mm reducer horizontal span
PID_REDUCER_INLET_HALF_H = GRID_SIZE  # 5mm reducer inlet half-height
PID_REDUCER_OUTLET_HALF_H = GRID_SIZE * 0.5  # 2.5mm reducer outlet half-height
PID_CAP_HALF_HEIGHT = GRID_SIZE * 0.6  # 3mm cap bar half-height

# HX internals
PID_HX_TUBE_OFFSET = GRID_SIZE * 0.7  # 3.5mm tube pass line offset from center
PID_HX_TUBE_LENGTH_FACTOR = 0.6  # tube pass line = 60% of radius (ratio, not mm)

# Flow arrow
PID_FLOW_ARROW_SIZE = GRID_SIZE * 0.6  # 3mm flow direction arrow half-size

# Default pipe segment length
PID_DEFAULT_PIPE_LENGTH = GRID_SIZE * 10  # 50mm

# Spacing constants (mm)
PID_MIN_EQUIPMENT_GAP = GRID_SIZE * 6  # 30mm — minimum gap between equipment
PID_MIN_LEG_SPACING = GRID_SIZE * 8  # 40mm — minimum spacing between pipe legs
PID_LABEL_OFFSET = GRID_SIZE  # 5mm — label offset from symbol edge

# ISA 5.1 letter code lookup tables
ISA_FIRST_LETTER = {
    "A": "Analysis",
    "B": "Burner/Combustion",
    "C": "Conductivity",
    "D": "Density",
    "E": "Voltage",
    "F": "Flow",
    "G": "Gauging",
    "H": "Hand",
    "I": "Current",
    "J": "Power",
    "K": "Time",
    "L": "Level",
    "M": "Moisture",
    "N": "User Choice",
    "O": "User Choice",
    "P": "Pressure",
    "Q": "Quantity",
    "R": "Radiation",
    "S": "Speed",
    "T": "Temperature",
    "U": "Multivariable",
    "V": "Vibration",
    "W": "Weight",
    "X": "Unclassified",
    "Y": "Event/State",
    "Z": "Position",
}

ISA_SUCCEEDING_LETTERS = {
    "A": "Alarm",
    "C": "Controller",
    "E": "Element",
    "G": "Glass/Gauge",
    "H": "High",
    "I": "Indicator",
    "K": "Control Station",
    "L": "Low",
    "N": "User Choice",
    "O": "Orifice",
    "P": "Point",
    "R": "Recorder",
    "S": "Switch",
    "T": "Transmitter",
    "V": "Valve",
    "X": "Unclassified",
    "Y": "Relay/Compute",
    "Z": "Driver/Actuator",
}


def validate_isa_letters(letters: str) -> list[str]:
    """Validate ISA 5.1 instrument letter codes.

    The first character must be a valid ISA first letter (measured variable).
    All subsequent characters must be valid ISA succeeding letters (function
    modifiers).

    Args:
        letters: ISA letter code string (e.g. ``"TT"``, ``"FIC"``, ``"PT"``).

    Returns:
        List of error strings.  Empty list means the code is valid.

    Examples:
        >>> validate_isa_letters("TT")
        []
        >>> validate_isa_letters("FIC")
        []
        >>> validate_isa_letters("QQ")  # Q is not a succeeding letter
        ["Succeeding letter 'Q' at position 2 is not a valid ISA 5.1 ..."]
    """
    errors: list[str] = []
    if not letters:
        errors.append("ISA letter code must not be empty")
        return errors

    first = letters[0].upper()
    if first not in ISA_FIRST_LETTER:
        errors.append(
            f"First letter '{first}' is not a valid ISA 5.1 measured-variable "
            f"code.  Valid: {sorted(ISA_FIRST_LETTER)}"
        )

    for i, ch in enumerate(letters[1:], start=2):
        upper_ch = ch.upper()
        if upper_ch not in ISA_SUCCEEDING_LETTERS:
            errors.append(
                f"Succeeding letter '{upper_ch}' at position {i} is not a "
                f"valid ISA 5.1 function modifier.  "
                f"Valid: {sorted(ISA_SUCCEEDING_LETTERS)}"
            )

    return errors
