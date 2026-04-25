"""BlockDiagram -- the top-level API for containment-based block diagrams.

Usage::

    d = BlockDiagram()
    msb = d.block("Main switchboard (MSB)")
    esb = d.block("Emergency switchboard (ESB)")
    esb.below(msb)
    d.cable(msb, esb, "4x95 (W0001)", AC_POWER)
    d.render("output.svg")
"""

from __future__ import annotations

from schematika.block.constants import CONTAINER_PADDING
from schematika.block.layout import resolve_placements, resolve_sizes
from schematika.block.model import (
    Block,
    Cable,
    CableStyle,
    MirroredBlock,
    Placement,
)
from schematika.block.rendering import (
    render_blocks,
    render_cables,
    render_legend,
    render_notes,
)
from schematika.rendering.svg import render_to_svg
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from schematika.core.geometry import Element

_FLIP_KIND = {"left_of": "right_of", "right_of": "left_of"}
_FLIP_ALIGN = {"left": "right", "right": "left"}
_FLIP_CORNER = {
    "top-left": "top-right",
    "top-right": "top-left",
    "bottom-left": "bottom-right",
    "bottom-right": "bottom-left",
    "center": "center",
}


class BlockDiagram:
    """Mutable diagram builder using containment-based layout."""

    def __init__(self) -> None:
        """Build an empty ``BlockDiagram`` with no blocks or cables."""
        self._root_blocks: list[Block] = []
        self._cables: list[Cable] = []
        self._spread_groups: list[tuple[list[Block], Block, list[float] | None]] = []
        self._show_legend: bool = False
        self._notes: list[str] | None = None
        self._abbreviations: dict[str, str] | None = None

    def block(self, label: str, **kwargs: Any) -> Block:  # noqa: ANN401
        """Create a root-level block."""
        b = Block(label=label, **kwargs)
        self._root_blocks.append(b)
        return b

    def cable(
        self,
        from_block: Block,
        to_block: Block,
        label: str,
        style: CableStyle,
        from_side: str | None = None,
        to_side: str | None = None,
        label_pos: str = "middle",
    ) -> None:
        """Declare a cable connection between two blocks."""
        self._cables.append(
            Cable(
                from_block=from_block,
                to_block=to_block,
                label=label,
                style=style,
                from_side=from_side,
                to_side=to_side,
                label_pos=label_pos,
            )
        )

    def spread(
        self,
        *blocks: Block | MirroredBlock,
        below: Block,
        weights: list[float] | None = None,
    ) -> None:
        """Distribute blocks across the page width, below a reference block.

        Divides the available page width into columns and centers each
        block in its column.  All blocks are placed at the same Y
        (below the reference block + gap).

        Args:
            *blocks: The blocks to distribute (left to right).
                     MirroredBlock instances are unwrapped to their root.
            below: The reference block -- spread blocks appear below this.
            weights: Optional column width weights (e.g. [3, 2, 3]).
                     When set, columns are sized proportionally.
        """
        resolved = [b.root if isinstance(b, MirroredBlock) else b for b in blocks]
        self._spread_groups.append((resolved, below, weights))

    def mirror(self, block: Block, name: str) -> MirroredBlock:
        """Deep-copy a block and all transitively referenced blocks, flipping L/R."""
        # Phase 1: collect the containment tree of `block`
        original_set: set[int] = set()
        _collect_tree_ids(block, original_set)

        # Phase 2: find external blocks whose placement transitively references
        # `block` or any of its descendants
        all_diagram_blocks = self._all_blocks()
        external_ids: set[int] = set()
        _collect_transitive_externals(original_set, all_diagram_blocks, external_ids)

        # Phase 3: deep-copy all blocks in original_set | external_ids
        old_to_new: dict[int, Block] = {}

        # Deep copy the root block (and its tree)
        new_root = _deep_copy_block(block, old_to_new)
        new_root.name = name

        # Deep copy external blocks
        for b in all_diagram_blocks:
            if id(b) in external_ids and id(b) not in old_to_new:
                _deep_copy_block(b, old_to_new)

        # Phase 4: fix placements in all copies -- flip left/right, align
        for new_block in old_to_new.values():
            if new_block.placement is not None:
                new_block.placement = _flip_placement(new_block.placement, old_to_new)

        # Phase 5: register copied root blocks in diagram
        self._root_blocks.append(new_root)
        for new_block in old_to_new.values():
            if new_block.parent is None and new_block is not new_root:
                self._root_blocks.append(new_block)

        # Phase 6: build name lookup
        named: dict[str, Block] = {}
        for new_block in old_to_new.values():
            if new_block.name is not None:
                named[new_block.name] = new_block

        return MirroredBlock(new_root, named)

    def legend(self) -> None:
        """Enable auto-generated legend from cable styles used."""
        self._show_legend = True

    def notes(self, lines: list[str]) -> None:
        """Set note lines to display on the diagram."""
        self._notes = lines

    def abbreviations(self, items: dict[str, str]) -> None:
        """Set abbreviation definitions to display on the diagram."""
        self._abbreviations = items

    def render(self, filename: str, width: float = 420, height: float = 297) -> None:
        """Resolve layout and render to SVG.

        The SVG auto-sizes to fit all content so nothing is clipped.
        """
        all_blocks = self._all_blocks()

        # Layout
        resolve_sizes(all_blocks)
        resolve_placements(all_blocks, self._spread_groups, width)

        # Render
        elements: list[Element] = []
        elements.extend(render_blocks(all_blocks))
        elements.extend(render_cables(self._cables, all_blocks))

        if self._show_legend:
            elements.extend(
                render_legend(
                    [c.style for c in self._cables],
                    origin_x=CONTAINER_PADDING,
                    origin_y=height - CONTAINER_PADDING * 4,
                )
            )

        if self._notes or self._abbreviations:
            elements.extend(
                render_notes(
                    self._notes,
                    self._abbreviations,
                    origin_x=width * 0.75,
                    origin_y=CONTAINER_PADDING,
                )
            )

        # Fixed page size — user must ensure content fits
        render_to_svg(elements, filename, width=int(width), height=int(height))

    def _all_blocks(self) -> list[Block]:
        """Collect all blocks in the diagram (root + descendants)."""
        result: list[Block] = []
        for b in self._root_blocks:
            _collect_tree(b, result)
        return result

    @property
    def blocks(self) -> list[Block]:
        """All blocks in the diagram."""
        return self._all_blocks()

    @property
    def cables(self) -> list[Cable]:
        """All cables in the diagram."""
        return list(self._cables)

    @property
    def elements(self) -> list[Element]:
        """Rendered elements (for validation). Triggers layout + render."""
        all_blocks = self._all_blocks()
        resolve_sizes(all_blocks)
        resolve_placements(all_blocks)
        elems: list[Element] = []
        elems.extend(render_blocks(all_blocks))
        elems.extend(render_cables(self._cables, all_blocks))
        return elems


def _collect_tree(block: Block, result: list[Block]) -> None:
    result.append(block)
    for child in block.children:
        _collect_tree(child, result)


def _collect_tree_ids(block: Block, ids: set[int]) -> None:
    ids.add(id(block))
    for child in block.children:
        _collect_tree_ids(child, ids)


def _collect_transitive_externals(
    tree_ids: set[int],
    all_blocks: list[Block],
    external_ids: set[int],
) -> None:
    """Find blocks outside tree_ids whose placement transitively references the tree."""
    changed = True
    target_ids = set(tree_ids)
    while changed:
        changed = False
        for b in all_blocks:
            if id(b) in target_ids or id(b) in external_ids:
                continue
            if (
                b.placement is not None
                and b.placement.reference is not None
                and id(b.placement.reference) in target_ids
            ):
                external_ids.add(id(b))
                target_ids.add(id(b))
                changed = True


def _deep_copy_block(block: Block, old_to_new: dict[int, Block]) -> Block:
    """Deep copy a block and its children, tracking old->new mapping."""
    if id(block) in old_to_new:
        return old_to_new[id(block)]

    new = Block(
        label=block.label,
        name=block.name,
        parent=None,  # fixed up below
        children=[],
        contains=list(block.contains),
        style=block.style,
        wide=block.wide,
        note=block.note,
        rotation=block.rotation,
        placement=block.placement,  # fixed up by caller
        width=block.width,
        height=block.height,
    )
    old_to_new[id(block)] = new

    for child in block.children:
        new_child = _deep_copy_block(child, old_to_new)
        new_child.parent = new
        new.children.append(new_child)

    return new


def _remap_reference(p: Placement, old_to_new: dict[int, Block]) -> Block | None:
    """Find the mirrored reference block, or keep original."""
    if p.reference is None:
        return None
    ref_old_id = id(p.reference)
    if ref_old_id in old_to_new:
        return old_to_new[ref_old_id]
    return p.reference


def _flip_placement(p: Placement, old_to_new: dict[int, Block]) -> Placement:
    """Create a mirrored copy of a placement, flipping L/R."""
    if p.kind == "corner":
        return Placement(
            kind="corner",
            corner=_FLIP_CORNER.get(p.corner, p.corner),
            inside=p.inside,
            padding=p.padding,
            reference=_remap_reference(p, old_to_new),
        )
    new_ref = _remap_reference(p, old_to_new)
    if p.kind == "next_to":
        return Placement(kind="next_to", reference=new_ref, gap=p.gap)
    return Placement(
        kind=_FLIP_KIND.get(p.kind, p.kind),
        reference=new_ref,
        align=_FLIP_ALIGN.get(p.align, p.align),
    )
