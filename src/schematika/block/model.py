"""
Data model for block diagrams.

Provides Block, Placement, Cable, BlockStyle, MirroredBlock, and
predefined cable styles (CableStyle, AC_POWER, DC_CONTROL, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from schematika.block.constants import (
    BLOCK_GAP,
    CABLE_COLOR_AC_POWER,
    CABLE_COLOR_DC_CONTROL,
    CABLE_COLOR_ETHERNET,
    CABLE_COLOR_SIGNAL,
    CABLE_ETHERNET_DASH,
    CABLE_WEIGHT_CONTROL,
    CABLE_WEIGHT_ETHERNET,
    CABLE_WEIGHT_POWER,
    CABLE_WEIGHT_SIGNAL,
)

__all__ = [
    "BlockStyle",
    "SOLID",
    "DASHED",
    "Placement",
    "Cable",
    "Block",
    "MirroredBlock",
    "CableStyle",
    "AC_POWER",
    "DC_CONTROL",
    "SIGNAL_CABLE",
    "ETHERNET",
    "CABLE_TYPE_STYLES",
]


# ---------------------------------------------------------------------------
# Cable styles (kept from previous model)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CableStyle:
    """Visual style for a cable connection line."""

    stroke_width: float
    color: str = "black"
    dash_pattern: str | None = None


AC_POWER = CableStyle(CABLE_WEIGHT_POWER, CABLE_COLOR_AC_POWER)
DC_CONTROL = CableStyle(CABLE_WEIGHT_CONTROL, CABLE_COLOR_DC_CONTROL)
SIGNAL_CABLE = CableStyle(CABLE_WEIGHT_SIGNAL, CABLE_COLOR_SIGNAL)
ETHERNET = CableStyle(CABLE_WEIGHT_ETHERNET, CABLE_COLOR_ETHERNET, CABLE_ETHERNET_DASH)

CABLE_TYPE_STYLES: dict[str, CableStyle] = {
    "power_ac": AC_POWER,
    "power_dc": DC_CONTROL,
    "signal": SIGNAL_CABLE,
    "ethernet": ETHERNET,
    "control": DC_CONTROL,
}


# ---------------------------------------------------------------------------
# Block styles
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BlockStyle:
    """Visual style for a block rectangle."""

    stroke_width: float = 0.5
    dash_pattern: str | None = None
    fill: str = "none"
    color: str = "black"


SOLID = BlockStyle()
DASHED = BlockStyle(dash_pattern="4,2")


# ---------------------------------------------------------------------------
# Placement
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Placement:
    """Describes how a block is placed relative to another block or parent.

    Kinds:
        "below", "above", "right_of", "left_of" -- relative to reference block
        "corner" -- placed at a corner of parent (reference is None)
        "next_to" -- placed to the right of reference with a gap
    """

    kind: str  # "below", "above", "right_of", "left_of", "corner", "next_to"
    reference: Block | None = None
    align: str = "center"  # "center", "left", "right"
    corner: str = ""  # "top-left", "top-right", "bottom-left", "bottom-right", "center"
    inside: bool = True
    padding: float = 0.0
    gap: float = 0.0  # for next_to


# ---------------------------------------------------------------------------
# Cable
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Cable:
    """A cable connection between two blocks."""

    from_block: Block
    to_block: Block
    label: str
    style: CableStyle
    from_side: str | None = None  # "left", "right", "top", "bottom" or None=auto
    to_side: str | None = None
    label_pos: str = "middle"  # "start", "middle", "end"


# ---------------------------------------------------------------------------
# Block
# ---------------------------------------------------------------------------


@dataclass
class Block:
    """Mutable block -- placement methods mutate self.placement."""

    label: str
    name: str | None = None
    parent: Block | None = field(default=None, repr=False)
    children: list[Block] = field(default_factory=list)
    contains: list[str] = field(default_factory=list)
    style: BlockStyle = field(default_factory=lambda: SOLID)
    wide: bool = False
    note: str = ""
    rotation: float = 0.0
    placement: Placement | None = None
    # Resolved by layout engine:
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    # Set True when the user specifies width/height (skip auto-sizing):
    _user_sized: bool = field(default=False, repr=False)

    def __post_init__(self) -> None:
        if self.width > 0 and self.height > 0:
            self._user_sized = True

    def block(self, label: str, **kwargs: object) -> Block:
        """Create a child block inside this block."""
        child = Block(label=label, parent=self, **kwargs)  # type: ignore[arg-type]
        self.children.append(child)
        return child

    def _check_no_placement(self, kind: str) -> None:
        if self.placement is not None:
            ref_label = (
                self.placement.reference.label if self.placement.reference else "parent"
            )
            raise ValueError(
                f"Block '{self.label}' already has placement "
                f"({self.placement.kind} {ref_label}). "
                f"Cannot set {kind}."
            )

    def _set_placement(self, kind: str, ref: Block, align: str = "center") -> Block:
        self._check_no_placement(kind)
        self.placement = Placement(kind=kind, reference=ref, align=align)
        return self

    def below(self, ref: Block, align: str = "center", gap: float = 0) -> Block:
        """Place below reference. gap=0 uses default BLOCK_GAP."""
        self._check_no_placement("below")
        self.placement = Placement(kind="below", reference=ref, align=align, gap=gap)
        return self

    def above(self, ref: Block, align: str = "center", gap: float = 0) -> Block:
        """Place above reference. gap=0 uses default BLOCK_GAP."""
        self._check_no_placement("above")
        self.placement = Placement(kind="above", reference=ref, align=align, gap=gap)
        return self

    def right_of(self, ref: Block, gap: float = 0) -> Block:
        """Place to the right. gap=0 uses default BLOCK_GAP."""
        self._check_no_placement("right_of")
        self.placement = Placement(kind="right_of", reference=ref, gap=gap)
        return self

    def left_of(self, ref: Block, gap: float = 0) -> Block:
        """Place to the left. gap=0 uses default BLOCK_GAP."""
        self._check_no_placement("left_of")
        self.placement = Placement(kind="left_of", reference=ref, gap=gap)
        return self

    def place(
        self,
        corner: str = "center",
        inside: bool = True,
        padding: float = 0.0,
        on: Block | None = None,
    ) -> Block:
        """Place this block at a corner of its parent or another block.

        Args:
            corner: "top-left", "top-right", "bottom-left", "bottom-right", or "center"
            inside: True = inside the reference, False = outside
            padding: Gap from corner (default 0 for exact edge alignment)
            on: Reference block. If None, uses the parent block.
        """
        self._check_no_placement("corner")
        self.placement = Placement(
            kind="corner",
            reference=on,
            corner=corner,
            inside=inside,
            padding=padding,
        )
        return self

    def next_to(self, sibling: Block, gap: float = BLOCK_GAP) -> Block:
        """Place this block to the right of a sibling (same row).

        Args:
            sibling: The block to place next to
            gap: Gap between blocks (default BLOCK_GAP from constants)
        """
        self._check_no_placement("next_to")
        self.placement = Placement(kind="next_to", reference=sibling, gap=gap)
        return self

    def under(self, sibling: Block, gap: float = BLOCK_GAP) -> Block:
        """Place this block below a sibling (same column).

        Like next_to but vertical. Left edges align.

        Args:
            sibling: The block to place under
            gap: Gap between blocks (default BLOCK_GAP from constants)
        """
        self._check_no_placement("under")
        self.placement = Placement(kind="under", reference=sibling, gap=gap)
        return self


# ---------------------------------------------------------------------------
# MirroredBlock
# ---------------------------------------------------------------------------


class MirroredBlock:
    """Wrapper providing name-based access to mirrored blocks."""

    def __init__(self, root: Block, named: dict[str, Block]) -> None:
        self._root = root
        self._named = named

    @property
    def root(self) -> Block:
        return self._root

    def __getitem__(self, name: str) -> Block:
        if name not in self._named:
            available = list(self._named.keys())
            raise KeyError(f"No mirrored block named '{name}'. Available: {available}")
        return self._named[name]
