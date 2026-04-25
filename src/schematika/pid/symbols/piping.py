"""ISO 14617 piping primitive symbol factories."""

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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from schematika.core.geometry import Element

_PIPE_STYLE = Style(stroke="black", stroke_width=PID_LINE_WEIGHT, fill="none")
_BODY_STYLE = Style(stroke="black", stroke_width=PID_EQUIPMENT_STROKE, fill="none")
_TEXT_STYLE = Style(stroke="none", fill="black", font_family=TEXT_FONT_FAMILY)


def pipe_segment(length: float = PID_DEFAULT_PIPE_LENGTH, label: str = "") -> Symbol:
    """Horizontal pipe; ports `in` (left), `out` (right)."""
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
    """Horizontal pipe + downward branch; ports `in`/`out`/`branch`."""
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
    """Trapezoid: inlet (left) wider than outlet (right)."""
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
    """Short stub ending in a perpendicular cap line; port `in`."""
    stub_len = PID_STUB_LENGTH
    cap_h = PID_CAP_HALF_HEIGHT

    stub = Line(Point(-stub_len, 0.0), Point(0.0, 0.0), _PIPE_STYLE)
    cap = Line(Point(0.0, -cap_h), Point(0.0, cap_h), _BODY_STYLE)

    elements: list[Element] = [stub, cap]

    ports = {
        "in": Port("in", Point(-stub_len, 0.0), Vector(-1, 0)),
    }

    return Symbol(elements, ports, label=None)
