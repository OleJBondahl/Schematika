"""Wire-label placement on connection lines."""

from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from schematika.electrical.system.system import Circuit

from schematika.electrical.model.constants import (
    TEXT_FONT_FAMILY_AUX,
    TEXT_SIZE_PIN,
    WIRE_LABEL_OFFSET_X,
)
from schematika.electrical.model.core import Element, Point
from schematika.electrical.model.primitives import Line, Text


def calculate_wire_label_position(
    start: Point,
    end: Point,
    offset_x: float = WIRE_LABEL_OFFSET_X,
) -> Point:
    """Wire midpoint shifted by `offset_x` (mm) from the centerline."""
    mid_x = (start.x + end.x) / 2.0
    mid_y = (start.y + end.y) / 2.0

    return Point(mid_x + offset_x, mid_y)


def create_wire_label_text(
    text_content: str, position: Point, font_size: float = TEXT_SIZE_PIN
) -> Text:
    """Rotated 90deg (downward) and centered on the wire."""
    from schematika.electrical.model.core import Style

    return Text(
        content=text_content,
        position=position,
        anchor="middle",  # Center horizontally (relative to rotated text)
        # Center vertically (relative to rotated text)
        dominant_baseline="middle",
        font_size=font_size,
        rotation=90.0,  # Text runs downwards
        style=Style(stroke="none", fill="black", font_family=TEXT_FONT_FAMILY_AUX),
    )


def format_wire_specification(color: str = "", size: str = "") -> str:
    """Joins non-empty parts with a space (e.g. `"RD 2.5mm²"`)."""
    parts = [p for p in [color, size] if p]
    return " ".join(parts)


def create_labeled_wire(
    start: Point,
    end: Point,
    wire_color: str = "",
    wire_size: str = "",
    label_offset_x: float = -2.5,
) -> list[Element]:
    """Returns the wire line plus an optional label when color/size is supplied."""
    from schematika.electrical.model.parts import standard_style

    elements: list[Element] = []

    # Create the wire line
    wire_line = Line(start, end, style=standard_style())
    elements.append(wire_line)

    # Add label if specifications are provided
    label_text = format_wire_specification(wire_color, wire_size)
    if label_text:
        label_pos = calculate_wire_label_position(start, end, label_offset_x)
        label = create_wire_label_text(label_text, label_pos)
        elements.append(label)

    return elements


def create_labeled_connections(
    connection_specs: list[tuple[Point, Point, str, str]],
) -> list[Element]:
    """Batch wrapper around `create_labeled_wire`; flattens the resulting elements."""
    from functools import reduce

    all_elements = [
        create_labeled_wire(start, end, color, size)
        for start, end, color, size in connection_specs
    ]

    # Flatten the list of lists into a single list
    return reduce(lambda acc, x: acc + x, all_elements, [])


def find_vertical_wires(elements: list[Element], tolerance: float = 0.1) -> list[Line]:
    """X-coords within *tolerance* mm and Y-coords differing more than *tolerance*."""
    # Vertical: start.x ≈ end.x and start.y differs from end.y
    return [
        element
        for element in elements
        if isinstance(element, Line)
        and abs(element.start.x - element.end.x) < tolerance
        and abs(element.start.y - element.end.y) > tolerance
    ]


def add_wire_labels_to_circuit(
    circuit: "Circuit",
    wire_labels: Sequence[str] | None = None,
    offset_x: float = WIRE_LABEL_OFFSET_X,
) -> "Circuit":
    """Annotate vertical wires in a circuit with colour/cross-section labels.

    Scans the circuit for vertical ``Line`` elements and attaches rotated
    text labels at the wire midpoints. Returns a new circuit; the input is
    not mutated. Raises :class:`~schematika.electrical.WireLabelMismatchError`
    if ``len(wire_labels) != len(vertical wires)``.

    Args:
        circuit: Source circuit whose vertical wires are to be labelled.
        wire_labels: Ordered list of label strings, one per vertical wire.
            ``None`` returns the circuit unchanged.
        offset_x: Horizontal shift in mm from the wire centreline.

    Returns:
        New :class:`~schematika.electrical.Circuit` with label text elements
        appended; original circuit is unchanged.

    Examples:
        >>> from schematika.electrical import Circuit, add_wire_labels_to_circuit
        >>> c = Circuit()
        >>> result = add_wire_labels_to_circuit(c, wire_labels=None)
        >>> result is c
        True
    """
    from schematika.electrical.system.system import Circuit

    # Find all vertical wires in the circuit
    vertical_wires = find_vertical_wires(circuit.elements)

    if not vertical_wires:
        import warnings

        warnings.warn("No vertical wires found in circuit", stacklevel=2)
        return circuit

    # If no wire labels are provided, do not add any labels
    if wire_labels is None:
        return circuit

    # Check label count vs vertical wire count
    if len(wire_labels) != len(vertical_wires):
        from schematika.core.exceptions import WireLabelMismatchError

        raise WireLabelMismatchError(
            expected=len(wire_labels), actual=len(vertical_wires)
        )

    new_elements = []

    # Add labels to each wire
    for i, wire in enumerate(vertical_wires):
        if i >= len(wire_labels):
            break

        label_text = wire_labels[i]

        # Calculate label position at wire midpoint
        label_pos = calculate_wire_label_position(
            wire.start, wire.end, offset_x=offset_x
        )

        # Create text element
        text_element = create_wire_label_text(label_text, label_pos)

        # Add to new elements list
        new_elements.append(text_element)

    return Circuit(
        symbols=circuit.symbols,
        elements=list(circuit.elements) + new_elements,
    )


def apply_wire_labels(
    circuit: "Circuit",
    wire_labels: Sequence[str] | None,
) -> "Circuit":
    """No-op if *wire_labels* is None; else `add_wire_labels_to_circuit`."""
    if wire_labels is not None:
        return add_wire_labels_to_circuit(circuit, wire_labels)
    return circuit
