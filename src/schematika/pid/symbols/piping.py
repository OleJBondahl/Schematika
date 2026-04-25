"""ISO 14617 piping primitive symbol factories."""

from typing import TYPE_CHECKING

from schematika.core import Line, Point, Port, Style, Symbol, Text, Vector
from schematika.core.constants import TEXT_FONT_FAMILY
from schematika.pid.constants import (
    PID_CAP_HALF_HEIGHT,
    PID_DEFAULT_PIPE_LENGTH,
    PID_EQUIPMENT_STROKE,
    PID_LINE_WEIGHT,
    PID_REDUCER_INLET_HALF_H,
    PID_REDUCER_LENGTH,
    PID_REDUCER_OUTLET_HALF_H,
    PID_STUB_LENGTH,
    PID_TAG_OFFSET,
    PID_TEE_BRANCH_LENGTH,
    PID_TEE_HALF_LENGTH,
    PID_TEXT_SIZE_TAG,
)

if TYPE_CHECKING:
    from schematika.core.geometry import Element

_PIPE_STYLE = Style(stroke="black", stroke_width=PID_LINE_WEIGHT, fill="none")
_BODY_STYLE = Style(stroke="black", stroke_width=PID_EQUIPMENT_STROKE, fill="none")
_TEXT_STYLE = Style(stroke="none", fill="black", font_family=TEXT_FONT_FAMILY)


def pipe_segment(length: float = PID_DEFAULT_PIPE_LENGTH, label: str = "") -> Symbol:
    """Horizontal pipe segment per ISO 14617.

    Port IDs:
        ``"in"`` — pipe inlet (left, west).
        ``"out"`` — pipe outlet (right, east).

    Args:
        length: Total pipe length in mm. Defaults to ``PID_DEFAULT_PIPE_LENGTH`` (50mm).
        label: Optional pipe tag or line specification, e.g. ``"3-CS-001"``.

    Returns:
        Symbol: Pipe segment with two horizontal ports.

    Examples:
        >>> from schematika.pid import pipe_segment
        >>> sym = pipe_segment(label="3-CS-001")
        >>> sorted(sym.ports)
        ['in', 'out']
        >>> sym.label
        '3-CS-001'
    """
    half = length / 2.0
    pipe = Line(Point(-half, 0.0), Point(half, 0.0), _PIPE_STYLE)

    elements: list[Element] = [pipe]

    if label:
        elements.append(
            Text(
                content=label,
                position=Point(0.0, -PID_TAG_OFFSET),
                style=_TEXT_STYLE,
                anchor="middle",
                dominant_baseline="auto",
                font_size=PID_TEXT_SIZE_TAG,
            )
        )

    ports = {
        "in": Port("in", Point(-half, 0.0), Vector(-1, 0)),
        "out": Port("out", Point(half, 0.0), Vector(1, 0)),
    }

    return Symbol(elements, ports, label=label)


def pipe_tee() -> Symbol:
    """Pipe tee junction per ISO 14617.

    Horizontal pipe with a perpendicular downward branch.

    Port IDs:
        ``"in"`` — pipe inlet (left, west).
        ``"out"`` — pipe outlet (right, east).
        ``"branch"`` — branch outlet (bottom, south).

    Returns:
        Symbol: Pipe tee with two horizontal ports and one branch port.

    Examples:
        >>> from schematika.pid import pipe_tee
        >>> sym = pipe_tee()
        >>> sorted(sym.ports)
        ['branch', 'in', 'out']
        >>> sym.label is None
        True
    """
    half = PID_TEE_HALF_LENGTH
    branch_len = PID_TEE_BRANCH_LENGTH

    horizontal = Line(Point(-half, 0.0), Point(half, 0.0), _PIPE_STYLE)
    branch = Line(Point(0.0, 0.0), Point(0.0, branch_len), _PIPE_STYLE)

    elements: list[Element] = [horizontal, branch]

    ports = {
        "in": Port("in", Point(-half, 0.0), Vector(-1, 0)),
        "out": Port("out", Point(half, 0.0), Vector(1, 0)),
        "branch": Port("branch", Point(0.0, branch_len), Vector(0, 1)),
    }

    return Symbol(elements, ports, label=None)


def pipe_reducer(label: str = "") -> Symbol:
    """Pipe reducer symbol per ISO 14617.

    Trapezoid shape tapering from a wider inlet (left) to a narrower outlet (right).

    Port IDs:
        ``"in"`` — pipe inlet (left, west).
        ``"out"`` — pipe outlet (right, east).

    Args:
        label: Optional reducer tag, e.g. ``"R-101"``.

    Returns:
        Symbol: Pipe reducer with two horizontal ports.

    Examples:
        >>> from schematika.pid import pipe_reducer
        >>> sym = pipe_reducer("R-101")
        >>> sorted(sym.ports)
        ['in', 'out']
        >>> sym.label
        'R-101'
    """
    length = PID_REDUCER_LENGTH
    h_in = PID_REDUCER_INLET_HALF_H
    h_out = PID_REDUCER_OUTLET_HALF_H

    # Trapezoid outline
    top_line = Line(Point(-length, -h_in), Point(length, -h_out), _BODY_STYLE)
    bot_line = Line(Point(-length, h_in), Point(length, h_out), _BODY_STYLE)
    left_cap = Line(Point(-length, -h_in), Point(-length, h_in), _BODY_STYLE)
    right_cap = Line(Point(length, -h_out), Point(length, h_out), _BODY_STYLE)

    # Pipe stubs
    in_stub = Line(
        Point(-length - PID_STUB_LENGTH, 0.0), Point(-length, 0.0), _PIPE_STYLE
    )
    out_stub = Line(
        Point(length, 0.0), Point(length + PID_STUB_LENGTH, 0.0), _PIPE_STYLE
    )

    elements: list[Element] = [
        top_line,
        bot_line,
        left_cap,
        right_cap,
        in_stub,
        out_stub,
    ]

    if label:
        elements.append(
            Text(
                content=label,
                position=Point(0.0, h_in + PID_TAG_OFFSET),
                style=_TEXT_STYLE,
                anchor="middle",
                dominant_baseline="auto",
                font_size=PID_TEXT_SIZE_TAG,
            )
        )

    ports = {
        "in": Port("in", Point(-length - PID_STUB_LENGTH, 0.0), Vector(-1, 0)),
        "out": Port("out", Point(length + PID_STUB_LENGTH, 0.0), Vector(1, 0)),
    }

    return Symbol(elements, ports, label=label)


def pipe_cap() -> Symbol:
    """Pipe cap (blind end) symbol per ISO 14617.

    Short stub ending in a perpendicular cap line, indicating a closed pipe end.

    Port IDs:
        ``"in"`` — pipe inlet (left, west).

    Returns:
        Symbol: Pipe cap with one port.

    Examples:
        >>> from schematika.pid import pipe_cap
        >>> sym = pipe_cap()
        >>> list(sym.ports)
        ['in']
        >>> sym.label is None
        True
    """
    stub_len = PID_STUB_LENGTH
    cap_h = PID_CAP_HALF_HEIGHT

    stub = Line(Point(-stub_len, 0.0), Point(0.0, 0.0), _PIPE_STYLE)
    cap = Line(Point(0.0, -cap_h), Point(0.0, cap_h), _BODY_STYLE)

    elements: list[Element] = [stub, cap]

    ports = {
        "in": Port("in", Point(-stub_len, 0.0), Vector(-1, 0)),
    }

    return Symbol(elements, ports, label=None)
