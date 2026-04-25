"""PIDDiagram: mutable container for P&ID symbols and pipe connections."""

from dataclasses import dataclass, field

from schematika.core.geometry import Element, Point
from schematika.core.symbol import Symbol
from schematika.core.transform import translate
from schematika.rendering.svg import render_to_svg


@dataclass
class PIDDiagram:
    """Mutable accumulator: equipment list + flat elements list (for the renderer)."""

    equipment: list[Symbol] = field(default_factory=list)
    elements: list[Element] = field(default_factory=list)

    def get_equipment_by_tag(self, tag: str) -> Symbol | None:
        """First equipment symbol with matching label, else None."""
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
    """Translate and append to both `equipment` and `elements`; *position* wins."""
    if position is not None:
        x, y = position.x, position.y
    placed = translate(symbol, x, y)
    diagram.equipment.append(placed)
    diagram.elements.append(placed)
    return placed


def merge_diagrams(target: PIDDiagram, source: PIDDiagram) -> None:
    """Mutates *target*; *source* is unchanged."""
    target.equipment.extend(source.equipment)
    target.elements.extend(source.elements)


def render_pid(
    diagram: "PIDDiagram | list[PIDDiagram]",
    filename: str,
    width: float = 297.0,
    height: float = 210.0,
) -> None:
    """A3 landscape default; accepts one diagram or a list."""
    all_elements: list[Element] = []

    diagram_list: list[PIDDiagram]
    diagram_list = [diagram] if isinstance(diagram, PIDDiagram) else diagram

    for d in diagram_list:
        all_elements.extend(d.elements)

    render_to_svg(all_elements, filename, width=int(width), height=int(height))
