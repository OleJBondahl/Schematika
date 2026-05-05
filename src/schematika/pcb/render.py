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
    _PIN_SPACING,
    _TOP_PADDING,
    connector_block,
)

_CONNECTOR_BLOCK_WIDTH_MM = 2 * GRID_SIZE  # 10 mm
_FIRST_COL_OFFSET_MM = 2 * GRID_SIZE  # 10 mm gap between anchor block and first column
_SLICE_HEIGHT_MM = 2 * GRID_SIZE  # 10 mm vertical step between stacked slices
_WIRE_STYLE = Style(stroke="black", fill="none", stroke_width=0.25)
_LABEL_STYLE = Style(stroke="none", fill="black", font_family=TEXT_FONT_FAMILY)


def _render_label(circuit: Circuit, text: str, x: float, y: float) -> None:
    circuit.elements.append(
        Text(
            content=text,
            position=Point(x, y),
            anchor="middle",
            font_size=TERMINAL_TEXT_SIZE,
            style=_LABEL_STYLE,
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
        return
    if terminator is Terminator.POWER and label is not None:
        for pnet in mapping.power_nets:
            if pnet.matches(label):
                add_symbol(circuit, pnet.symbol(), x=x, y=y)
                return
        _render_label(circuit, label, x, y)
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

    Each PinColumns row maps to a pin on the anchor block. Slices stack
    downward within each column. Terminators appear below the last slice.
    A vertical wire connects consecutive slices and the anchor port.

    Args:
        block: A ConnectorBlock from pcb.build().
        mapping: SymbolMapping for power-net terminator lookup. If None,
            power terminators fall back to a text label.
        origin_x_mm: X offset for this block on the page (mm).
        column_spacing_mm: Width of one symbol column (mm).

    Returns:
        A populated Circuit with connector, slice, wire, and terminator elements.
    """
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
        # Y of this pin's port on the anchor block (from connector_block geometry).
        pin_anchor_y = _TOP_PADDING + (pin_idx + 0.5) * _PIN_SPACING

        for col_idx, column in enumerate(pin_col.columns):
            col_x = (
                origin_x_mm
                + _CONNECTOR_BLOCK_WIDTH_MM
                + _FIRST_COL_OFFSET_MM
                + col_idx * column_spacing_mm
            )

            prev_y = pin_anchor_y
            for slice_idx, placed in enumerate(column.slices):
                sym_y = pin_anchor_y + slice_idx * _SLICE_HEIGHT_MM
                add_symbol(circuit, placed.symbol, x=col_x, y=sym_y)
                _render_wire(circuit, col_x, prev_y, sym_y)
                prev_y = sym_y + _SLICE_HEIGHT_MM

            _render_terminator(circuit, column, mapping, col_x, prev_y)

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
