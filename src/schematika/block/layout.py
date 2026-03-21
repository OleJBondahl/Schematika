"""
Layout engine for block diagrams.

Simple two-phase approach:
1. resolve_sizes  -- assign dimensions to blocks (user-specified or auto)
2. resolve_placements -- single top-down pass to resolve positions
"""

from __future__ import annotations

from collections import deque

from schematika.block.constants import (
    BLOCK_DEFAULT_HEIGHT,
    BLOCK_GAP,
    BLOCK_LABEL_SIZE,
    BLOCK_MIN_WIDTH,
    CONTAINER_PADDING,
    TAG_LABEL_SIZE,
)
from schematika.block.model import Block, Placement


def _estimate_label_width(label: str, font_size: float) -> float:
    """Rough width estimate: chars * font_size * 0.55."""
    return len(label) * font_size * 0.55


def _compute_contains_size(tags: list[str], max_cols: int = 5) -> tuple[float, float]:
    """Compute width/height for a grid of tag labels inside a block."""
    if not tags:
        return 0.0, 0.0
    n = len(tags)
    cols = min(n, max_cols)
    rows = (n + cols - 1) // cols
    col_width = (
        max(_estimate_label_width(t, TAG_LABEL_SIZE) for t in tags) + TAG_LABEL_SIZE
    )
    row_height = TAG_LABEL_SIZE * 2.0
    return cols * col_width, rows * row_height


def resolve_sizes(all_blocks: list[Block]) -> None:
    """Assign dimensions to blocks. User-specified sizes are never overridden."""
    for b in all_blocks:
        _size_one(b)
    _apply_wide(all_blocks)


def _size_one(b: Block) -> None:
    """Compute size for a single block."""
    if b._user_sized:
        return
    if b.contains:
        cw, ch = _compute_contains_size(b.contains)
        label_w = _estimate_label_width(b.label, BLOCK_LABEL_SIZE)
        inner_w = max(cw, label_w)
        b.width = max(inner_w + CONTAINER_PADDING * 2, BLOCK_MIN_WIDTH)
        b.height = ch + BLOCK_LABEL_SIZE * 3 + CONTAINER_PADDING * 2
    elif b.children:
        label_w = (
            _estimate_label_width(b.label, BLOCK_LABEL_SIZE) + CONTAINER_PADDING * 2
        )
        b.width = max(label_w, BLOCK_MIN_WIDTH)
        b.height = BLOCK_DEFAULT_HEIGHT
    else:
        label_w = _estimate_label_width(b.label, BLOCK_LABEL_SIZE)
        b.width = max(label_w + CONTAINER_PADDING * 2, BLOCK_MIN_WIDTH)
        b.height = BLOCK_DEFAULT_HEIGHT


def _apply_wide(all_blocks: list[Block]) -> None:
    """Stretch wide=True blocks to match the widest sibling."""
    groups: dict[int | None, list[Block]] = {}
    for b in all_blocks:
        pid = id(b.parent) if b.parent else None
        groups.setdefault(pid, []).append(b)

    for siblings in groups.values():
        max_w = max(s.width for s in siblings) if siblings else 0
        for s in siblings:
            if s.wide:
                s.width = max_w


_PAGE_MARGIN = CONTAINER_PADDING * 2


def _build_dependency_graph(
    blocks: list[Block],
) -> tuple[dict[int, Block], dict[int, list[int]], dict[int, int]]:
    """Build adjacency list and in-degree map from placement references."""
    block_set = {id(b) for b in blocks}
    id_to_block: dict[int, Block] = {id(b): b for b in blocks}
    dependents: dict[int, list[int]] = {id(b): [] for b in blocks}
    in_degree: dict[int, int] = {id(b): 0 for b in blocks}

    for b in blocks:
        if b.placement is not None and b.placement.reference is not None:
            ref_id = id(b.placement.reference)
            if ref_id in block_set:
                dependents[ref_id].append(id(b))
                in_degree[id(b)] += 1

    return id_to_block, dependents, in_degree


def _topological_sort_blocks(
    blocks: list[Block],
) -> list[Block]:
    """Return blocks in topological order based on placement dependencies.

    Only considers dependencies among the given blocks.
    Raises ValueError on cycles.
    """
    id_to_block, dependents, in_degree = _build_dependency_graph(blocks)

    queue: deque[int] = deque(bid for bid, deg in in_degree.items() if deg == 0)

    ordered: list[Block] = []
    while queue:
        bid = queue.popleft()
        ordered.append(id_to_block[bid])
        for dep_id in dependents[bid]:
            in_degree[dep_id] -= 1
            if in_degree[dep_id] == 0:
                queue.append(dep_id)

    if len(ordered) != len(blocks):
        unresolved = [id_to_block[bid].label for bid in in_degree if in_degree[bid] > 0]
        raise ValueError(f"Placement cycle detected among blocks: {unresolved}")

    return ordered


def _resolve_one(b: Block) -> None:
    """Resolve a single block's position from its placement."""
    p = b.placement
    if p is None:
        return

    if p.kind == "corner":
        _resolve_corner(b, p)
    elif p.kind in ("next_to", "under"):
        _resolve_next_to(b, p)
    elif p.kind in ("below", "above"):
        _resolve_vertical(b, p)
    elif p.kind in ("right_of", "left_of"):
        _resolve_horizontal(b, p)


def _resolve_next_to(b: Block, p: Placement) -> None:
    """Place block next to (right) or under (below) its reference with a gap."""
    ref = p.reference
    assert ref is not None
    if p.kind == "under":
        b.x = ref.x
        b.y = ref.y + ref.height + p.gap
    else:  # next_to
        b.x = ref.x + ref.width + p.gap
        b.y = ref.y


def _resolve_vertical(b: Block, p: Placement) -> None:
    """Resolve below/above placement."""
    ref = p.reference
    assert ref is not None
    if p.kind == "below":
        b.y = ref.y + ref.height + BLOCK_GAP
    else:
        b.y = ref.y - b.height - BLOCK_GAP
    _apply_align(b, ref, p.align)


def _resolve_horizontal(b: Block, p: Placement) -> None:
    """Resolve right_of/left_of placement."""
    ref = p.reference
    assert ref is not None
    if p.kind == "right_of":
        b.x = ref.x + ref.width + BLOCK_GAP
    else:
        b.x = ref.x - b.width - BLOCK_GAP
    b.y = ref.y


def _apply_align(b: Block, ref: Block, align: str) -> None:
    """Apply horizontal alignment relative to reference."""
    if align == "left":
        b.x = ref.x
    elif align == "right":
        b.x = ref.x + ref.width - b.width
    else:
        b.x = ref.x + ref.width / 2 - b.width / 2


def _resolve_corner(b: Block, p: Placement) -> None:
    """Resolve corner-based placement relative to parent or a reference block."""
    # Use explicit reference if provided, otherwise fall back to parent
    ref = p.reference if p.reference is not None else b.parent
    if ref is None:
        return
    if p.inside:
        _resolve_corner_inside(b, ref, p.corner, p.padding)
    else:
        _resolve_corner_outside(b, ref, p.corner, p.padding)


def _resolve_corner_inside(b: Block, parent: Block, corner: str, pad: float) -> None:
    """Position child inside parent at the given corner."""
    if corner == "top-left":
        b.x, b.y = parent.x + pad, parent.y + pad
    elif corner == "top-right":
        b.x = parent.x + parent.width - b.width - pad
        b.y = parent.y + pad
    elif corner == "bottom-left":
        b.x = parent.x + pad
        b.y = parent.y + parent.height - b.height - pad
    elif corner == "bottom-right":
        b.x = parent.x + parent.width - b.width - pad
        b.y = parent.y + parent.height - b.height - pad
    elif corner == "center":
        b.x = parent.x + parent.width / 2 - b.width / 2
        b.y = parent.y + parent.height / 2 - b.height / 2


def _resolve_corner_outside(b: Block, parent: Block, corner: str, pad: float) -> None:
    """Position child outside parent at the given corner."""
    if corner == "top-left":
        b.x, b.y = parent.x + pad, parent.y - b.height
    elif corner == "top-right":
        b.x = parent.x + parent.width - b.width - pad
        b.y = parent.y - b.height
    elif corner == "bottom-left":
        b.x = parent.x + pad
        b.y = parent.y + parent.height
    elif corner == "bottom-right":
        b.x = parent.x + parent.width - b.width - pad
        b.y = parent.y + parent.height
    elif corner == "center":
        b.x = parent.x + parent.width / 2 - b.width / 2
        b.y = parent.y + parent.height / 2 - b.height / 2


def _shift_descendants(block: Block, dx: float, dy: float) -> None:
    """Shift all descendants of a block by (dx, dy)."""
    for child in block.children:
        child.x += dx
        child.y += dy
        _shift_descendants(child, dx, dy)


def _move_block(block: Block, new_x: float, new_y: float) -> None:
    """Move a block to a new position and shift all its descendants."""
    dx, dy = new_x - block.x, new_y - block.y
    block.x, block.y = new_x, new_y
    _shift_descendants(block, dx, dy)


def _compute_spread_positions(
    blocks: list[Block],
    margin: float,
    usable_width: float,
    weights: list[float] | None,
) -> list[float]:
    """Compute x positions for blocks in a spread group."""
    n = len(blocks)
    if n == 1:
        return [margin + usable_width / 2 - blocks[0].width / 2]

    if weights:
        total_weight = sum(weights)
        col_widths = [usable_width * w / total_weight for w in weights]
        positions: list[float] = []
        x = margin
        for i, b in enumerate(blocks):
            positions.append(x + col_widths[i] / 2 - b.width / 2)
            x += col_widths[i]
        return positions

    total_block_width = sum(b.width for b in blocks)
    total_gap = usable_width - total_block_width
    gap = max(total_gap / (n - 1), BLOCK_GAP)
    positions = []
    x = margin
    for b in blocks:
        positions.append(x)
        x += b.width + gap
    return positions


def _resolve_spread_groups(
    spread_groups: list[tuple[list[Block], Block, list[float] | None]],
    page_width: float,
) -> None:
    """Distribute spread groups across the page width.

    When a spread block moves, ALL its descendants move by the same delta.
    """
    margin = _PAGE_MARGIN
    usable_width = page_width - 2 * margin

    for blocks, ref, weights in spread_groups:
        if not blocks:
            continue

        y = ref.y + ref.height + BLOCK_GAP
        x_positions = _compute_spread_positions(blocks, margin, usable_width, weights)

        for b, new_x in zip(blocks, x_positions, strict=True):
            _move_block(b, new_x, y)


def resolve_placements(
    all_blocks: list[Block],
    spread_groups: list[tuple[list[Block], Block, list[float] | None]] | None = None,
    page_width: float = 420.0,
) -> None:
    """Single-pass placement resolution. Modifies blocks in place.

    1. Place root blocks, resolve root-level placements
    2. For each container: place unplaced children, resolve placed children
    3. Apply spread groups (shift containers + descendants)
    4. Re-resolve external placements affected by spread
    """
    # Separate roots from children
    roots = [b for b in all_blocks if b.parent is None]

    # Step 1: Place root blocks and resolve root-level placements
    _place_roots(roots)

    # Step 2: Layout children inside each container (recursive)
    for b in roots:
        if b.children:
            _layout_container_children(b)

    # Step 3: Apply spread groups
    if spread_groups:
        _resolve_spread_groups(spread_groups, page_width)
        _re_resolve_after_spread(roots, spread_groups)


def _place_roots(roots: list[Block]) -> None:
    """Place unplaced root blocks, then resolve placed ones in topo order."""
    ordered = _topological_sort_blocks(roots)

    next_x = _PAGE_MARGIN
    for b in ordered:
        if b.placement is None:
            b.x = next_x
            b.y = _PAGE_MARGIN
            next_x += b.width + BLOCK_GAP

    for b in ordered:
        if b.placement is not None:
            _resolve_one(b)


def _categorize_children(
    children: list[Block],
) -> tuple[list[Block], list[Block], list[Block], list[Block]]:
    """Split children into corner, unplaced, other-placed, and next_to groups."""
    corner: list[Block] = []
    next_to: list[Block] = []
    other: list[Block] = []
    unplaced: list[Block] = []
    for child in children:
        if child.placement is None:
            unplaced.append(child)
        elif child.placement.kind == "corner" and child.placement.reference is None:
            # Corner relative to parent — no dependency, resolve first
            corner.append(child)
        elif child.placement.kind == "corner" and child.placement.reference is not None:
            # Corner relative to a sibling — needs sibling resolved first
            other.append(child)
        elif child.placement.kind in ("next_to", "under"):
            next_to.append(child)
        else:
            other.append(child)
    return corner, unplaced, other, next_to


def _layout_container_children(parent: Block) -> None:
    """Place children inside a container with priority ordering.

    Processing order:
    1. Corner-placed children (depend only on parent)
    2. Unplaced children (stack horizontally)
    3. Other placed children (below, right_of, etc.)
    4. next_to children (depend on sibling, in chain order)

    Recurses into nested containers.
    """
    corner, unplaced, other_placed, next_to = _categorize_children(parent.children)

    for child in corner:
        _resolve_one(child)

    cx = parent.x + CONTAINER_PADDING
    cy = parent.y + CONTAINER_PADDING + BLOCK_LABEL_SIZE * 2
    for child in unplaced:
        child.x = cx
        child.y = cy
        cx += child.width + BLOCK_GAP

    for child in _topological_sort_blocks(other_placed):
        _resolve_one(child)

    for child in _topological_sort_blocks(next_to):
        _resolve_one(child)

    for child in parent.children:
        if child.children:
            _layout_container_children(child)


def _re_resolve_after_spread(
    roots: list[Block],
    spread_groups: list[tuple[list[Block], Block, list[float] | None]],
) -> None:
    """Re-resolve placements for root blocks not in spread groups.

    After resolving each block, also re-layout its children so they
    move with it.
    """
    ordered = _topological_sort_blocks(roots)
    for b in ordered:
        if b.placement is not None:
            if not _is_spread_member(b, spread_groups):
                _resolve_one(b)
                # Re-layout children inside this block
                if b.children:
                    _layout_container_children(b)


def _is_spread_member(
    block: Block,
    spread_groups: list[tuple[list[Block], Block, list[float] | None]],
) -> bool:
    """Check if a block is directly in a spread group."""
    for blocks, _ref, _weights in spread_groups:
        if block in blocks:
            return True
    return False
