"""Factory functions for cross-reference arrow symbols.

Provides symbol factories for page cross-reference arrows (jump-in and
jump-out) used to link related circuits across pages. Raises
``CircuitValidationError`` on invalid configuration.
"""

from schematika.core.exceptions import CircuitValidationError
from schematika.electrical.model.constants import (
    REF_ARROW_HEAD_LENGTH,
    REF_ARROW_HEAD_WIDTH,
    REF_ARROW_LENGTH,
)
from schematika.electrical.model.core import Element, Point, Port, Symbol, Vector
from schematika.electrical.model.parts import standard_style, standard_text
from schematika.electrical.model.primitives import Line, Polygon


def ref(
    tag: str = "",
    label: str = "",
    pins: tuple[str, ...] = (),
    direction: str = "up",
    label_pos: str = "left",
    **kwargs,
) -> Symbol:
    """Reference symbol (arrow) to indicate connection to another circuit element.

    Args:
        tag: Auto-generated tag (usually ignored if label is present).
        label: The text to display (e.g. "F1:1"). If empty, uses tag.
        pins: Accepted for CircuitBuilder API compatibility; unused.
        direction: "up" or "down".
        label_pos: Position of the label ("left" or "right").
        **kwargs: Extra arguments for compatibility.

    Raises:
        ValueError: If direction is not "up" or "down".
    """
    if direction not in ("up", "down"):
        raise CircuitValidationError(
            f"direction must be 'up' or 'down', got {direction!r}"
        )

    elements: list[Element] = []
    ports: dict[str, Port] = {}

    text_content = label if label else tag
    origin = Point(0, 0)
    style = standard_style()

    if direction == "up":
        tip = origin
        tail = Point(0, REF_ARROW_LENGTH)

        elements.append(Line(tail, tip, style))

        head_base_y = tip.y + REF_ARROW_HEAD_LENGTH
        p_left = Point(-REF_ARROW_HEAD_WIDTH / 2, head_base_y)
        p_right = Point(REF_ARROW_HEAD_WIDTH / 2, head_base_y)
        elements.append(Polygon([p_left, tip, p_right], style))

        mid_y = REF_ARROW_LENGTH / 2
        elements.append(
            standard_text(text_content, Point(0, mid_y), label_pos=label_pos)
        )

        ports["2"] = Port("2", tail, Vector(0, 1))

    else:
        tip = origin
        tail = Point(0, -REF_ARROW_LENGTH)

        elements.append(Line(tail, tip, style))

        head_base_y = tip.y - REF_ARROW_HEAD_LENGTH
        p_left = Point(-REF_ARROW_HEAD_WIDTH / 2, head_base_y)
        p_right = Point(REF_ARROW_HEAD_WIDTH / 2, head_base_y)
        elements.append(Polygon([p_left, tip, p_right], style))

        mid_y = -REF_ARROW_LENGTH / 2
        elements.append(
            standard_text(text_content, Point(0, mid_y), label_pos=label_pos)
        )

        ports["1"] = Port("1", tail, Vector(0, -1))

    return Symbol(elements=elements, ports=ports, label=text_content)
