"""Factory functions for cross-reference arrow symbols.

Provides symbol factories for page cross-reference arrows (jump-in and
jump-out) used to link related circuits across pages. Raises
``CircuitValidationError`` on invalid configuration.
"""

from typing import Any

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
    pins: tuple[str, ...] = (),  # noqa: ARG001
    direction: str = "up",
    label_pos: str = "left",
    **kwargs: Any,  # noqa: ANN401, ARG001
) -> Symbol:
    """Cross-reference arrow linking two points across circuits or pages.

    ``direction="up"`` creates a jump-in arrow (port ``"2"`` at the tail);
    ``direction="down"`` creates a jump-out arrow (port ``"1"`` at the tail).
    Exactly one port is exposed per symbol.

    Ports:
        2: wire connection point for direction="up" (tail at bottom).
        1: wire connection point for direction="down" (tail at top).

    Args:
        tag: Auto-generated tag used as label when ``label`` is empty.
        label: Text displayed alongside the arrow, e.g. ``"F1:1"``.
        pins: Accepted for :class:`~schematika.electrical.CircuitBuilder`
            API compatibility; not used.
        direction: ``"up"`` (jump-in, port ``"2"``) or ``"down"`` (jump-out,
            port ``"1"``).
        label_pos: Side for the label text: ``"left"`` or ``"right"``.
        **kwargs: Extra keyword arguments accepted for compatibility; ignored.

    Returns:
        Symbol with one port (``"2"`` for up, ``"1"`` for down).

    Raises:
        CircuitValidationError: If ``direction`` is not ``"up"`` or ``"down"``.

    Examples:
        >>> from schematika.electrical.symbols import ref
        >>> sym_up = ref(label="F1:1", direction="up")
        >>> list(sym_up.ports.keys())
        ['2']
        >>> sym_down = ref(label="F1:1", direction="down")
        >>> list(sym_down.ports.keys())
        ['1']
    """
    if direction not in ("up", "down"):
        msg = f"direction must be 'up' or 'down', got {direction!r}"
        raise CircuitValidationError(msg)

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
