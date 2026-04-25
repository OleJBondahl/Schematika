"""Generic block / function-box symbol factories."""

from dataclasses import replace
from typing import Literal

import deal

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
    """Rectangular terminal box with upward-pointing pins and left-aligned labels.

    Port IDs match the ``pins`` tuple if supplied, otherwise sequential integers
    starting at ``start_pin_number``.

    Ports:
        <pin_id>: one upward port per pin position.

    Args:
        label: Box label, e.g. ``"X1"``.
        num_pins: Number of pins when ``pins`` is not supplied.
        start_pin_number: First sequential pin number when ``pins`` is not supplied.
        pin_spacing: Horizontal spacing between pins in mm.
        pins: Explicit pin IDs (overrides ``num_pins`` and ``start_pin_number``).

    Returns:
        Symbol with sequential or named upward-pointing ports.

    Examples:
        >>> from schematika.electrical.symbols import terminal_box
        >>> sym = terminal_box(num_pins=3)
        >>> sorted(sym.ports.keys())
        ['1', '2', '3']
        >>> sym2 = terminal_box(pins=("A", "B"))
        >>> sorted(sym2.ports.keys())
        ['A', 'B']
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


def psu(label: str = "U1", pins: tuple[str, ...] = ()) -> Symbol:  # noqa: ARG001
    """IEC-style power supply unit block with fixed AC input / DC output pins.

    Built on :func:`block` with hard-coded top pins ``L``, ``N``, ``PE`` and
    bottom pins ``24V``, ``GND``. Also exposes numeric alias ports so the
    block's standard connectivity works.

    Ports:
        L, N, PE: AC input (top, pointing up).
        24V, GND: DC output (bottom, pointing down).
        1, 2, 3: numeric aliases for L, N, PE respectively.
        4, 5: numeric aliases for 24V, GND respectively.

    Args:
        label: Component tag, e.g. ``"U1"``.
        pins: Accepted for API compatibility; ignored (pins are fixed).

    Returns:
        Symbol with fixed AC/DC ports and diagonal AC/DC marker.

    Examples:
        >>> from schematika.electrical.symbols import psu
        >>> sym = psu(label="U1")
        >>> "L" in sym.ports and "24V" in sym.ports
        True
        >>> sorted(p for p in sym.ports if p.isalpha())  # semantic ports
        ['GND', 'L', 'N', 'PE']
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


@deal.pure
def _compute_pin_x_positions(
    pins: tuple[str, ...],
    explicit: tuple[float, ...] | None,
    spacing: float,
) -> list[float]:
    if explicit is not None:
        return list(explicit)
    return [i * spacing for i in range(len(pins))]


@deal.raises(CircuitValidationError)
def _validate_pin_positions(
    positions: tuple[float, ...] | None,
    pins: tuple[str, ...],
    name: str,
) -> None:
    if positions is not None and len(positions) != len(pins):
        msg = (
            f"{name}_pin_positions length ({len(positions)}) "
            f"must match {name}_pins length ({len(pins)})"
        )
        raise CircuitValidationError(msg)


@deal.pure
def _make_pin_side(
    pins: tuple[str, ...],
    x_positions: list[float],
    side: Literal["top", "bottom"],
    box_height: float,
    pin_length: float,
    style: Style,
) -> tuple[list[Element], dict[str, Port]]:
    if side == "top":
        line_start_y = 0.0
        line_end_y = -pin_length
        port_y = -pin_length
        port_dir = Vector(0, -1)
        text_y = -pin_length / 2
    else:
        line_start_y = box_height
        line_end_y = box_height + pin_length
        port_y = box_height + pin_length
        port_dir = Vector(0, 1)
        text_y = box_height + pin_length

    elements: list[Element] = []
    ports: dict[str, Port] = {}
    for i, pin_label in enumerate(pins):
        px = x_positions[i]
        elements.append(Line(Point(px, line_start_y), Point(px, line_end_y), style))
        ports[pin_label] = Port(pin_label, Point(px, port_y), port_dir)
        elements.append(
            Text(
                content=pin_label,
                position=Point(px - 1.0, text_y),
                anchor="end",
                dominant_baseline="middle",
                font_size=TEXT_SIZE_PIN,
                style=Style(
                    stroke="none", fill=COLOR_BLACK, font_family=TEXT_FONT_FAMILY_AUX
                ),
            )
        )
    return elements, ports


@deal.pure
def _make_alias_ports(
    pins: tuple[str, ...],
    existing_ports: dict[str, Port],
    parity_offset: int,
) -> dict[str, Port]:
    aliases: dict[str, Port] = {}
    for i, pin_label in enumerate(pins):
        std_id = str(i * 2 + parity_offset)
        if std_id not in existing_ports and std_id not in aliases:
            aliases[std_id] = replace(existing_ports[pin_label], id=std_id)
    return aliases


def block(
    label: str = "",
    top_pins: tuple[str, ...] | None = None,
    bottom_pins: tuple[str, ...] | None = None,
    pin_spacing: float = DEFAULT_POLE_SPACING,
    top_pin_positions: tuple[float, ...] | None = None,
    bottom_pin_positions: tuple[float, ...] | None = None,
) -> Symbol:
    """Generic function-box symbol with named top and bottom pins.

    Box height is fixed at 4 grid units (20 mm). Each named top/bottom pin
    becomes a port. Numeric alias ports (``"1"``, ``"2"``, ...) are also added:
    odd indices for top pins, even for bottom pins.

    Ports:
        <top_pin>: upward-pointing port for each top pin label.
        <bottom_pin>: downward-pointing port for each bottom pin label.
        1, 3, 5, ...: numeric aliases for top pins (odd = input side).
        2, 4, 6, ...: numeric aliases for bottom pins (even = output side).

    Args:
        label: Component tag, e.g. ``"A1"``.
        top_pins: Pin labels on the top edge (pointing up).
        bottom_pins: Pin labels on the bottom edge (pointing down).
        pin_spacing: Uniform horizontal spacing in mm; ignored when
            ``*_pin_positions`` is supplied.
        top_pin_positions: Explicit x-positions for top pins (overrides spacing).
        bottom_pin_positions: Explicit x-positions for bottom pins.

    Returns:
        Symbol with named and numeric alias ports.

    Examples:
        >>> from schematika.electrical.symbols import block
        >>> sym = block(top_pins=("IN",), bottom_pins=("OUT",))
        >>> "IN" in sym.ports and "OUT" in sym.ports
        True
        >>> sym_empty = block()
        >>> sym_empty.ports
        {}
    """
    top_pins = top_pins or ()
    bottom_pins = bottom_pins or ()
    _validate_pin_positions(top_pin_positions, top_pins, "top")
    _validate_pin_positions(bottom_pin_positions, bottom_pins, "bottom")

    style = standard_style()
    box_height = 4 * GRID_SIZE
    pin_length = GRID_SIZE / 2
    padding = GRID_SIZE / 2

    top_x = _compute_pin_x_positions(top_pins, top_pin_positions, pin_spacing)
    bottom_x = _compute_pin_x_positions(bottom_pins, bottom_pin_positions, pin_spacing)
    all_x = top_x + bottom_x
    if all_x:
        box_width = (max(all_x) - min(all_x)) + 2 * padding
        center_x = (min(all_x) + max(all_x)) / 2
    else:
        box_width = 2 * padding
        center_x = 0

    center_y = box_height / 2

    elements: list[Element] = [
        box(Point(center_x, center_y), box_width, box_height, filled=False)
    ]
    ports: dict[str, Port] = {}

    top_elems, top_ports = _make_pin_side(
        top_pins, top_x, "top", box_height, pin_length, style
    )
    elements.extend(top_elems)
    ports.update(top_ports)

    bottom_elems, bottom_ports = _make_pin_side(
        bottom_pins, bottom_x, "bottom", box_height, pin_length, style
    )
    elements.extend(bottom_elems)
    ports.update(bottom_ports)

    if label:
        elements.append(standard_text(label, Point(center_x - box_width / 2, center_y)))

    ports.update(_make_alias_ports(top_pins, ports, parity_offset=1))
    ports.update(_make_alias_ports(bottom_pins, ports, parity_offset=2))

    return Symbol(elements, ports, label=label)
