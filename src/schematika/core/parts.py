"""Reusable parts and factory functions for IEC 60617 electrical symbols."""

from collections.abc import Callable
from dataclasses import replace
from typing import TYPE_CHECKING, Any

import deal

from schematika._purity import pure

if TYPE_CHECKING:
    from schematika.core.primitives import Line

from typing import Final

from schematika.core.constants import (
    COLOR_BLACK,
    DEFAULT_POLE_SPACING,
    GRID_SIZE,
    LINE_WIDTH_THIN,
    PIN_LABEL_OFFSET_X,
    PIN_LABEL_OFFSET_Y_ADJUST,
    TERMINAL_RADIUS,
    TERMINAL_TEXT_OFFSET_X,
    TERMINAL_TEXT_OFFSET_X_CLOSE,
    TERMINAL_TEXT_SIZE,
    TEXT_FONT_FAMILY,
    TEXT_FONT_FAMILY_AUX,
    TEXT_OFFSET_X,
    TEXT_SIZE_MAIN,
    TEXT_SIZE_PIN,
)
from schematika.core.geometry import Point, Style
from schematika.core.primitives import Circle, Element, Polygon, Text
from schematika.core.symbol import Symbol
from schematika.core.transform import translate

# Tolerance used to classify port directions (up vs. down).
_PORT_DIRECTION_THRESHOLD: Final = 0.1


@deal.pure
def standard_style(*, filled: bool = False) -> Style:
    """Standard symbol style; `filled=True` paints solid black, otherwise no fill."""
    return Style(
        stroke=COLOR_BLACK,
        stroke_width=LINE_WIDTH_THIN,
        fill=COLOR_BLACK if filled else "none",
    )


@deal.pure
def create_pin_label_text(
    content: str,
    position: Point,
    anchor: str = "start",
) -> "Text":
    """Pin-label text with standard styling."""
    from schematika.core.primitives import Text

    return Text(
        content=content,
        position=position,
        font_size=TEXT_SIZE_PIN,
        style=Style(
            stroke="none",
            fill=COLOR_BLACK,
            font_family=TEXT_FONT_FAMILY_AUX,
        ),
        anchor=anchor,
    )


@deal.pure
def create_label_text(
    content: str,
    position: Point,
    font_size: float,
    anchor: str = "middle",
    dominant_baseline: str = "auto",
    font_family: str = TEXT_FONT_FAMILY,
) -> Text:
    """Create a styled label text element (black fill, no stroke)."""
    return Text(
        content=content,
        position=position,
        font_size=font_size,
        anchor=anchor,
        dominant_baseline=dominant_baseline,
        style=Style(stroke="none", fill=COLOR_BLACK, font_family=font_family),
    )


@deal.pure
def standard_text(content: str, parent_origin: Point, label_pos: str = "left") -> Text:
    """Component label text; `label_pos` is `"left"` or `"right"` of the symbol."""
    if label_pos == "right":
        pos = Point(parent_origin.x - TEXT_OFFSET_X, parent_origin.y)
        anchor = "start"
    else:
        pos = Point(parent_origin.x + TEXT_OFFSET_X, parent_origin.y)
        anchor = "end"

    return Text(
        content=content,
        position=pos,
        anchor=anchor,
        font_size=TEXT_SIZE_MAIN,
        style=Style(stroke="none", fill=COLOR_BLACK, font_family=TEXT_FONT_FAMILY),
    )


@deal.pure
def terminal_text(
    content: str,
    parent_origin: Point,
    label_pos: str = "left",
    pin_label_pos: str | None = None,
) -> Text:
    """Smaller and farther than `standard_text` to avoid pin-number collisions."""
    if pin_label_pos is not None and pin_label_pos != label_pos:
        offset = TERMINAL_TEXT_OFFSET_X_CLOSE
    else:
        offset = TERMINAL_TEXT_OFFSET_X

    if label_pos == "right":
        pos = Point(parent_origin.x - offset, parent_origin.y)
        anchor = "start"
    else:
        pos = Point(parent_origin.x + offset, parent_origin.y)
        anchor = "end"

    return Text(
        content=content,
        position=pos,
        anchor=anchor,
        font_size=TERMINAL_TEXT_SIZE,
        style=Style(stroke="none", fill=COLOR_BLACK, font_family=TEXT_FONT_FAMILY),
    )


@deal.pure
def terminal_circle(center: Point | None = None, *, filled: bool = False) -> Element:
    """`filled=True` marks a connected point; unfilled marks a loose end."""
    if center is None:
        center = Point(0, 0)
    return Circle(center, TERMINAL_RADIUS, standard_style(filled=filled))


@deal.pure
def create_extended_blade(
    start: Point,
    target: Point,
    style: Style,
    extension: float = GRID_SIZE / 4,
) -> "Line":
    """Used for NC/SPDT blade geometry; zero-length input returns a zero-length line."""
    from schematika.core.primitives import Line

    dx = target.x - start.x
    dy = target.y - start.y
    length = (dx**2 + dy**2) ** 0.5
    if length == 0:
        return Line(start, target, style)
    scale = (length + extension) / length
    end = Point(start.x + dx * scale, start.y + dy * scale)
    return Line(start, end, style)


@deal.pure
def box(center: Point, width: float, height: float, *, filled: bool = False) -> Element:
    """Rectangular box centered at a point."""
    half_w = width / 2
    half_h = height / 2

    x1, y1 = center.x - half_w, center.y - half_h
    x2, y2 = center.x + half_w, center.y + half_h

    # Create points for Polygon
    p1 = Point(x1, y1)
    p2 = Point(x2, y1)
    p3 = Point(x2, y2)
    p4 = Point(x1, y2)

    return Polygon(points=[p1, p2, p3, p4], style=standard_style(filled=filled))


@deal.pure
def create_pin_labels(ports: dict[str, Any], pins: tuple[str, ...]) -> list[Text]:
    """Labels are assigned in port insertion order; empty `""` skips a label."""
    labels = []
    # Sort port keys to have deterministic mapping
    # Use insertion order (Python 3.7+ dict ordering) instead of alphabetical
    p_keys = list(ports.keys())

    for i, p_key in enumerate(p_keys):
        if i >= len(pins):
            break

        p_text = str(pins[i])

        # Skip creating label if pin text is empty
        if not p_text:
            continue

        port = ports[p_key]

        # Position logic
        # Default: Left (-X)  # noqa: ERA001
        pos_x = port.position.x - PIN_LABEL_OFFSET_X
        pos_y = port.position.y

        # Inward shift based on direction
        # If dir is UP (0, -1), move DOWN (y+)
        if port.direction.dy < -_PORT_DIRECTION_THRESHOLD:  # UP
            pos_y += PIN_LABEL_OFFSET_Y_ADJUST
        elif port.direction.dy > _PORT_DIRECTION_THRESHOLD:  # DOWN
            pos_y -= PIN_LABEL_OFFSET_Y_ADJUST

        labels.append(
            Text(
                content=p_text,
                position=Point(pos_x, pos_y),
                anchor="end",
                font_size=TEXT_SIZE_PIN,
                style=Style(
                    stroke="none", fill=COLOR_BLACK, font_family=TEXT_FONT_FAMILY_AUX
                ),
            )
        )

    return labels


@pure
def _add_remapped_ports(
    symbol: Symbol, in_key: str, out_key: str, port_ids: tuple[str, str], target: dict
) -> None:
    """Copies *in_key*/*out_key* from `symbol.ports` into *target* under *port_ids*."""
    if in_key in symbol.ports:
        p = symbol.ports[in_key]
        new_id = port_ids[0]
        target[new_id] = replace(p, id=new_id)
    if out_key in symbol.ports:
        p = symbol.ports[out_key]
        new_id = port_ids[1]
        target[new_id] = replace(p, id=new_id)


@deal.pure
def pad_pins(pins: tuple[str, ...], count: int, fill: str = "") -> list[str]:
    """Pad a pin tuple to *count* entries with *fill* value."""
    result = list(pins)
    while len(result) < count:
        result.append(fill)
    return result


@pure
def multipole(
    single_pole_func: Callable[..., Symbol],
    poles: int,
    pole_spacing: float = DEFAULT_POLE_SPACING,
) -> Callable[..., Symbol]:
    """N-pole factory: stamps poles horizontally; ports renumbered 1..2N."""
    if poles < 1:
        msg = f"poles must be >= 1, got {poles}"
        raise ValueError(msg)
    if pole_spacing <= 0:
        msg = f"pole_spacing must be positive, got {pole_spacing}"
        raise ValueError(msg)

    expected_pins = poles * 2
    default_pins = tuple(str(i) for i in range(1, expected_pins + 1))

    def _factory(
        label: str = "",
        pins: tuple[str, ...] = default_pins,
        **kwargs: Any,  # noqa: ANN401
    ) -> Symbol:
        if len(pins) != expected_pins:
            msg = (
                f"{poles}-pole symbol requires "
                f"{expected_pins} pin labels, got {len(pins)}"
            )
            raise ValueError(msg)

        all_elements: list[Element] = []
        new_ports: dict = {}

        for i in range(poles):
            pole_label = label if i == 0 else ""
            pole_pins = (pins[i * 2], pins[i * 2 + 1])
            pole_sym = single_pole_func(label=pole_label, pins=pole_pins, **kwargs)

            if i > 0:
                pole_sym = translate(pole_sym, pole_spacing * i, 0)

            all_elements.extend(pole_sym.elements)

            port_ids = (str(i * 2 + 1), str(i * 2 + 2))
            _add_remapped_ports(pole_sym, "1", "2", port_ids, new_ports)

        return Symbol(elements=all_elements, ports=new_ports, label=label)

    return _factory


@deal.pure
def draw_rectangle(
    x1: float, y1: float, x2: float, y2: float, style: Style
) -> list["Line"]:
    """Create 4 lines forming a rectangle from diagonal corners."""
    from schematika.core.primitives import Line

    tl, tr = Point(x1, y1), Point(x2, y1)
    br, bl = Point(x2, y2), Point(x1, y2)
    return [
        Line(tl, tr, style),
        Line(tr, br, style),
        Line(br, bl, style),
        Line(bl, tl, style),
    ]
