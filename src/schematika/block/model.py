"""
Data model for block diagrams.

Provides Block, Placement, Cable, BlockStyle, MirroredBlock, and
predefined cable styles (CableStyle, AC_POWER, DC_CONTROL, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from schematika.block.constants import (
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
    """Describes how a block is placed relative to another block."""

    kind: str  # "below", "above", "right_of", "left_of"
    reference: Block
    align: str = "center"  # "center", "left", "right"


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
    placement: Placement | None = None
    # Resolved by layout engine:
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0

    def block(self, label: str, **kwargs: object) -> Block:
        """Create a child block inside this block."""
        child = Block(label=label, parent=self, **kwargs)  # type: ignore[arg-type]
        self.children.append(child)
        return child

    def _set_placement(self, kind: str, ref: Block, align: str = "center") -> Block:
        if self.placement is not None:
            raise ValueError(
                f"Block '{self.label}' already has placement "
                f"({self.placement.kind} {self.placement.reference.label}). "
                f"Cannot set {kind}."
            )
        self.placement = Placement(kind=kind, reference=ref, align=align)
        return self

    def below(self, ref: Block, align: str = "center") -> Block:
        return self._set_placement("below", ref, align)

    def above(self, ref: Block, align: str = "center") -> Block:
        return self._set_placement("above", ref, align)

    def right_of(self, ref: Block) -> Block:
        return self._set_placement("right_of", ref)

    def left_of(self, ref: Block) -> Block:
        return self._set_placement("left_of", ref)


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
