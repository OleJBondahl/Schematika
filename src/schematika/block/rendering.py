"""
SVG rendering for block diagrams.

Converts resolved Block/Cable data into core Element primitives.
"""

from __future__ import annotations

from collections import defaultdict

from schematika.block.constants import (
    BLOCK_LABEL_SIZE,
    BLOCK_STROKE_WIDTH,
    CABLE_BUNDLE_SPACING,
    CABLE_LABEL_OFFSET,
    CONTAINER_PADDING,
    LEGEND_ENTRY_HEIGHT,
    LEGEND_LINE_SAMPLE_LENGTH,
    NOTE_TEXT_SIZE,
    TAG_BOX_PADDING,
    TAG_LABEL_SIZE,
)
from schematika.block.model import (
    CABLE_TYPE_STYLES,
    Block,
    Cable,
    CableStyle,
)
from schematika.core.geometry import Element, Point, Style
from schematika.core.primitives import Line, Text


def render_blocks(blocks: list[Block]) -> list[Element]:
    """Render block rectangles with labels and contained tags."""
    elements: list[Element] = []
    for b in blocks:
        elements.extend(_render_one_block(b))
    return elements


def _render_one_block(b: Block) -> list[Element]:
    """Render a single block as rectangle + label + tags."""
    elements: list[Element] = []

    rect_style = Style(
        stroke=b.style.color,
        stroke_width=BLOCK_STROKE_WIDTH,
        fill=b.style.fill,
        stroke_dasharray=b.style.dash_pattern,
    )

    # Rectangle corners
    x1, y1 = b.x, b.y
    x2, y2 = b.x + b.width, b.y + b.height

    tl = Point(x1, y1)
    tr = Point(x2, y1)
    br = Point(x2, y2)
    bl = Point(x1, y2)

    elements.append(Line(start=tl, end=tr, style=rect_style))
    elements.append(Line(start=tr, end=br, style=rect_style))
    elements.append(Line(start=br, end=bl, style=rect_style))
    elements.append(Line(start=bl, end=tl, style=rect_style))

    # Label at top center of block
    label_style = Style(stroke="none", fill="black")
    label_y = y1 + CONTAINER_PADDING if b.children else y1 + b.height / 2
    if b.contains:
        label_y = y1 + CONTAINER_PADDING + BLOCK_LABEL_SIZE

    elements.append(
        Text(
            content=b.label,
            position=Point(x1 + b.width / 2, label_y),
            style=label_style,
            anchor="middle",
            dominant_baseline="central",
            font_size=BLOCK_LABEL_SIZE,
            rotation=b.rotation,
        )
    )

    # Note annotation
    if b.note:
        elements.append(
            Text(
                content=b.note,
                position=Point(x2 - CONTAINER_PADDING, y1 + CONTAINER_PADDING),
                style=Style(stroke="none", fill="gray"),
                anchor="end",
                dominant_baseline="central",
                font_size=TAG_LABEL_SIZE,
            )
        )

    # Contained tags grid
    if b.contains:
        _render_tags(elements, b)

    return elements


def _render_tags(elements: list[Element], b: Block) -> None:
    """Render device tags as a grid of small boxed labels inside a block."""
    tags = b.contains
    if not tags:
        return

    max_cols = 5
    n = len(tags)
    cols = min(n, max_cols)

    tag_text_style = Style(stroke="none", fill="black")
    box_style = Style(
        stroke="black",
        stroke_width=BLOCK_STROKE_WIDTH * 0.5,
        fill="none",
    )
    start_y = b.y + CONTAINER_PADDING + BLOCK_LABEL_SIZE * 3
    col_width = b.width / (cols + 1)

    for i, tag in enumerate(tags):
        col = i % cols
        row = i // cols
        tx = b.x + col_width * (col + 1)
        ty = start_y + row * TAG_LABEL_SIZE * 2.0

        # Estimate box dimensions from text
        text_w = len(tag) * TAG_LABEL_SIZE * 0.55
        half_w = text_w / 2 + TAG_BOX_PADDING
        half_h = TAG_LABEL_SIZE / 2 + TAG_BOX_PADDING

        # Box corners
        tl = Point(tx - half_w, ty - half_h)
        tr = Point(tx + half_w, ty - half_h)
        br = Point(tx + half_w, ty + half_h)
        bl = Point(tx - half_w, ty + half_h)
        elements.append(Line(start=tl, end=tr, style=box_style))
        elements.append(Line(start=tr, end=br, style=box_style))
        elements.append(Line(start=br, end=bl, style=box_style))
        elements.append(Line(start=bl, end=tl, style=box_style))

        elements.append(
            Text(
                content=tag,
                position=Point(tx, ty),
                style=tag_text_style,
                anchor="middle",
                dominant_baseline="central",
                font_size=TAG_LABEL_SIZE,
                rotation=b.rotation,
            )
        )


def render_cables(cables: list[Cable], all_blocks: list[Block]) -> list[Element]:
    """Render cables with bundling for cables between the same block pair."""
    elements: list[Element] = []

    # Group cables by unordered (from, to) pair
    groups: dict[tuple[int, int], list[Cable]] = defaultdict(list)
    for c in cables:
        key = _cable_pair_key(c)
        groups[key].append(c)

    for group in groups.values():
        elements.extend(_render_cable_bundle(group))

    return elements


def _cable_pair_key(c: Cable) -> tuple[int, int]:
    """Return an order-independent key for a cable's block pair."""
    a, b = id(c.from_block), id(c.to_block)
    return (min(a, b), max(a, b))


def _block_center(b: Block) -> tuple[float, float]:
    return b.x + b.width / 2, b.y + b.height / 2


def _render_cable_bundle(cables: list[Cable]) -> list[Element]:
    """Render a bundle of cables between the same pair of blocks."""
    elements: list[Element] = []
    if not cables:
        return elements

    ref = cables[0]
    cx1, cy1 = _block_center(ref.from_block)
    cx2, cy2 = _block_center(ref.to_block)

    dx = cx2 - cx1
    dy = cy2 - cy1

    # Determine if primarily horizontal or vertical
    horizontal = abs(dx) >= abs(dy)

    n = len(cables)
    # Offsets centered around 0
    offsets = [(i - (n - 1) / 2) * CABLE_BUNDLE_SPACING for i in range(n)]

    for cable, offset in zip(cables, offsets, strict=True):
        elems = _route_one_cable(cable, horizontal, offset, cx1, cy1, cx2, cy2)
        elements.extend(elems)

    return elements


def _route_one_cable(
    cable: Cable,
    horizontal: bool,
    offset: float,
    cx1: float,
    cy1: float,
    cx2: float,
    cy2: float,
) -> list[Element]:
    """Route a single cable with offset for bundling."""
    elements: list[Element] = []
    fb = cable.from_block
    tb = cable.to_block

    line_style = Style(
        stroke=cable.style.color,
        stroke_width=cable.style.stroke_width,
        fill="none",
        stroke_dasharray=cable.style.dash_pattern,
    )
    label_style = Style(stroke="none", fill=cable.style.color)

    if horizontal:
        # Exit from right/left edges
        if cx2 >= cx1:
            start_x = fb.x + fb.width
            end_x = tb.x
        else:
            start_x = fb.x
            end_x = tb.x + tb.width

        y_mid = (cy1 + cy2) / 2 + offset
        start = Point(start_x, y_mid)
        end = Point(end_x, y_mid)

        elements.append(Line(start=start, end=end, style=line_style))

        # Label above the line at midpoint
        if cable.label:
            lx = (start_x + end_x) / 2
            ly = y_mid - CABLE_LABEL_OFFSET - cable.style.stroke_width
            elements.append(
                Text(
                    content=cable.label,
                    position=Point(lx, ly),
                    style=label_style,
                    anchor="middle",
                    font_size=NOTE_TEXT_SIZE,
                )
            )
    else:
        # Exit from top/bottom edges
        if cy2 >= cy1:
            start_y = fb.y + fb.height
            end_y = tb.y
        else:
            start_y = fb.y
            end_y = tb.y + tb.height

        x_mid = (cx1 + cx2) / 2 + offset
        start = Point(x_mid, start_y)
        end = Point(x_mid, end_y)

        elements.append(Line(start=start, end=end, style=line_style))

        # Label to the right of the line at midpoint
        if cable.label:
            lx = x_mid + CABLE_LABEL_OFFSET + cable.style.stroke_width
            ly = (start_y + end_y) / 2
            elements.append(
                Text(
                    content=cable.label,
                    position=Point(lx, ly),
                    style=label_style,
                    anchor="start",
                    font_size=NOTE_TEXT_SIZE,
                    rotation=270,
                )
            )

    return elements


def render_legend(
    cable_styles_used: list[CableStyle],
    origin_x: float = 0.0,
    origin_y: float = 0.0,
) -> list[Element]:
    """Render a legend showing the cable styles used."""
    if not cable_styles_used:
        return []

    elements: list[Element] = []
    text_style = Style(stroke="none", fill="black")

    # Deduplicate while preserving order
    seen: set[tuple[float, str, str | None]] = set()
    unique: list[CableStyle] = []
    for cs in cable_styles_used:
        key = (cs.stroke_width, cs.color, cs.dash_pattern)
        if key not in seen:
            seen.add(key)
            unique.append(cs)

    # Reverse lookup for labels
    style_labels: dict[tuple[float, str, str | None], str] = {}
    for name, cs in CABLE_TYPE_STYLES.items():
        key = (cs.stroke_width, cs.color, cs.dash_pattern)
        if key not in style_labels:
            style_labels[key] = name.replace("_", " ").title()

    y = origin_y
    for cs in unique:
        line_style = Style(
            stroke=cs.color,
            stroke_width=cs.stroke_width,
            fill="none",
            stroke_dasharray=cs.dash_pattern,
        )
        elements.append(
            Line(
                start=Point(origin_x, y),
                end=Point(origin_x + LEGEND_LINE_SAMPLE_LENGTH, y),
                style=line_style,
            )
        )
        key = (cs.stroke_width, cs.color, cs.dash_pattern)
        label = style_labels.get(key, "Cable")
        elements.append(
            Text(
                content=label,
                position=Point(
                    origin_x + LEGEND_LINE_SAMPLE_LENGTH + NOTE_TEXT_SIZE, y
                ),
                style=text_style,
                anchor="start",
                dominant_baseline="central",
                font_size=NOTE_TEXT_SIZE,
            )
        )
        y += LEGEND_ENTRY_HEIGHT

    return elements


def render_notes(
    notes: list[str] | None,
    abbreviations: dict[str, str] | None,
    origin_x: float = 0.0,
    origin_y: float = 0.0,
) -> list[Element]:
    """Render notes and abbreviations text."""
    elements: list[Element] = []
    text_style = Style(stroke="none", fill="black")
    y = origin_y

    if notes:
        for note in notes:
            elements.append(
                Text(
                    content=note,
                    position=Point(origin_x, y),
                    style=text_style,
                    anchor="start",
                    dominant_baseline="central",
                    font_size=NOTE_TEXT_SIZE,
                )
            )
            y += LEGEND_ENTRY_HEIGHT

    if abbreviations:
        y += LEGEND_ENTRY_HEIGHT * 0.5
        for abbr, meaning in abbreviations.items():
            elements.append(
                Text(
                    content=f"{abbr} - {meaning}",
                    position=Point(origin_x, y),
                    style=text_style,
                    anchor="start",
                    dominant_baseline="central",
                    font_size=NOTE_TEXT_SIZE,
                )
            )
            y += LEGEND_ENTRY_HEIGHT

    return elements
