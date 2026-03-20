"""
BlockDiagram container for block symbols and cable connections.

Analogous to ``PIDDiagram`` in the P&ID domain: a mutable accumulator
that collects block symbols and graphical elements during diagram
construction.  Once building is finished the elements list is consumed
by the renderer.
"""

from dataclasses import dataclass, field

from schematika.core.geometry import Element
from schematika.core.renderer import render_to_svg
from schematika.core.symbol import Symbol
from schematika.core.transform import translate


@dataclass
class BlockDiagram:
    """Mutable container for block symbols and connections.

    Attributes:
        blocks: Ordered list of placed block symbols.
        elements: All graphical elements (block symbols + cable lines).
    """

    blocks: list[Symbol] = field(default_factory=list)
    elements: list[Element] = field(default_factory=list)

    def get_block_by_tag(self, tag: str) -> Symbol | None:
        """Look up a placed block symbol by its label/tag.

        Args:
            tag: The symbol label to search for.

        Returns:
            The matching Symbol, or None if not found.
        """
        for sym in self.blocks:
            if sym.label == tag:
                return sym
        return None


def add_block(diagram: BlockDiagram, symbol: Symbol, x: float, y: float) -> Symbol:
    """Place a block at (x, y) and add it to the diagram.

    Translates the symbol to the given coordinates, appends it to both
    ``diagram.blocks`` and ``diagram.elements``, and returns the
    placed (translated) symbol.

    Args:
        diagram: The diagram to add to.
        symbol: The symbol template (usually centred at origin).
        x: X-coordinate of the placement origin.
        y: Y-coordinate of the placement origin.

    Returns:
        The translated symbol.
    """
    placed = translate(symbol, x, y)
    diagram.blocks.append(placed)
    diagram.elements.append(placed)
    return placed


def merge_block_diagrams(target: BlockDiagram, source: BlockDiagram) -> None:
    """Merge *source* diagram into *target* (mutates target).

    All blocks and elements from *source* are appended to *target*.
    The source diagram is not modified.

    Args:
        target: The diagram to merge into (mutated).
        source: The diagram to merge from (unchanged).
    """
    target.blocks.extend(source.blocks)
    target.elements.extend(source.elements)


def render_block_diagram(
    diagram: "BlockDiagram | list[BlockDiagram]",
    filename: str,
    width: float = 420.0,
    height: float = 297.0,
) -> None:
    """Render one or more block diagrams to an SVG file.

    Args:
        diagram: A single ``BlockDiagram`` or a list of diagrams.
        filename: Destination SVG file path.
        width: Document width in mm (A3 landscape default: 420).
        height: Document height in mm (A3 landscape default: 297).
    """
    all_elements: list[Element] = []

    diagram_list: list[BlockDiagram]
    if isinstance(diagram, BlockDiagram):
        diagram_list = [diagram]
    else:
        diagram_list = diagram

    for d in diagram_list:
        all_elements.extend(d.elements)

    render_to_svg(all_elements, filename, width=int(width), height=int(height))
