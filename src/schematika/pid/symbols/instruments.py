"""ISA 5.1 instrument bubble symbol factories."""

from typing import TYPE_CHECKING

from schematika.core import Circle, Line, Point, Port, Style, Symbol, Text, Vector
from schematika.core.constants import LINE_WIDTH_THIN, TEXT_FONT_FAMILY
from schematika.pid.constants import (
    INSTRUMENT_BUBBLE_RADIUS,
    PID_EQUIPMENT_STROKE,
    PID_SIGNAL_DASH,
    PID_SIGNAL_LINE_WEIGHT,
    PID_STUB_LENGTH,
    PID_TEXT_SIZE_BUBBLE,
)

if TYPE_CHECKING:
    from schematika.core.geometry import Element

_SIGNAL_STYLE = Style(stroke="black", stroke_width=PID_SIGNAL_LINE_WEIGHT, fill="none")
_BUBBLE_STYLE = Style(stroke="black", stroke_width=PID_EQUIPMENT_STROKE, fill="white")
_TEXT_STYLE = Style(stroke="none", fill="black", font_family=TEXT_FONT_FAMILY)
_LABEL_STYLE = Style(stroke="none", fill="black", font_family=TEXT_FONT_FAMILY)

_R = INSTRUMENT_BUBBLE_RADIUS  # 6mm


def instrument_bubble(
    label: str = "",
    letters: str = "TT",
    location: str = "field",
    tag_number: str = "",
) -> Symbol:
    """ISA 5.1 instrument bubble.

    A circle whose interior displays the ISA tag letters.
    Location variants:
      - "field":  plain circle (field-mounted instrument)
      - "panel":  circle with horizontal dividing line (panel-mounted)
      - "dcs":    circle with dashed horizontal line (DCS/shared-display)

    Args:
        label: Overall symbol label (if any).
        letters: ISA letter codes displayed inside the bubble (e.g. "TT", "FIC").
        location: One of "field", "panel", or "dcs".
        tag_number: Tag suffix displayed below the bubble (e.g. "101").

    Returns:
        Symbol with ports 'process' (bottom) and 'signal_out' (top).
    """
    # Bubble circle
    bubble = Circle(center=Point(0.0, 0.0), radius=_R, style=_BUBBLE_STYLE)

    elements: list[Element] = [bubble]

    # Horizontal dividing line through center (always shown per ISA 5.1
    # when tag_number is present; also for panel/dcs location variants)
    has_tag = bool(tag_number)
    if has_tag or location in ("panel", "dcs"):
        if location == "dcs":
            line_style = Style(
                stroke="black",
                stroke_width=LINE_WIDTH_THIN,
                fill="none",
                stroke_dasharray=PID_SIGNAL_DASH,
            )
        else:
            line_style = _SIGNAL_STYLE
        divider = Line(Point(-_R, 0.0), Point(_R, 0.0), line_style)
        elements.append(divider)

    # Letters inside bubble (upper half if divided, centered if not)
    if letters:
        letter_y = -_R * 0.3 if has_tag or location in ("panel", "dcs") else 0.0
        letter_text = Text(
            content=letters,
            position=Point(0.0, letter_y),
            style=_TEXT_STYLE,
            anchor="middle",
            dominant_baseline="middle",
            font_size=PID_TEXT_SIZE_BUBBLE,
        )
        elements.append(letter_text)

    # Tag number inside bubble (lower half)
    if has_tag:
        tag_text = Text(
            content=tag_number,
            position=Point(0.0, _R * 0.35),
            style=_TEXT_STYLE,
            anchor="middle",
            dominant_baseline="middle",
            font_size=PID_TEXT_SIZE_BUBBLE,
        )
        elements.append(tag_text)

    # Signal line stubs
    process_stub = Line(Point(0.0, _R), Point(0.0, _R + PID_STUB_LENGTH), _SIGNAL_STYLE)
    signal_stub = Line(
        Point(0.0, -_R), Point(0.0, -_R - PID_STUB_LENGTH), _SIGNAL_STYLE
    )
    elements.extend([process_stub, signal_stub])

    ports = {
        "process": Port("process", Point(0.0, _R + PID_STUB_LENGTH), Vector(0, 1)),
        "signal_out": Port(
            "signal_out", Point(0.0, -_R - PID_STUB_LENGTH), Vector(0, -1)
        ),
    }

    effective_label = label or (f"{letters}-{tag_number}" if tag_number else letters)
    return Symbol(elements, ports, label=effective_label)
