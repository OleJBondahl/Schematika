"""Factory functions for generic block / function-box symbols.

Provides rectangular block symbols used for PLCs, drives, and other
box-style components. Raises ``CircuitValidationError`` on invalid geometry.
"""

from dataclasses import replace

from schematika.core.exceptions import CircuitValidationError
from schematika.electrical.model.constants import (
    COLOR_BLACK,
    DEFAULT_POLE_SPACING,
    GRID_SIZE,
    TEXT_FONT_FAMILY_AUX,
    TEXT_SIZE_PIN,
)
from schematika.electrical.model.core import Element, Point, Port, Style, Symbol, Vector
from schematika.electrical.model.parts import box, standard_style, standard_text
from schematika.electrical.model.primitives import Line, Text


def terminal_box(
    label: str = "",
    num_pins: int = 1,
    start_pin_number: int = 1,
    pin_spacing: float = DEFAULT_POLE_SPACING,
    pins: tuple[str, ...] = (),
) -> Symbol:
    """Create a Rectangular Terminal Box Symbol.

    Dimensions:
        Height: Equal to pin_spacing (default 10mm / 2 grids).
        Width: Flexible (num_pins - 1) * spacing + 1 Grid (padding 0.5 grid each side).
        Pins: Pointing upwards.
        Pin Numbers: LEFT of the pins.

    Args:
        label (str): Component tag.
        num_pins (int): Number of pins/terminals.
        start_pin_number (int): Starting number for pin labels.
        pin_spacing (float): distance between pins.
        pins: Explicit pin labels. Overrides start_pin_number when provided.

    Returns:
        Symbol: The symbol.
    """
    if pins:
        num_pins = len(pins)

    num_pins = max(num_pins, 1)

    style = standard_style()

    # Box is too short in the height direction, increase to the same as pin spacing
    # Pin Spacing default is 10.0 (2 Grid).
    box_height = pin_spacing

    # Standard Pin length and alignment
    # Pin points UP from Top of box.
    # Origin (0,0) at Top Edge of Box where first pin starts?
    # Or Origin at First Port?
    # Sticking with: Origin (0,0) is at Box Top Edge, First Pin X.
    # Pin extends Up from 0 to -pin_length.

    pin_length = GRID_SIZE / 2  # 2.5mm
    padding = GRID_SIZE / 2  # 2.5mm

    span = (num_pins - 1) * pin_spacing
    box_width = span + 2 * padding

    # Center of box
    # X: span / 2  # noqa: ERA001
    # Y: box_height / 2 (Below 0)
    center_x = span / 2
    center_y = box_height / 2

    rect = box(Point(center_x, center_y), box_width, box_height, filled=False)

    elements: list[Element] = [rect]
    ports = {}

    for i in range(num_pins):
        p_str = pins[i] if pins else str(start_pin_number + i)

        px = i * pin_spacing

        # Pin Line
        # From box top (0) upwards to (-pin_length)
        line = Line(Point(px, 0), Point(px, -pin_length), style)
        elements.append(line)

        # Port at tip
        ports[p_str] = Port(p_str, Point(px, -pin_length), Vector(0, -1))

        # Pin Number
        # "always put the pin numbers of the left of the pins"
        # Position: px - offset  # noqa: ERA001

        text_x = px - 1.0  # 1mm to the LEFT of pin
        text_y = -pin_length / 2  # Middle of the pin line

        text = Text(
            content=p_str,
            position=Point(text_x, text_y),
            anchor="end",  # Right aligned (End of text touches x)
            dominant_baseline="middle",
            font_size=TEXT_SIZE_PIN,
            style=Style(
                stroke="none", fill=COLOR_BLACK, font_family=TEXT_FONT_FAMILY_AUX
            ),
        )
        elements.append(text)

    if label:
        elements.append(standard_text(label, Point(0, 0)))

    return Symbol(elements, ports, label=label)


def psu(label: str = "U1", pins: tuple[str, ...] = ()) -> Symbol:
    """Create a Power Supply Unit (PSU) symbol.

    A specialized dynamic block with:
    - Pins: Top (L, N, PE), Bottom (24V, GND)
    - Visuals: Diagonal line, 'AC' in top-left, 'DC' in bottom-right.

    Args:
        label (str): Component tag.
        pins: Accepted for builder compatibility but not used;
              the PSU has fixed pin assignments.

    Returns:
        Symbol: The PSU symbol.
    """
    # Define fixed configuration for PSU
    top_pins = ("L", "N", "PE")
    bottom_pins = ("24V", "GND")
    pin_spacing = DEFAULT_POLE_SPACING

    # Create the base block
    sym = block(
        label=label, top_pins=top_pins, bottom_pins=bottom_pins, pin_spacing=pin_spacing
    )

    # Re-calculate dimensions to place internal elements
    # (Logic matches dynamic_block)
    box_height = 4 * GRID_SIZE  # 20mm
    padding = GRID_SIZE / 2

    num_top = len(top_pins)
    num_bottom = len(bottom_pins)
    max_pins = max(num_top, num_bottom)

    span = (max_pins - 1) * pin_spacing
    box_width = span + 2 * padding

    # Center of box
    center_x = span / 2

    # Box edges relative to origin (0,0)
    # Left edge: center_x - box_width / 2
    # Right edge: center_x + box_width / 2
    # Top edge: 0
    # Bottom edge: box_height

    left = center_x - box_width / 2
    right = center_x + box_width / 2
    top = 0
    bottom = box_height

    style = standard_style()

    # Diagonal line (Bottom-Left to Top-Right to separate AC top-left / DC bottom-right)
    # Alternatively: Top-Left AC, Bottom-Right DC often separated by diagonal /
    # Let's draw a line from Bottom-Left to Top-Right
    p1 = Point(left, bottom)
    p2 = Point(right, top)
    sym.elements.append(Line(p1, p2, style))

    # Text "AC" in top-left
    # Position: Slightly indented from top-left corner
    ac_pos = Point(left + 2.0, top + 4.0)
    ac_text = Text(
        content="AC",
        position=ac_pos,
        anchor="start",
        dominant_baseline="hanging",  # Text hangs below the point
        font_size=3.5,
        style=Style(stroke="none", fill=COLOR_BLACK, font_family=TEXT_FONT_FAMILY_AUX),
    )
    sym.elements.append(ac_text)

    # Text "DC" in bottom-right
    # Position: Slightly indented from bottom-right corner
    dc_pos = Point(right - 2.0, bottom - 4.0)
    dc_text = Text(
        content="DC",
        position=dc_pos,
        anchor="end",
        dominant_baseline="baseline",  # Text sits on the point
        font_size=3.5,
        style=Style(stroke="none", fill=COLOR_BLACK, font_family=TEXT_FONT_FAMILY_AUX),
    )
    sym.elements.append(dc_text)

    return sym


def block(
    label: str = "",
    top_pins: tuple[str, ...] | None = None,
    bottom_pins: tuple[str, ...] | None = None,
    pin_spacing: float = DEFAULT_POLE_SPACING,
    top_pin_positions: tuple[float, ...] | None = None,
    bottom_pin_positions: tuple[float, ...] | None = None,
) -> Symbol:
    """Create a dynamic block symbol with configurable pins on top and bottom.

    The block automatically adjusts its width based on the maximum number of pins
    (top or bottom). The box is half a grid wider than the last pin on either side
    and has a fixed height of 4 grids.

    Supports both uniform spacing and explicit pin positions:
    - Uniform spacing: Use pin_spacing (backward compatible default)
    - Explicit positions: Use top_pin_positions/bottom_pin_positions

    Dimensions:
        Height: 4 grids (20mm).
        Width: Calculated from pin positions + padding.
        Top Pins: Pointing upwards with pin labels on the left.
        Bottom Pins: Pointing downwards with pin labels on the left.

    Args:
        label (str): Component tag.
        top_pins (tuple[str, ...]): Tuple of pin labels for
            top pins (e.g., ("L", "N", "PE")).
        bottom_pins (tuple[str, ...]): Tuple of pin labels
            for bottom pins (e.g., ("24V", "GND")).
        pin_spacing (float): Distance between pins when using uniform spacing.
        top_pin_positions (tuple[float, ...] | None):
            Explicit x-coordinates for top pins. If provided,
            must match length of top_pins. Overrides
            pin_spacing for top pins.
        bottom_pin_positions (tuple[float, ...] | None):
            Explicit x-coordinates for bottom pins.
            If provided, must match length of bottom_pins.
            Overrides pin_spacing for bottom pins.

    Returns:
        Symbol: The dynamic block symbol.

    Examples:
        # Uniform spacing (backward compatible):
        block(label="U1", top_pins=("L", "N", "PE"), pin_spacing=10.0)

        # Explicit positions (for non-uniform spacing):
        block(
            label="U1",
            top_pins=("+1", "-1", "+2", "-2"),
            top_pin_positions=(0.0, 10.0, 40.0, 50.0)
        )
    """
    # Default to empty tuples if not provided
    if top_pins is None:
        top_pins = ()
    if bottom_pins is None:
        bottom_pins = ()

    # Validate explicit positions if provided
    if top_pin_positions is not None and len(top_pin_positions) != len(top_pins):
        msg = (
            f"top_pin_positions length ({len(top_pin_positions)}) "
            f"must match top_pins length ({len(top_pins)})"
        )
        raise CircuitValidationError(msg)
    if bottom_pin_positions is not None and len(bottom_pin_positions) != len(
        bottom_pins
    ):
        msg = (
            f"bottom_pin_positions length ({len(bottom_pin_positions)}) "
            f"must match bottom_pins length ({len(bottom_pins)})"
        )
        raise CircuitValidationError(msg)

    style = standard_style()

    # Fixed box height of 4 grids
    box_height = 4 * GRID_SIZE  # 20mm

    # Pin dimensions
    pin_length = GRID_SIZE / 2  # 2.5mm
    padding = GRID_SIZE / 2  # 2.5mm (half a grid)

    # Determine pin positions for top and bottom
    if top_pin_positions is not None:
        # Use explicit positions
        top_x_positions = list(top_pin_positions)
    else:
        # Use uniform spacing
        top_x_positions = [i * pin_spacing for i in range(len(top_pins))]

    if bottom_pin_positions is not None:
        # Use explicit positions
        bottom_x_positions = list(bottom_pin_positions)
    else:
        # Use uniform spacing
        bottom_x_positions = [i * pin_spacing for i in range(len(bottom_pins))]

    # Calculate box width based on all pin positions
    all_positions = top_x_positions + bottom_x_positions
    if all_positions:
        min_x = min(all_positions)
        max_x = max(all_positions)
        box_width = (max_x - min_x) + 2 * padding
        # Center of box aligned with pin positions
        center_x = (min_x + max_x) / 2
    else:
        # No pins - minimal box
        box_width = 2 * padding
        center_x = 0

    center_y = box_height / 2

    # Create the rectangle
    rect = box(Point(center_x, center_y), box_width, box_height, filled=False)

    elements: list[Element] = [rect]
    ports = {}

    # Create top pins (pointing upward)
    for i, pin_label in enumerate(top_pins):
        px = top_x_positions[i]

        # Pin line from box top (0) upwards to (-pin_length)
        line = Line(Point(px, 0), Point(px, -pin_length), style)
        elements.append(line)

        # Port at tip - use the label as the port name
        ports[pin_label] = Port(pin_label, Point(px, -pin_length), Vector(0, -1))

        # Pin label to the left of the pin
        text_x = px - 1.0  # 1mm to the LEFT of pin
        text_y = -pin_length / 2  # Middle of the pin line

        text = Text(
            content=pin_label,
            position=Point(text_x, text_y),
            anchor="end",
            dominant_baseline="middle",
            font_size=TEXT_SIZE_PIN,
            style=Style(
                stroke="none", fill=COLOR_BLACK, font_family=TEXT_FONT_FAMILY_AUX
            ),
        )
        elements.append(text)

    # Create bottom pins (pointing downward)
    for i, pin_label in enumerate(bottom_pins):
        px = bottom_x_positions[i]

        # Pin line from box bottom (box_height) downwards to (box_height + pin_length)
        line = Line(Point(px, box_height), Point(px, box_height + pin_length), style)
        elements.append(line)

        # Port at tip - use the label as the port name
        ports[pin_label] = Port(
            pin_label, Point(px, box_height + pin_length), Vector(0, 1)
        )

        # Pin label to the left of the pin, positioned below
        # to avoid collision with box
        text_x = px - 1.0  # 1mm to the LEFT of pin
        # At the end of the pin line (below box)
        text_y = box_height + pin_length

        text = Text(
            content=pin_label,
            position=Point(text_x, text_y),
            anchor="end",
            dominant_baseline="middle",
            font_size=TEXT_SIZE_PIN,
            style=Style(
                stroke="none", fill=COLOR_BLACK, font_family=TEXT_FONT_FAMILY_AUX
            ),
        )
        elements.append(text)

    # Add label if provided - position to the LEFT of the block (not inside)
    # Use the left edge of the box as the reference point so standard_text
    # offsets the label outside the block, consistent with other symbols
    if label:
        left_edge = center_x - box_width / 2
        elements.append(standard_text(label, Point(left_edge, center_y)))

    # Aliasing for standard pole connectivity
    # Map standard port IDs ("1", "2", "3", "4"...) to named ports
    # Top Pins = Input (Odd Standard IDs: 1, 3, 5...)
    for i, pin_label in enumerate(top_pins):
        std_id = str(i * 2 + 1)
        if std_id not in ports:
            ports[std_id] = replace(ports[pin_label], id=std_id)

    # Bottom Pins = Output (Even Standard IDs: 2, 4, 6...)
    for i, pin_label in enumerate(bottom_pins):
        std_id = str(i * 2 + 2)
        if std_id not in ports:
            ports[std_id] = replace(ports[pin_label], id=std_id)

    return Symbol(elements, ports, label=label)
