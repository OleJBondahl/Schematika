"""Factory functions and data class for IEC 60617 terminal symbols.

Provides ``TerminalSymbol`` (a ``Symbol`` subclass) and factory functions for
single and feed-through terminal blocks. Raises ``CircuitValidationError`` on
invalid configuration.
"""

from dataclasses import dataclass, replace

from schematika.core.exceptions import CircuitValidationError
from schematika.electrical.model.constants import (
    COLOR_BLACK,
    DEFAULT_POLE_SPACING,
    PIN_LABEL_OFFSET_X,
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
    """Symbol type for terminals.

    Distinct from generic Symbols to allow for specialized
    system-level processing (e.g., CSV export).

    Attributes:
        terminal_number (str | None): The specifically assigned terminal number.
    """

    terminal_number: str | None = None


@dataclass(frozen=True)
class TerminalBlock(Symbol):
    """Symbol representing a block of terminals (e.g. 3-pole)."""


def _terminal_single_pole(
    label: str = "",
    pins: tuple[str, ...] = (),
    label_pos: str = "left",
    pin_label_pos: str | None = None,
) -> TerminalSymbol:
    """Single-pole terminal implementation."""
    if label_pos not in ("left", "right"):
        msg = f"label_pos must be 'left' or 'right', got {label_pos!r}"
        raise CircuitValidationError(msg)
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


def _multi_pole_terminal(
    label: str = "",
    pins: tuple[str, ...] = (),
    poles: int = 2,
    label_pos: str = "left",
    pin_label_pos: str | None = None,
) -> TerminalBlock:
    """Multi-pole terminal block implementation."""
    if poles < 1:
        msg = f"poles must be >= 1, got {poles}"
        raise CircuitValidationError(msg)
    if label_pos not in ("left", "right"):
        msg = f"label_pos must be 'left' or 'right', got {label_pos!r}"
        raise CircuitValidationError(msg)
    p_safe = pad_pins(pins, poles)

    all_elements: list[Element] = []
    new_ports = {}

    for i in range(poles):
        pole_label = label if i == 0 else ""
        pole_lpos = label_pos if i == 0 else "left"
        pole = _terminal_single_pole(
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


def terminal(
    label: str = "",
    poles: int = 1,
    pins: tuple[str, ...] = (),
    label_pos: str = "left",
    pin_label_pos: str | None = None,
) -> TerminalSymbol | TerminalBlock:
    """IEC 60617 terminal block symbol (circle-based, through-wiring).

    Single-pole returns a :class:`TerminalSymbol`; multi-pole returns a
    :class:`TerminalBlock`.  Both ``"1"`` / ``"2"`` and semantic alias ports
    ``"top"`` / ``"bottom"`` are exposed for single-pole terminals.

    Ports (poles=1):
        1, top: upward connection point.
        2, bottom: downward connection point.

    Ports (poles=N):
        1, 2, 3, ..., 2N: sequential input/output per pole (odd = top, even = bottom).

    Args:
        label: Terminal strip tag, e.g. ``"X1"``.
        poles: Number of poles (1 for single, 2+ for multi-pole block).
        pins: Pin/terminal numbers; only the first is used for ``poles=1``.
        label_pos: Side for the tag label: ``"left"`` or ``"right"``.
        pin_label_pos: Side for the pin number: ``"left"`` or ``"right"``.

    Returns:
        :class:`TerminalSymbol` for single-pole; :class:`TerminalBlock` for multi-pole.

    Examples:
        >>> from schematika.electrical.symbols import terminal
        >>> sym = terminal(label="X1")
        >>> sorted(sym.ports.keys())
        ['1', '2', 'bottom', 'top']
        >>> blk = terminal(poles=3)
        >>> sorted(blk.ports.keys())
        ['1', '2', '3', '4', '5', '6']
    """
    if poles == 1:
        return _terminal_single_pole(
            label=label, pins=pins, label_pos=label_pos, pin_label_pos=pin_label_pos
        )

    return _multi_pole_terminal(
        label=label,
        pins=pins,
        poles=poles,
        label_pos=label_pos,
        pin_label_pos=pin_label_pos,
    )
