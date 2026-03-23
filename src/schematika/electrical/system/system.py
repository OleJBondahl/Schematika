from dataclasses import dataclass, field

from schematika.electrical.layout.layout import draw_wire
from schematika.electrical.model.core import Element, Symbol
from schematika.electrical.utils.renderer import (
    render_to_svg,
)
from schematika.electrical.utils.transform import translate


@dataclass
class Circuit:
    """
    A mutable container for electrical symbols and their connections.

    Unlike the frozen dataclasses in ``model/core.py``, Circuit is intentionally
    mutable — it serves as an accumulator/builder that collects symbols and
    connection wires during circuit construction. Once building is finished the
    elements list is consumed by the renderer and never mutated again.

    Attributes:
        symbols (list[Symbol]): Ordered list of main components.
        elements (list[Element]): All graphical elements (symbols + wires).
    """

    symbols: list[Symbol] = field(default_factory=list)
    elements: list[Element] = field(default_factory=list)

    def get_symbol_by_tag(self, tag: str) -> Symbol | None:
        """Look up a placed symbol by its label/tag.

        Args:
            tag: The symbol label to search for (e.g. "Q1", "F1").

        Returns:
            The matching Symbol, or None if not found.
        """
        for sym in self.symbols:
            if sym.label == tag:
                return sym
        return None


def add_symbol(circuit: Circuit, symbol: Symbol, x: float, y: float) -> Symbol:
    """
    Add a symbol to the circuit at a specified position.

    This function handles the translation of the symbol to the given coordinates
    and adds it to the circuit's internal storage.

    Args:
        circuit (Circuit): The circuit to add to.
        symbol (Symbol): The symbol instance to add
            (usually created from symbols library).
        x (float): The x-coordinate.
        y (float): The y-coordinate.

    Returns:
        Symbol: The placed (translated) symbol.
    """
    placed_symbol = translate(symbol, x, y)
    circuit.symbols.append(placed_symbol)
    circuit.elements.append(placed_symbol)
    return placed_symbol


# Deprecated: CircuitBuilder now uses PlannedConnection instead.
def auto_connect_circuit(circuit: Circuit) -> None:
    """
    Automatically connect all adjacent connectable symbols in the circuit.

    Iterates through the symbols in the order they were added and connects
    each symbol to the next one using draw_wire logic.

    Args:
        circuit (Circuit): The circuit to process.
    """
    connectable_symbols = circuit.symbols

    for i in range(len(connectable_symbols) - 1):
        s1 = connectable_symbols[i]
        s2 = connectable_symbols[i + 1]
        lines = draw_wire(s1, s2)
        circuit.elements.extend(lines)


def render_system(
    circuits: Circuit | list[Circuit],
    filename: str,
    width: str | int = "auto",
    height: str | int = "auto",
) -> None:
    """
    Render one or more circuits to an SVG file.

    Args:
        circuits (Circuit | list[Circuit]): A single Circuit or list of Circuits.
        filename (str): The output file path.
        width (str|int): Document width.
        height (str|int): Document height.
    """
    all_elements = []

    # Normalize to list
    circuit_list: list[Circuit]
    if isinstance(circuits, Circuit):
        circuit_list = [circuits]
    else:
        circuit_list = circuits

    for c in circuit_list:
        all_elements.extend(c.elements)

    render_to_svg(all_elements, filename, width=width, height=height)


def merge_circuits(target: Circuit, source: Circuit) -> Circuit:
    """
    Merge source circuit into target circuit.

    Returns a NEW Circuit containing all symbols and elements from both.
    The original circuits are NOT modified.

    Args:
        target: The circuit to merge into
        source: The circuit to merge from

    Returns:
        Circuit: A new circuit containing merged contents.
    """
    return Circuit(
        symbols=target.symbols + source.symbols,
        elements=target.elements + source.elements,
    )
