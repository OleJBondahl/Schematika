"""PIDDiagram container for P&ID symbols and pipe connections.

Analogous to ``Circuit`` in the electrical domain: a mutable accumulator
that collects equipment symbols and graphical elements during diagram
construction. Once building is finished the elements list is consumed by
the renderer.
"""

from dataclasses import dataclass, field

from schematika.core.geometry import Element, Point
from schematika.core.symbol import Symbol
from schematika.core.transform import translate
from schematika.rendering.svg import render_to_svg


@dataclass
class PIDDiagram:
    """Mutable container for P&ID symbols and connections.

    Attributes:
        equipment: Ordered list of placed equipment symbols.
        elements: All graphical elements (equipment symbols + pipe lines).
    """

    equipment: list[Symbol] = field(default_factory=list)
    elements: list[Element] = field(default_factory=list)

    def get_equipment_by_tag(self, tag: str) -> Symbol | None:
        """Look up a placed equipment symbol by its label/tag.

        Args:
            tag: The symbol label to search for (e.g. "P-101", "TIC-100").

        Returns:
            The matching Symbol, or None if not found.
        """
        for sym in self.equipment:
            if sym.label == tag:
                return sym
        return None


def add_equipment(
    diagram: PIDDiagram,
    symbol: Symbol,
    x: float = 0.0,
    y: float = 0.0,
    *,
    position: Point | None = None,
) -> Symbol:
    """Place equipment at (x, y) and add it to the diagram.

    Translates the symbol to the given coordinates, appends it to both
    ``diagram.equipment`` and ``diagram.elements``, and returns the
    placed (translated) symbol.

    Args:
        diagram: The diagram to add to.
        symbol: The symbol template (usually centred at origin).
        x: X-coordinate of the placement origin (ignored when ``position`` set).
        y: Y-coordinate of the placement origin (ignored when ``position`` set).
        position: Point alternative to ``x``/``y``; wins when provided.

    Returns:
        The translated symbol.
    """
    if position is not None:
        x, y = position.x, position.y
    placed = translate(symbol, x, y)
    diagram.equipment.append(placed)
    diagram.elements.append(placed)
    return placed


def merge_diagrams(target: PIDDiagram, source: PIDDiagram) -> None:
    """Merge *source* diagram into *target* (mutates target).

    All equipment and elements from *source* are appended to *target*.
    The source diagram is not modified.

    Args:
        target: The diagram to merge into (mutated).
        source: The diagram to merge from (unchanged).
    """
    target.equipment.extend(source.equipment)
    target.elements.extend(source.elements)


def render_pid(
    diagram: "PIDDiagram | list[PIDDiagram]",
    filename: str,
    width: float = 297.0,
    height: float = 210.0,
) -> None:
    """Render one or more P&ID diagrams to an SVG file.

    Args:
        diagram: A single ``PIDDiagram`` or a list of diagrams.
        filename: Destination SVG file path.
        width: Document width in mm (A3 landscape default: 297).
        height: Document height in mm (A3 landscape default: 210).
    """
    all_elements: list[Element] = []

    diagram_list: list[PIDDiagram]
    diagram_list = [diagram] if isinstance(diagram, PIDDiagram) else diagram

    for d in diagram_list:
        all_elements.extend(d.elements)

    render_to_svg(all_elements, filename, width=int(width), height=int(height))
