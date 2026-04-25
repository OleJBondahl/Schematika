"""SVG rendering for block diagrams.

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
from schematika.core.parts import draw_rectangle
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

    elements.extend(draw_rectangle(x1, y1, x2, y2, rect_style))

    # Label placement:
    # - Leaf blocks: centered vertically
    # - Blocks with children: at the bottom (children fill the top)
    # - Blocks with contains (old tag grid): below the label padding
    label_style = Style(stroke="none", fill="black")
    if b.children:
        label_y = y2 - CONTAINER_PADDING
    elif b.contains:
        label_y = y1 + CONTAINER_PADDING + BLOCK_LABEL_SIZE
    else:
        label_y = y1 + b.height / 2

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

        # Box
        elements.extend(
            draw_rectangle(
                tx - half_w, ty - half_h, tx + half_w, ty + half_h, box_style
            )
        )

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

    # Determine direction: explicit from_side overrides auto-detection
    first_side = ref.from_side
    if first_side in ("left", "right"):
        horizontal = True
    elif first_side in ("top", "bottom"):
        horizontal = False
    else:
        horizontal = abs(dx) >= abs(dy)

    n = len(cables)
    # Offsets centered around 0
    offsets = [(i - (n - 1) / 2) * CABLE_BUNDLE_SPACING for i in range(n)]

    for idx, (cable, offset) in enumerate(zip(cables, offsets, strict=True)):
        elems = _route_one_cable(cable, horizontal, offset, cx1, cy1, cx2, cy2, idx, n)
        elements.extend(elems)

    return elements


def _determine_sides(
    cable: Cable, horizontal: bool, cx1: float, cy1: float, cx2: float, cy2: float
) -> tuple[str, str]:
    """Determine exit/entry sides for a cable, using explicit or auto."""
    if cable.from_side and cable.to_side:
        return cable.from_side, cable.to_side
    if horizontal:
        if cx2 >= cx1:
            return cable.from_side or "right", cable.to_side or "left"
        return cable.from_side or "left", cable.to_side or "right"
    if cy2 >= cy1:
        return cable.from_side or "bottom", cable.to_side or "top"
    return cable.from_side or "top", cable.to_side or "bottom"


def _edge_point(block: Block, side: str, offset: float, horizontal: bool) -> Point:
    """Get the point where a cable exits/enters a block edge."""
    cx = block.x + block.width / 2
    cy = block.y + block.height / 2
    if side == "right":
        return Point(block.x + block.width, cy + (offset if horizontal else 0))
    if side == "left":
        return Point(block.x, cy + (offset if horizontal else 0))
    if side == "bottom":
        return Point(cx + (offset if not horizontal else 0), block.y + block.height)
    # top
    return Point(cx + (offset if not horizontal else 0), block.y)


def _label_position(
    start: Point, end: Point, pos: str, offset: float
) -> tuple[float, float]:
    """Compute label x,y based on position preference."""
    if pos == "start":
        t = 0.15
    elif pos == "end":
        t = 0.85
    else:  # middle
        t = 0.5
    return start.x + t * (end.x - start.x), start.y + t * (end.y - start.y)


def _route_one_cable(
    cable: Cable,
    horizontal: bool,
    offset: float,
    cx1: float,
    cy1: float,
    cx2: float,
    cy2: float,
    bundle_index: int = 0,
    bundle_size: int = 1,
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

    from_side, to_side = _determine_sides(cable, horizontal, cx1, cy1, cx2, cy2)

    # Strictly horizontal or vertical — endpoints touch block edges
    if horizontal:
        # Y: use from_block's center Y + offset (cable touches from_block edge)
        y = cy1 + offset
        start = Point(fb.x + fb.width, y) if from_side == "right" else Point(fb.x, y)
        end = Point(tb.x, y) if to_side == "left" else Point(tb.x + tb.width, y)
    else:
        # X: use from_block's center X + offset (cable touches from_block edge)
        x = cx1 + offset
        start = Point(x, fb.y + fb.height) if from_side == "bottom" else Point(x, fb.y)
        end = Point(x, tb.y) if to_side == "top" else Point(x, tb.y + tb.height)

    elements.append(Line(start=start, end=end, style=line_style))

    if cable.label:
        # Stagger labels along the cable to avoid overlap in bundles
        if bundle_size > 1 and cable.label_pos == "middle":
            # Spread labels from 0.2 to 0.8 along the cable
            t = 0.2 + 0.6 * bundle_index / max(bundle_size - 1, 1)
            lx = start.x + t * (end.x - start.x)
            ly = start.y + t * (end.y - start.y)
        else:
            lx, ly = _label_position(start, end, cable.label_pos, offset)
        if horizontal:
            ly -= CABLE_LABEL_OFFSET + cable.style.stroke_width
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
            lx += CABLE_LABEL_OFFSET + cable.style.stroke_width
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
