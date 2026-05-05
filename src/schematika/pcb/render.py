"""Render ConnectorBlock and FloatingPart to schematika Circuit objects."""

from schematika.core.constants import TERMINAL_TEXT_SIZE, TEXT_FONT_FAMILY
from schematika.core.geometry import Point, Style
from schematika.core.primitives import Line, Text
from schematika.electrical.system.system import Circuit, add_symbol
from schematika.pcb.layout_spec import LayoutSpec
from schematika.pcb.model import (
    Column,
    ConnectorBlock,
    FloatingPart,
    SymbolMapping,
    Terminator,
)
from schematika.pcb.symbols.connector_block import connector_block

_WIRE_STYLE = Style(stroke="black", fill="none", stroke_width=0.25)
_LABEL_STYLE = Style(stroke="none", fill="black", font_family=TEXT_FONT_FAMILY)


def _render_outgoing_label(circuit: Circuit, text: str, x: float, y: float) -> None:
    circuit.elements.append(
        Text(
            content=text,
            position=Point(x, y),
            anchor="start",
            font_size=TERMINAL_TEXT_SIZE,
            style=_LABEL_STYLE,
            rotation=90,
        )
    )


def _render_incoming_label(circuit: Circuit, text: str, x: float, y: float) -> None:
    circuit.elements.append(
        Text(
            content=f"{text}→",
            position=Point(x, y),
            anchor="end",
            font_size=TERMINAL_TEXT_SIZE,
            style=_LABEL_STYLE,
            rotation=90,
        )
    )


def _autoconnect_wire(circuit: Circuit, x: float, y_start: float, y_end: float) -> None:
    if y_end <= y_start:
        return
    circuit.elements.append(Line(Point(x, y_start), Point(x, y_end), _WIRE_STYLE))


def _render_terminator(
    circuit: Circuit,
    column: Column,
    mapping: SymbolMapping,
    layout: LayoutSpec,
    x: float,
    y: float,
) -> None:
    terminator = column.terminator
    label = column.terminator_label
    if terminator is Terminator.NC:
        half = 1.0
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
        power_y = y + layout.power_terminator_offset_mm
        for pnet in mapping.power_nets:
            if pnet.matches(label):
                add_symbol(circuit, pnet.symbol(), x=x, y=power_y)
                _autoconnect_wire(circuit, x, y, power_y)
                return
        _render_outgoing_label(circuit, label, x, power_y)
        return
    if terminator is Terminator.LABEL and label is not None:
        _render_outgoing_label(circuit, label, x, y)
        return
    if terminator is Terminator.CONTINUATION and label is not None:
        _render_outgoing_label(circuit, f"→{label}", x, y)


def render_connector_block(
    block: ConnectorBlock,
    mapping: SymbolMapping | None = None,
    *,
    origin_x_mm: float = 0.0,
    origin_y_mm: float | None = None,
    layout: LayoutSpec | None = None,
) -> Circuit:
    """Render one ConnectorBlock to a schematika Circuit.

    Wires are emitted ONLY within a single Column: pin->first slice,
    slice->slice within the column, and last slice->POWER terminator symbol.
    No wire is drawn between two Columns under the same pin; the second
    Column starts with an incoming label derived from the previous Column's
    terminator label.
    """
    if layout is None:
        layout = LayoutSpec()
    if origin_y_mm is None:
        origin_y_mm = layout.page_top_margin_mm
    if mapping is None:
        mapping = SymbolMapping(symbols=(), connectors=(), power_nets=())

    circuit = Circuit()
    pin_ids = [pc.pin_id for pc in block.pin_columns]

    anchor_sym = connector_block(
        ref=block.connector_ref,
        pins=pin_ids,
        functional_label=block.functional_label,
        layout=layout,
    )
    add_symbol(circuit, anchor_sym, x=origin_x_mm, y=origin_y_mm)

    for pin_idx, pin_col in enumerate(block.pin_columns):
        pin_x = (
            origin_x_mm
            + layout.side_padding_mm
            + (pin_idx + 0.5) * layout.pin_spacing_mm
        )
        pin_anchor_y = origin_y_mm + layout.block_height_mm
        cursor_y = pin_anchor_y

        for col_idx, column in enumerate(pin_col.columns):
            if col_idx == 0:
                pass  # first column: wire drawn in slice loop below
            else:
                cursor_y += layout.section_gap_mm
                prev_label = pin_col.columns[col_idx - 1].terminator_label
                if prev_label is not None:
                    _render_incoming_label(circuit, prev_label, pin_x, cursor_y)
                cursor_y += layout.section_gap_mm

            prev_y = cursor_y
            for placed in column.slices:
                sym_y = cursor_y
                _autoconnect_wire(circuit, pin_x, prev_y, sym_y)
                add_symbol(circuit, placed.symbol, x=pin_x, y=sym_y)
                prev_y = sym_y + layout.slice_height_mm
                cursor_y = prev_y

            _render_terminator(circuit, column, mapping, layout, pin_x, cursor_y)
            cursor_y += layout.slice_height_mm

    return circuit


def render_floating_part(floating: FloatingPart) -> Circuit:
    """Render a FloatingPart as an empty Circuit (for linter pickup only)."""
    del floating
    return Circuit()
