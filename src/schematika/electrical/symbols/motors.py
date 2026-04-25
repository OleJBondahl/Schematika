"""Factory functions for IEC 60617 motor symbols.

Provides symbol factories for 3-phase and single-phase induction motors.
Imports constants and core types from ``electrical/model/``.
"""

import math
from typing import Final

from schematika.electrical.model.constants import (
    COLOR_BLACK,
    DEFAULT_POLE_SPACING,
    GRID_SIZE,
    MOTOR_1P_PINS,
    MOTOR_3P_PINS,
    TEXT_FONT_FAMILY,
)
from schematika.electrical.model.core import Element, Point, Port, Style, Symbol, Vector
from schematika.electrical.model.parts import (
    PIN_LABEL_OFFSET_X,
    PIN_LABEL_OFFSET_Y_ADJUST,
    TEXT_FONT_FAMILY_AUX,
    TEXT_SIZE_PIN,
    create_pin_labels,
    standard_style,
    standard_text,
)
from schematika.electrical.model.primitives import Circle, Line, Text

# Number of phases in a three-phase motor.
_THREE_PHASE_COUNT: Final = 3
# Zero-based index of the PE (Protective Earth) pin in the pin list.
_PE_PIN_INDEX: Final = 3
# Tolerance for port direction classification (up vs. down).
_MOTOR_DIR_THRESHOLD: Final = 0.1

"""
IEC 60617 Motor Symbols.

This module contains motor symbols following IEC 60617 standard:
- Three-phase AC motor (most common in industrial applications)
- Generic motor symbol
"""


def _three_pole_motor(label: str = "", pins: tuple[str, ...] = MOTOR_3P_PINS) -> Symbol:
    """Three-phase AC motor implementation."""
    style = standard_style()

    # Pin spacing - use standard spacing to match terminals
    pin_spacing = DEFAULT_POLE_SPACING  # 10mm (2*GRID_SIZE)

    radius = 2 * pin_spacing  # 10mm

    elements: list[Element] = []
    ports = {}

    # Main circle - centered at origin
    circle = Circle(center=Point(0, 0), radius=radius, style=style)
    elements.append(circle)

    # Add component tag inside the circle
    if label:
        label_text = Text(
            content=label,
            position=Point(0, 0),
            anchor="middle",
            font_size=5.0,
            style=Style(stroke="none", fill=COLOR_BLACK, font_family=TEXT_FONT_FAMILY),
        )
        elements.append(label_text)

    # Pin labels from tuple
    pin_labels = list(pins) if pins else ["U", "V", "W", "PE"]

    terminal_length = pin_spacing  # 5mm lead length

    phase_x_positions = [
        -pin_spacing,  # U (left)
        0,  # V (center - top of circle)
        pin_spacing,  # W (right)
    ]

    for i, x_pos in enumerate(phase_x_positions):
        if i >= len(pin_labels):
            break

        pin_id = pin_labels[i]

        y_on_circle = -math.sqrt(radius**2 - x_pos**2)

        terminal_bottom = Point(x_pos, y_on_circle)
        terminal_top = Point(x_pos, y_on_circle - terminal_length)

        elements.append(Line(terminal_bottom, terminal_top, style))

        ports[pin_id] = Port(id=pin_id, position=terminal_top, direction=Vector(0, -1))

    # PE (Protective Earth) terminal
    if len(pin_labels) > _THREE_PHASE_COUNT:
        pe_label = pin_labels[3]

        pe_x_on_circle = radius
        pe_y_on_circle = 0

        pe_terminal_bottom = Point(pe_x_on_circle, pe_y_on_circle)
        pe_terminal_top = Point(pe_x_on_circle, pe_y_on_circle - terminal_length)

        elements.append(Line(pe_terminal_bottom, pe_terminal_top, style))

        ports[pe_label] = Port(
            id=pe_label, position=pe_terminal_top, direction=Vector(0, -1)
        )

    # Add pin labels if provided
    if pins:
        for i, pin_text in enumerate(pin_labels):
            if not pin_text or pin_text not in ports:
                continue

            port = ports[pin_text]

            # Default: Left (-X)  # noqa: ERA001
            pos_x = port.position.x - PIN_LABEL_OFFSET_X
            pos_y = port.position.y
            anchor = "end"

            # PE (4th pin) special handling - Place on RIGHT side
            if i == _PE_PIN_INDEX:
                pos_x = port.position.x + PIN_LABEL_OFFSET_X
                anchor = "start"

            # Adjustment for Up/Down direction
            if port.direction.dy < -_MOTOR_DIR_THRESHOLD:  # UP
                pos_y += PIN_LABEL_OFFSET_Y_ADJUST
            elif port.direction.dy > _MOTOR_DIR_THRESHOLD:  # DOWN
                pos_y -= PIN_LABEL_OFFSET_Y_ADJUST

            elements.append(
                Text(
                    content=pin_text,
                    position=Point(pos_x, pos_y),
                    anchor=anchor,
                    font_size=TEXT_SIZE_PIN,
                    style=Style(
                        stroke="none",
                        fill=COLOR_BLACK,
                        font_family=TEXT_FONT_FAMILY_AUX,
                    ),
                )
            )

    return Symbol(elements, ports, label=label)


def _single_pole_motor(
    label: str = "", pins: tuple[str, ...] = MOTOR_1P_PINS
) -> Symbol:
    """Single-phase generic motor implementation."""
    style = standard_style()

    # Motor circle diameter
    diameter = 3 * GRID_SIZE  # 15mm
    radius = diameter / 2

    elements: list[Element] = []

    # Main circle
    circle = Circle(center=Point(0, 0), radius=radius, style=style)
    elements.append(circle)

    # Add "M" text
    m_text = Text(
        content="M",
        position=Point(0, 0),
        anchor="middle",
        font_size=4.0,
        style=Style(stroke="none", fill=COLOR_BLACK, font_family=TEXT_FONT_FAMILY),
    )
    elements.append(m_text)

    # Terminal leads
    terminal_length = GRID_SIZE  # 5mm

    # Top terminal
    elements.append(Line(Point(0, -radius), Point(0, -radius - terminal_length), style))

    # Bottom terminal
    elements.append(Line(Point(0, radius), Point(0, radius + terminal_length), style))

    # Ports
    ports = {
        "1": Port("1", Point(0, -radius - terminal_length), Vector(0, -1)),
        "2": Port("2", Point(0, radius + terminal_length), Vector(0, 1)),
    }

    # Label
    if label:
        elements.append(standard_text(label, Point(radius + GRID_SIZE / 2, 0)))

    # Pin labels
    if pins:
        elements.extend(create_pin_labels(ports, pins))

    return Symbol(elements, ports, label=label)


def motor(
    label: str = "",
    poles: int = 1,
    pins: tuple[str, ...] | None = None,
) -> Symbol:
    """IEC 60617 motor symbol: circle with ``M`` or label inside.

    Use ``poles=3`` for a three-phase induction motor (IEC semantic pin IDs
    ``U``, ``V``, ``W``, ``PE``). Use ``poles=1`` for a generic single-phase
    motor (numeric IDs ``"1"`` / ``"2"``).

    Ports:
        U, V, W, PE: three-phase AC motor (poles=3); PE is on the right side.
        1, 2: single-phase generic motor (poles=1).

    Args:
        label: Component tag, e.g. ``"-M1"`` (rendered inside the circle).
        poles: ``3`` for three-phase, ``1`` for generic single-phase.
        pins: Custom pin IDs; defaults to ``MOTOR_3P_PINS`` or ``MOTOR_1P_PINS``.

    Returns:
        Symbol with semantic (3-phase) or numeric (1-phase) ports.

    Examples:
        >>> from schematika.electrical.symbols import motor
        >>> sym3 = motor(poles=3)
        >>> sorted(sym3.ports.keys())
        ['PE', 'U', 'V', 'W']
        >>> sym1 = motor(poles=1)
        >>> sorted(sym1.ports.keys())
        ['1', '2']
    """
    if poles == _THREE_PHASE_COUNT:
        if pins is None:
            pins = MOTOR_3P_PINS
        return _three_pole_motor(label=label, pins=pins)

    if pins is None:
        pins = MOTOR_1P_PINS
    return _single_pole_motor(label=label, pins=pins)
