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
    """Mutable accumulator of placed symbols and bare elements for one page.

    Intentionally not frozen — the builder appends to it in sequence.
    Pass to :func:`render_system` to produce SVG output.

    Examples:
        >>> from schematika.electrical import Circuit
        >>> c = Circuit()
        >>> c.symbols, c.elements
        ([], [])
    """

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
    viewbox: str | None = None,
) -> None:
    """Render one or more circuits to an SVG file.

    All circuit elements are flattened into a single SVG viewport. When
    ``width`` or ``height`` is ``"auto"`` the bounding box is computed from
    the element coordinates.

    Args:
        circuits: A single :class:`Circuit` or a list of circuits to render
            together.
        filename: Output SVG file path, e.g. ``"output/panel.svg"``.
        width: SVG viewport width in mm, or ``"auto"`` for bounding-box fit.
        height: SVG viewport height in mm, or ``"auto"`` for bounding-box fit.
        viewbox: Optional explicit SVG viewBox string (e.g. ``"0 0 250 297"``).
            When provided overrides the auto-computed viewBox; width/height
            still control the SVG element dimensions.

    Returns:
        None (writes the file as a side-effect).

    Examples:
        >>> import tempfile, os
        >>> from schematika.electrical import Circuit, render_system
        >>> c = Circuit()
        >>> tmp = tempfile.NamedTemporaryFile(suffix=".svg", delete=False)
        >>> path = tmp.name
        >>> tmp.close()
        >>> render_system(c, path)
        >>> os.path.exists(path)
        True
        >>> os.unlink(path)
    """
    all_elements = []

    # Normalize to list
    circuit_list: list[Circuit]
    circuit_list = [circuits] if isinstance(circuits, Circuit) else circuits

    for c in circuit_list:
        all_elements.extend(c.elements)

    render_to_svg(all_elements, filename, width=width, height=height, viewbox=viewbox)


def merge_circuits(target: Circuit, source: Circuit) -> Circuit:
    """Combine two circuits into a new circuit without mutating either input.

    Args:
        target: First circuit; its symbols and elements appear first.
        source: Second circuit; appended after target.

    Returns:
        New :class:`Circuit` with combined symbols and elements.

    Examples:
        >>> from schematika.electrical import Circuit, merge_circuits
        >>> a, b = Circuit(), Circuit()
        >>> merged = merge_circuits(a, b)
        >>> merged is not a and merged is not b
        True
    """
    return Circuit(
        symbols=target.symbols + source.symbols,
        elements=target.elements + source.elements,
    )
