"""
Layout engine for block diagrams.

Two phases:
1. resolve_sizes -- bottom-up: compute block dimensions from content/children
2. resolve_placements -- topological sort on placement dependency graph
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
from schematika.block.model import Block


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
    """Bottom-up size resolution. Modifies blocks in place."""
    # Process leaves first, then containers. We do multiple passes:
    # walk from deepest nesting level upward.
    # Collect blocks by depth.
    depth_map: dict[int, list[Block]] = {}
    for b in all_blocks:
        d = _depth(b)
        depth_map.setdefault(d, []).append(b)

    # Process from deepest to shallowest
    for depth in sorted(depth_map.keys(), reverse=True):
        for b in depth_map[depth]:
            _size_one(b)

    # wide=True: stretch to widest sibling at same level within same parent
    _apply_wide(all_blocks)


def _depth(b: Block) -> int:
    d = 0
    p = b.parent
    while p is not None:
        d += 1
        p = p.parent
    return d


def _size_one(b: Block) -> None:
    """Compute size for a single block."""
    if b.children:
        # Container: will be sized after children are placed.
        # Set a minimum so placement can proceed; the actual size is
        # finalized after resolve_placements lays out children.
        # For now give it a preliminary size based on label.
        label_w = (
            _estimate_label_width(b.label, BLOCK_LABEL_SIZE) + CONTAINER_PADDING * 2
        )
        b.width = max(label_w, BLOCK_MIN_WIDTH)
        b.height = BLOCK_DEFAULT_HEIGHT
    elif b.contains:
        cw, ch = _compute_contains_size(b.contains)
        label_w = _estimate_label_width(b.label, BLOCK_LABEL_SIZE)
        inner_w = max(cw, label_w)
        b.width = max(inner_w + CONTAINER_PADDING * 2, BLOCK_MIN_WIDTH)
        b.height = ch + BLOCK_LABEL_SIZE * 3 + CONTAINER_PADDING * 2
    else:
        label_w = _estimate_label_width(b.label, BLOCK_LABEL_SIZE)
        b.width = max(label_w + CONTAINER_PADDING * 2, BLOCK_MIN_WIDTH)
        b.height = BLOCK_DEFAULT_HEIGHT


def _apply_wide(all_blocks: list[Block]) -> None:
    """Stretch wide=True blocks to match the widest sibling."""
    # Group by parent
    groups: dict[int | None, list[Block]] = {}
    for b in all_blocks:
        pid = id(b.parent) if b.parent else None
        groups.setdefault(pid, []).append(b)

    for siblings in groups.values():
        max_w = max(s.width for s in siblings) if siblings else 0
        for s in siblings:
            if s.wide:
                s.width = max_w


def _topological_sort(
    all_blocks: list[Block],
) -> tuple[list[int], dict[int, Block]]:
    """Build dependency graph and return topological order.

    Raises ValueError on cycles.
    """
    block_set = {id(b) for b in all_blocks}
    id_to_block: dict[int, Block] = {id(b): b for b in all_blocks}

    dependents: dict[int, list[int]] = {id(b): [] for b in all_blocks}
    in_degree: dict[int, int] = {id(b): 0 for b in all_blocks}

    for b in all_blocks:
        if b.placement is not None:
            ref_id = id(b.placement.reference)
            if ref_id not in block_set:
                raise ValueError(
                    f"Block '{b.label}' references "
                    f"'{b.placement.reference.label}' "
                    f"which is not in the diagram"
                )
            dependents[ref_id].append(id(b))
            in_degree[id(b)] += 1

    queue: deque[int] = deque()
    for bid, deg in in_degree.items():
        if deg == 0:
            queue.append(bid)

    resolved_order: list[int] = []
    while queue:
        bid = queue.popleft()
        resolved_order.append(bid)
        for dep_id in dependents[bid]:
            in_degree[dep_id] -= 1
            if in_degree[dep_id] == 0:
                queue.append(dep_id)

    if len(resolved_order) != len(all_blocks):
        unresolved = [id_to_block[bid].label for bid in in_degree if in_degree[bid] > 0]
        raise ValueError(f"Placement cycle detected among blocks: {unresolved}")

    return resolved_order, id_to_block


def _place_in_order(resolved_order: list[int], id_to_block: dict[int, Block]) -> None:
    """Place blocks in topological order, stacking unplaced root blocks."""
    next_x = CONTAINER_PADDING
    for bid in resolved_order:
        b = id_to_block[bid]
        if b.placement is None:
            if b.parent is None:
                b.x = next_x
                b.y = CONTAINER_PADDING
                next_x += b.width + BLOCK_GAP
        else:
            _resolve_one(b)


def resolve_placements(all_blocks: list[Block]) -> None:
    """Topological-sort placement resolution. Modifies blocks in place.

    Raises ValueError on cycles.
    """
    resolved_order, id_to_block = _topological_sort(all_blocks)

    _place_in_order(resolved_order, id_to_block)

    for b in all_blocks:
        if b.children:
            _place_unplaced_children(b)

    _resize_containers(all_blocks)

    # Second pass after container resizing
    _place_in_order(resolved_order, id_to_block)

    for b in all_blocks:
        if b.children:
            _place_unplaced_children(b)


def _resolve_one(b: Block) -> None:
    """Resolve a single block's position from its placement."""
    p = b.placement
    if p is None:
        return

    ref = p.reference

    if p.kind == "below":
        b.y = ref.y + ref.height + BLOCK_GAP
        if p.align == "left":
            b.x = ref.x
        elif p.align == "right":
            b.x = ref.x + ref.width - b.width
        else:  # center
            b.x = ref.x + ref.width / 2 - b.width / 2

    elif p.kind == "above":
        b.y = ref.y - b.height - BLOCK_GAP
        if p.align == "left":
            b.x = ref.x
        elif p.align == "right":
            b.x = ref.x + ref.width - b.width
        else:  # center
            b.x = ref.x + ref.width / 2 - b.width / 2

    elif p.kind == "right_of":
        b.x = ref.x + ref.width + BLOCK_GAP
        b.y = ref.y

    elif p.kind == "left_of":
        b.x = ref.x - b.width - BLOCK_GAP
        b.y = ref.y


def _place_unplaced_children(parent: Block) -> None:
    """Place children that have no placement inside their parent."""
    cx = parent.x + CONTAINER_PADDING
    cy = parent.y + CONTAINER_PADDING + BLOCK_LABEL_SIZE * 2
    for child in parent.children:
        if child.placement is None:
            child.x = cx
            child.y = cy
            cx += child.width + BLOCK_GAP


def _resize_containers(all_blocks: list[Block]) -> None:
    """Resize container blocks to fit their children."""
    # Process deepest containers first
    containers = [b for b in all_blocks if b.children]
    containers.sort(key=lambda b: -_depth(b))

    for c in containers:
        if not c.children:
            continue
        min_x = min(ch.x for ch in c.children)
        min_y = min(ch.y for ch in c.children)
        max_x = max(ch.x + ch.width for ch in c.children)
        max_y = max(ch.y + ch.height for ch in c.children)

        needed_w = (max_x - min_x) + CONTAINER_PADDING * 2
        needed_h = (max_y - min_y) + CONTAINER_PADDING * 2 + BLOCK_LABEL_SIZE * 2
        label_w = (
            _estimate_label_width(c.label, BLOCK_LABEL_SIZE) + CONTAINER_PADDING * 2
        )

        c.width = max(c.width, needed_w, label_w, BLOCK_MIN_WIDTH)
        c.height = max(c.height, needed_h)

        # Adjust position so children fit
        c.x = min(c.x, min_x - CONTAINER_PADDING)
        c.y = min(c.y, min_y - CONTAINER_PADDING - BLOCK_LABEL_SIZE * 2)
