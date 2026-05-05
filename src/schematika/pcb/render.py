"""Render ConnectorBlock and FloatingPart to schematika Circuit objects.

This module is the boundary between pure pcb data and schematika's
rendering pipeline. Lives in schematika.pcb so it can import from
schematika.electrical.* without crossing layer boundaries (importlinter
forbids pcb from importing schematika.project).
"""

from schematika.core.constants import (
    GRID_SIZE,
    TERMINAL_TEXT_SIZE,
    TEXT_FONT_FAMILY,
)
from schematika.core.geometry import Point, Style
from schematika.core.primitives import Line, Text
from schematika.electrical.system.system import Circuit, add_symbol
from schematika.pcb.model import (
    Column,
    ConnectorBlock,
    FloatingPart,
    SymbolMapping,
    Terminator,
)
from schematika.pcb.symbols.connector_block import (
    _BLOCK_HEIGHT,
    _PIN_SPACING,
    _SIDE_PADDING,
    connector_block,
)

_SLICE_HEIGHT_MM = 3 * GRID_SIZE  # 15 mm vertical step between stacked slices
_SECTION_GAP_MM = GRID_SIZE  # 5 mm gap between multi-column sections of the same pin
# Extra vertical offset for POWER terminators: pushes the symbol down so that
# adjacent pins whose terminator y-values land close together (due to differing
# slice counts) cannot have their triangle / bar bodies overlap each other.
_POWER_TERMINATOR_OFFSET_MM = GRID_SIZE  # 5 mm
_WIRE_STYLE = Style(stroke="black", fill="none", stroke_width=0.25)
_LABEL_STYLE = Style(stroke="none", fill="black", font_family=TEXT_FONT_FAMILY)


def _render_label(circuit: Circuit, text: str, x: float, y: float) -> None:
    circuit.elements.append(
        Text(
            content=text,
            position=Point(x, y),
            anchor="start",
            font_size=TERMINAL_TEXT_SIZE,
            style=_LABEL_STYLE,
            rotation=-90,
        )
    )


def _render_wire(circuit: Circuit, x: float, y_start: float, y_end: float) -> None:
    circuit.elements.append(Line(Point(x, y_start), Point(x, y_end), _WIRE_STYLE))


def _render_terminator(
    circuit: Circuit,
    column: Column,
    mapping: SymbolMapping,
    x: float,
    y: float,
) -> None:
    terminator = column.terminator
    label = column.terminator_label
    if terminator is Terminator.NC:
        # Draw a small x marker so the pin is visibly terminated rather than dangling.
        half = 1.0  # mm — half-width of each arm
        circuit.elements.append(
            Line(Point(x - half, y - half), Point(x + half, y + half), _WIRE_STYLE)
        )
        circuit.elements.append(
            Line(Point(x - half, y + half), Point(x + half, y - half), _WIRE_STYLE)
        )
        circuit.elements.append(
            Text(
                content="NC",
                position=Point(x, y + half + TERMINAL_TEXT_SIZE * 0.6),
                anchor="middle",
                font_size=TERMINAL_TEXT_SIZE,
                style=_LABEL_STYLE,
            )
        )
        return
    if terminator is Terminator.POWER and label is not None:
        power_y = y + _POWER_TERMINATOR_OFFSET_MM
        for pnet in mapping.power_nets:
            if pnet.matches(label):
                add_symbol(circuit, pnet.symbol(), x=x, y=power_y)
                return
        _render_label(circuit, label, x, power_y)
    elif terminator is Terminator.LABEL and label is not None:
        _render_label(circuit, label, x, y)
    elif terminator is Terminator.CONTINUATION and label is not None:
        _render_label(circuit, f"→{label}", x, y)


def render_connector_block(
    block: ConnectorBlock,
    mapping: SymbolMapping | None = None,
    *,
    origin_x_mm: float = 0.0,
    column_spacing_mm: float = 32.0,
) -> Circuit:
    """Render one ConnectorBlock to a schematika Circuit with full 2-D layout.

    The connector body sits horizontally at the top of the block. Pins emerge
    from the bottom edge facing downward. For each pin, all its columns stack
    vertically beneath that pin's X position (one section after another with a
    small gap). Terminators appear below the last slice of each column section.
    A vertical wire connects the anchor port to the first slice and between
    consecutive slices within a section.

    Args:
        block: A ConnectorBlock from pcb.build().
        mapping: SymbolMapping for power-net terminator lookup. If None,
            power terminators fall back to a text label.
        origin_x_mm: X offset for this block on the page (mm).
        column_spacing_mm: Preserved for API compatibility; not used internally
            (column layout is now driven by pin count and _PIN_SPACING).

    Returns:
        A populated Circuit with connector, slice, wire, and terminator elements.
    """
    del column_spacing_mm  # layout now driven by pin positions, not column slots

    if mapping is None:
        mapping = SymbolMapping(symbols=(), connectors=(), power_nets=())

    circuit = Circuit()
    pin_ids = [pc.pin_id for pc in block.pin_columns]

    anchor_sym = connector_block(
        ref=block.connector_ref,
        pins=pin_ids,
        functional_label=block.functional_label,
    )
    add_symbol(circuit, anchor_sym, x=origin_x_mm, y=0.0)

    for pin_idx, pin_col in enumerate(block.pin_columns):
        # X of this pin's port on the anchor block (from connector_block geometry).
        pin_x = origin_x_mm + _SIDE_PADDING + (pin_idx + 0.5) * _PIN_SPACING
        # Y of the pin's port — bottom edge of connector body.
        pin_anchor_y = _BLOCK_HEIGHT

        cursor_y = pin_anchor_y
        for col_idx, column in enumerate(pin_col.columns):
            if col_idx > 0:
                # Add a gap between consecutive column sections of the same pin.
                cursor_y += _SECTION_GAP_MM

            prev_y = cursor_y
            for placed in column.slices:
                sym_y = cursor_y
                _render_wire(circuit, pin_x, prev_y, sym_y)
                add_symbol(circuit, placed.symbol, x=pin_x, y=sym_y)
                prev_y = sym_y + _SLICE_HEIGHT_MM
                cursor_y = prev_y

            _render_terminator(circuit, column, mapping, pin_x, cursor_y)
            # Advance cursor past the terminator.
            cursor_y += _SLICE_HEIGHT_MM

    return circuit


def render_floating_part(floating: FloatingPart) -> Circuit:
    """Render a FloatingPart as an empty Circuit (for linter pickup only).

    Args:
        floating: A FloatingPart from pcb.build().

    Returns:
        An empty Circuit.
    """
    del floating  # to satisfy vulture
    return Circuit()
