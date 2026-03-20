"""
Reusable block templates for common subsystem layouts.

Provides :class:`BlockTemplate` for defining reusable arrangements of
blocks and cables that can be instantiated multiple times with different
tag prefixes and positions.
"""

from __future__ import annotations

from dataclasses import dataclass

from schematika.block.constants import BLOCK_DEFAULT_HEIGHT, BLOCK_DEFAULT_WIDTH
from schematika.block.model import BlockPort

__all__ = [
    "BlockTemplate",
    "TemplateCable",
    "TemplateBlock",
]

_OPPOSITE_SIDE: dict[str, str] = {
    "left": "right",
    "right": "left",
    "top": "bottom",
    "bottom": "top",
}


@dataclass(frozen=True)
class TemplateBlock:
    """A block within a template, positioned relative to the template origin.

    Attributes:
        role: Role identifier within the template (e.g. ``"battery_pack"``).
        label: Display label for the block.
        width: Block width in mm.
        height: Block height in mm.
        rel_x: X-position relative to the template origin.
        rel_y: Y-position relative to the template origin.
        fill: CSS fill color for the block interior.
        ports: Custom port definitions, or ``None`` for defaults.
    """

    role: str
    label: str
    width: float = BLOCK_DEFAULT_WIDTH
    height: float = BLOCK_DEFAULT_HEIGHT
    rel_x: float = 0.0
    rel_y: float = 0.0
    fill: str = "none"
    ports: list[BlockPort] | None = None


@dataclass(frozen=True)
class TemplateCable:
    """An internal cable connection within a template.

    Attributes:
        from_role: Source block role within the template.
        to_role: Target block role within the template.
        from_port: Port ID on the source block.
        to_port: Port ID on the target block.
        cable_type: Cable type for style mapping.
        spec: Cable specification string.
        label: Display label for the cable.
    """

    from_role: str
    to_role: str
    from_port: str = "right"
    to_port: str = "left"
    cable_type: str = "signal"
    spec: str = ""
    label: str = ""


@dataclass(frozen=True)
class BlockTemplate:
    """Reusable subsystem layout that can be instantiated with different tag prefixes.

    A template defines a fixed arrangement of blocks and internal cables.
    When instantiated via :meth:`BlockBuilder.add_template`, each block
    gets a name of ``f"{prefix}-{role}"`` and is placed at absolute
    coordinates ``(template_x + rel_x, template_y + rel_y)``.

    Attributes:
        name: Template name for identification.
        blocks: Tuple of template block definitions.
        cables: Tuple of internal cable definitions.
    """

    name: str
    blocks: tuple[TemplateBlock, ...]
    cables: tuple[TemplateCable, ...] = ()


def _mirror_port_side(side: str) -> str:
    """Swap left/right port sides for horizontal mirroring."""
    return _OPPOSITE_SIDE.get(side, side)


def instantiate_template(
    builder: object,
    template: BlockTemplate,
    prefix: str,
    *,
    x: float = 0.0,
    y: float = 0.0,
    mirror_x: bool = False,
) -> object:
    """Instantiate a template into a BlockBuilder.

    Each template block is added at absolute position
    ``(x + rel_x, y + rel_y)``.  When *mirror_x* is ``True``, ``rel_x``
    values are negated and left/right port sides are swapped on cables.

    This function is called by :meth:`BlockBuilder.add_template` — it is
    also available for direct use when extending the builder.

    Args:
        builder: A :class:`BlockBuilder` instance (typed as ``object`` to
            avoid circular imports).
        template: The template to instantiate.
        prefix: Name prefix for template blocks (e.g. ``"ups1"``).
        x: X-coordinate of the template origin.
        y: Y-coordinate of the template origin.
        mirror_x: If ``True``, flip layout horizontally.

    Returns:
        The builder for method chaining.
    """
    for block in template.blocks:
        rel_x = -block.rel_x if mirror_x else block.rel_x
        name = f"{prefix}-{block.role}"
        builder.add_block(  # type: ignore[attr-defined]
            name,
            block.label,
            width=block.width,
            height=block.height,
            x=x + rel_x,
            y=y + block.rel_y,
            fill=block.fill,
            ports=block.ports,
        )

    for cable in template.cables:
        from_name = f"{prefix}-{cable.from_role}"
        to_name = f"{prefix}-{cable.to_role}"
        from_port = _mirror_port_side(cable.from_port) if mirror_x else cable.from_port
        to_port = _mirror_port_side(cable.to_port) if mirror_x else cable.to_port
        builder.cable(  # type: ignore[attr-defined]
            from_name,
            to_name,
            cable_type=cable.cable_type,
            from_port=from_port,
            to_port=to_port,
            spec=cable.spec,
            label=cable.label,
        )

    return builder
