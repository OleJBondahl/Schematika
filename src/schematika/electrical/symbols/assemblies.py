"""Factory functions for multi-component IEC 60617 symbol assemblies.

Provides composite symbol factories (e.g., contactor assemblies with auxiliary
contacts) that combine primitives from other symbol modules. Imports constants
and core types from ``electrical/model/``.
"""

from schematika.electrical.model.constants import (
    COLOR_BLACK,
    CONTACTOR_3P_PINS,
    DEFAULT_POLE_SPACING,
    ESTOP_PINS,
    GRID_SIZE,
    LINE_WIDTH_THIN,
    LINKAGE_DASH_PATTERN,
    TURN_SWITCH_PINS,
)
from schematika.electrical.model.core import Point, Style, Symbol, Vector
from schematika.electrical.model.primitives import Line
from schematika.electrical.utils.transform import translate

from .actuators import estop_button, turn_actuator
from .coils import coil
from .contacts import nc_contact, no_contact


def contactor(
    label: str = "",
    coil_pins: tuple[str, str] | None = None,
    contact_pins: tuple[str, str, str, str, str, str] = CONTACTOR_3P_PINS,
) -> Symbol:
    """High-level contactor symbol.

    Combines a 3-pole NO contact block and a Coil.
    The coil is placed to the left of the contacts.
    A mechanical linkage (stippled line) connects the coil to the contacts.

    Args:
        label: The device label (e.g. "-K1").
        coil_pins: Pins for the coil (A1, A2). If None, coil terminals are hidden.
        contact_pins: Pins for the 3-pole contact (1..6).

    Returns:
        Symbol: The composite contactor symbol.
    """
    # 1. Create the 3-pole NO contacts
    contacts_sym = no_contact(label="", poles=3, pins=contact_pins)

    # 2. Create the coil with label
    coil_offset_x = -DEFAULT_POLE_SPACING * 2

    show_coil_terminals = coil_pins is not None
    safe_coil_pins = coil_pins if coil_pins is not None else ()

    coil_sym = coil(
        label=label, pins=safe_coil_pins, show_terminals=show_coil_terminals
    )
    coil_sym = translate(coil_sym, coil_offset_x, 0)

    # 3. Create the mechanical linkage (stippled line)
    linkage_start = Point(coil_offset_x + DEFAULT_POLE_SPACING / 2, 0)
    linkage_end = Point(DEFAULT_POLE_SPACING * 1.75, 0)

    linkage_style = Style(
        stroke=COLOR_BLACK,
        stroke_width=LINE_WIDTH_THIN,
        stroke_dasharray=LINKAGE_DASH_PATTERN,
    )

    linkage_line = Line(linkage_start, linkage_end, linkage_style)

    # 4. Combine everything
    all_elements = contacts_sym.elements + coil_sym.elements + [linkage_line]

    # Merge ports
    all_ports = {**contacts_sym.ports, **coil_sym.ports}

    return Symbol(elements=all_elements, ports=all_ports, label=label)


def estop(label: str = "", pins: tuple[str, str] = ESTOP_PINS) -> Symbol:
    """Emergency Stop Assembly.

    Combines a Normally Closed contact with an Emergency Stop Mushroom Head.
    The Button is placed to the LEFT of the contact.
    """
    # 1. Contact (Vertical)
    contact_sym = nc_contact(label=label, pins=pins)

    # 2. Linkage (Dashed line from contact center to Left)
    linkage_len = GRID_SIZE / 2  # 2.5mm
    linkage_vector = Vector(-linkage_len, 0)  # Left

    linkage = Line(
        Point(0, 0),
        Point(linkage_vector.dx, linkage_vector.dy),
        Style(
            stroke=COLOR_BLACK,
            stroke_width=LINE_WIDTH_THIN,
            stroke_dasharray=LINKAGE_DASH_PATTERN,
        ),
    )

    # 3. Button (Mushroom Head)
    button_sym = estop_button(rotation=180)
    button_sym = translate(button_sym, linkage_vector.dx, linkage_vector.dy)

    all_elements = [*contact_sym.elements, linkage, *button_sym.elements]

    return Symbol(elements=all_elements, ports=contact_sym.ports, label=label)


def turn_switch(label: str = "", pins: tuple[str, str] = TURN_SWITCH_PINS) -> Symbol:
    """Turn Switch Assembly.

    Combines a Normally Open contact with a Turn Switch actuator.
    The Turn Switch is placed to the LEFT of the contact.

    Args:
        label: Component label (e.g. "-S1").
        pins: Tuple of 2 pin labels for the contact.

    Returns:
        Symbol: The composite turn switch assembly.
    """
    # 1. NO Contact (vertical)
    contact_sym = no_contact(label=label, pins=pins)

    # 2. Linkage
    blade_x_at_center = -GRID_SIZE / 4
    actuator_x = -GRID_SIZE / 2

    linkage = Line(
        Point(blade_x_at_center, 0),
        Point(actuator_x, 0),
        Style(
            stroke=COLOR_BLACK,
            stroke_width=LINE_WIDTH_THIN,
            stroke_dasharray=LINKAGE_DASH_PATTERN,
        ),
    )

    # 3. Turn Switch actuator
    actuator_sym = turn_actuator(rotation=180)
    actuator_sym = translate(actuator_sym, actuator_x, 0)

    # 4. Combine all elements
    all_elements = [*contact_sym.elements, linkage, *actuator_sym.elements]

    return Symbol(elements=all_elements, ports=contact_sym.ports, label=label)
