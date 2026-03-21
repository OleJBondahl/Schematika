from dataclasses import dataclass, replace

from schematika.electrical.model.constants import (
    COLOR_BLACK,
    DEFAULT_POLE_SPACING,
    PIN_LABEL_OFFSET_X,
    TERMINAL_3P_PINS,
    TEXT_FONT_FAMILY_AUX,
    TEXT_SIZE_PIN,
)
from schematika.electrical.model.core import Element, Point, Port, Style, Symbol, Vector
from schematika.electrical.model.parts import (
    pad_pins,
    terminal_circle,
    terminal_text,
)
from schematika.electrical.model.primitives import Text
from schematika.electrical.utils.transform import translate

"""
IEC 60617 Terminal Symbols.
"""


@dataclass(frozen=True)
class TerminalSymbol(Symbol):
    """
    Specific symbol type for Terminals.
    Distinct from generic Symbols to allow for specialized
    system-level processing (e.g., CSV export).

    Attributes:
        terminal_number (str | None): The specifically assigned terminal number.
    """

    terminal_number: str | None = None


@dataclass(frozen=True)
class TerminalBlock(Symbol):
    """
    Symbol representing a block of terminals (e.g. 3-pole).
    """

    pass


def terminal_symbol(
    label: str = "",
    pins: tuple[str, ...] = (),
    label_pos: str = "left",
    pin_label_pos: str | None = None,
) -> TerminalSymbol:
    """
    Create an IEC 60617 Terminal symbol.

    Symbol Layout:
       O

    Args:
        label (str): The tag of the terminal strip (e.g. "X1").
        pins (tuple): Tuple of pin numbers. Only the first
                      one is used as the terminal number.
                      It is displayed at the bottom port.
        label_pos (str): Position of tag label ('left' or 'right').
        pin_label_pos (str | None): Position of pin number label
            ('left' or 'right'). Defaults to label_pos if None.

    Returns:
        Terminal: The terminal symbol.
    """
    if label_pos not in ("left", "right"):
        raise ValueError(f"label_pos must be 'left' or 'right', got {label_pos!r}")
    if pin_label_pos is None:
        pin_label_pos = "left"

    # Center at (0,0)
    c = terminal_circle(Point(0, 0))

    elements: list[Element] = [c]
    if label:
        elements.append(
            terminal_text(
                label,
                Point(0, 0),
                label_pos=label_pos,
                pin_label_pos=pin_label_pos,
            )
        )

    # Port 1: Up (Input/From)
    # Port 2: Down (Output/To)
    ports = {
        "1": Port("1", Point(0, 0), Vector(0, -1)),
        "2": Port("2", Point(0, 0), Vector(0, 1)),
    }
    ports["top"] = replace(ports["1"], id="top")
    ports["bottom"] = replace(ports["2"], id="bottom")

    term_num = None
    if pins:
        # User Requirement: "only have a pin number at the bottom"
        # We take the first pin as the terminal number.
        term_num = pins[0]

        # Place pin label independently from tag label
        port_y = float(ports["2"].position.y)
        if pin_label_pos == "right":
            pos_x = ports["2"].position.x + PIN_LABEL_OFFSET_X
            anchor = "start"
        else:
            pos_x = ports["2"].position.x - PIN_LABEL_OFFSET_X
            anchor = "end"
        elements.append(
            Text(
                content=term_num,
                position=Point(pos_x, port_y),
                anchor=anchor,
                font_size=TEXT_SIZE_PIN,
                style=Style(
                    stroke="none", fill=COLOR_BLACK, font_family=TEXT_FONT_FAMILY_AUX
                ),
            )
        )

    return TerminalSymbol(
        elements=elements, ports=ports, label=label, terminal_number=term_num
    )


def multi_pole_terminal_symbol(
    label: str = "",
    pins: tuple[str, ...] = (),
    poles: int = 2,
    label_pos: str = "left",
    pin_label_pos: str | None = None,
) -> TerminalBlock:
    """
    Create an N-pole terminal block.

    Args:
        label: The tag of the terminal strip (e.g. "X1").
        pins: Tuple of terminal numbers, one per pole.
              Padded with empty strings if shorter than poles.
        poles: Number of poles (must be >= 2).
        label_pos: Position of tag label ('left' or 'right').
        pin_label_pos: Position of pin number label ('left' or 'right').
            Defaults to label_pos if None.

    Returns:
        TerminalBlock: The N-pole terminal block.
    """
    if poles < 1:
        raise ValueError(f"poles must be >= 1, got {poles}")
    if label_pos not in ("left", "right"):
        raise ValueError(f"label_pos must be 'left' or 'right', got {label_pos!r}")
    p_safe = pad_pins(pins, poles)

    all_elements: list[Element] = []
    new_ports = {}

    for i in range(poles):
        pole_label = label if i == 0 else ""
        pole_lpos = label_pos if i == 0 else "left"
        pole = terminal_symbol(
            label=pole_label,
            pins=(p_safe[i],),
            label_pos=pole_lpos,
            pin_label_pos=pin_label_pos,
        )
        if i > 0:
            pole = translate(pole, DEFAULT_POLE_SPACING * i, 0)

        all_elements += pole.elements

        in_id = str(i * 2 + 1)
        out_id = str(i * 2 + 2)
        if "1" in pole.ports:
            new_ports[in_id] = replace(pole.ports["1"], id=in_id)
        if "2" in pole.ports:
            new_ports[out_id] = replace(pole.ports["2"], id=out_id)

    return TerminalBlock(elements=list(all_elements), ports=new_ports, label=label)


def three_pole_terminal_symbol(
    label: str = "",
    pins: tuple[str, ...] = TERMINAL_3P_PINS,
    label_pos: str = "left",
    pin_label_pos: str | None = None,
) -> TerminalBlock:
    """
    Create a 3-pole terminal block.

    Args:
        label: The tag of the terminal strip.
        pins: A tuple of 3 terminal numbers (e.g. ("1", "2", "3")).
        label_pos: Position of tag label ('left' or 'right').
        pin_label_pos: Position of pin number label ('left' or 'right').
            Defaults to label_pos if None.

    Returns:
        TerminalBlock: The 3-pole terminal block.
    """
    return multi_pole_terminal_symbol(
        label, pins, poles=3, label_pos=label_pos, pin_label_pos=pin_label_pos
    )
