"""Circuit accumulator + SVG render helpers."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from schematika.electrical.model.core import Element, Symbol
from schematika.electrical.utils.renderer import (
    render_to_svg,
)
from schematika.electrical.utils.transform import translate

if TYPE_CHECKING:
    from schematika.core.geometry import Point


@dataclass
class Circuit:
    """Mutable accumulator (intentionally not frozen); consumed by the renderer."""

    symbols: list[Symbol] = field(default_factory=list)
    elements: list[Element] = field(default_factory=list)

    def get_symbol_by_tag(self, tag: str) -> Symbol | None:
        """First symbol with matching label, else None."""
        for sym in self.symbols:
            if sym.label == tag:
                return sym
        return None


def add_symbol(
    circuit: Circuit,
    symbol: Symbol,
    x: float = 0.0,
    y: float = 0.0,
    *,
    position: "Point | None" = None,
) -> Symbol:
    """Translates and appends to both symbols and elements; *position* wins over x/y."""
    if position is not None:
        x, y = position.x, position.y
    placed_symbol = translate(symbol, x, y)
    circuit.symbols.append(placed_symbol)
    circuit.elements.append(placed_symbol)
    return placed_symbol


def render_system(
    circuits: Circuit | list[Circuit],
    filename: str,
    width: str | int = "auto",
    height: str | int = "auto",
) -> None:
    """Accepts one Circuit or a list."""
    all_elements = []

    # Normalize to list
    circuit_list: list[Circuit]
    circuit_list = [circuits] if isinstance(circuits, Circuit) else circuits

    for c in circuit_list:
        all_elements.extend(c.elements)

    render_to_svg(all_elements, filename, width=width, height=height)


def merge_circuits(target: Circuit, source: Circuit) -> Circuit:
    """Returns a NEW circuit; both inputs are unchanged."""
    return Circuit(
        symbols=target.symbols + source.symbols,
        elements=target.elements + source.elements,
    )
