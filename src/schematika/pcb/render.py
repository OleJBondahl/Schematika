"""Render ConnectorBlock and FloatingPart to schematika Circuit objects."""

from schematika.core.constants import TERMINAL_TEXT_SIZE, TEXT_FONT_FAMILY
from schematika.core.geometry import Point, Style
from schematika.core.primitives import Line, Text
from schematika.core.symbol import Symbol
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
from schematika.pcb.symbols.connector_pin_small import connector_pin_small

_WIRE_STYLE = Style(stroke="black", fill="none", stroke_width=0.25)
_LABEL_STYLE = Style(stroke="none", fill="black", font_family=TEXT_FONT_FAMILY)
_PORT_DIRECTION_THRESHOLD = 1e-6


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


def _autoconnect_wire(circuit: Circuit, x: float, y_start: float, y_end: float) -> None:
    if y_end <= y_start:
        return
    circuit.elements.append(Line(Point(x, y_start), Point(x, y_end), _WIRE_STYLE))


def _top_port_y_local(symbol: Symbol) -> float:
    """Return local Y of the topmost (incoming) port — direction dy < 0."""
    threshold = _PORT_DIRECTION_THRESHOLD
    upward = [p for p in symbol.ports.values() if p.direction.dy < -threshold]
    if upward:
        return min(p.position.y for p in upward)
    if not symbol.ports:
        return 0.0
    return min(p.position.y for p in symbol.ports.values())


def _bottom_port_y_local(symbol: Symbol) -> float:
    """Return local Y of the bottommost (outgoing) port — direction dy > 0."""
    threshold = _PORT_DIRECTION_THRESHOLD
    downward = [p for p in symbol.ports.values() if p.direction.dy > threshold]
    if downward:
        return max(p.position.y for p in downward)
    if not symbol.ports:
        return 0.0
    return max(p.position.y for p in symbol.ports.values())


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
        return
    if terminator is Terminator.PIN_AT_BOTTOM and label is not None:
        bottom_y = layout.bottom_terminator_y_mm
        if bottom_y > y + _PORT_DIRECTION_THRESHOLD:
            _autoconnect_wire(circuit, x, y, bottom_y)
        pin_sym = connector_pin_small(label=label, label_pos="left")
        port_local_y = pin_sym.ports["1"].position.y
        add_symbol(circuit, pin_sym, x=x, y=bottom_y - port_local_y)


def _render_column_slices(
    circuit: Circuit,
    column: Column,
    layout: LayoutSpec,
    pin_x: float,
    chain_y: float,
) -> float:
    """Place slices and emit in-column wires. Return terminator_y."""
    slice_top_y = chain_y
    last_outgoing_y = chain_y

    for placed in column.slices:
        sym = placed.symbol
        top_local = _top_port_y_local(sym)
        bot_local = _bottom_port_y_local(sym)

        sym_y = slice_top_y - top_local
        if slice_top_y > last_outgoing_y + _PORT_DIRECTION_THRESHOLD:
            _autoconnect_wire(circuit, pin_x, last_outgoing_y, slice_top_y)
        add_symbol(circuit, sym, x=pin_x, y=sym_y)

        last_outgoing_y = sym_y + bot_local
        slice_top_y += layout.slice_height_mm

    terminator_y = slice_top_y if column.slices else chain_y

    if column.slices:
        if terminator_y > last_outgoing_y + _PORT_DIRECTION_THRESHOLD:
            _autoconnect_wire(circuit, pin_x, last_outgoing_y, terminator_y)
    elif terminator_y > chain_y + _PORT_DIRECTION_THRESHOLD:
        _autoconnect_wire(circuit, pin_x, chain_y, terminator_y)

    return terminator_y


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
                if column.slices:
                    chain_y = pin_anchor_y + layout.connector_to_first_symbol_gap_mm
                else:
                    chain_y = pin_anchor_y + layout.connector_to_first_label_gap_mm
                cursor_y = chain_y
                _autoconnect_wire(circuit, pin_x, pin_anchor_y, chain_y)
            else:
                # Subsequent columns: only the previous column's outgoing label marks
                # the boundary. Skip slice_height so the label clears the next column.
                cursor_y += layout.slice_height_mm
                chain_y = cursor_y

            terminator_y = _render_column_slices(
                circuit, column, layout, pin_x, chain_y
            )
            _render_terminator(circuit, column, mapping, layout, pin_x, terminator_y)
            cursor_y = terminator_y + layout.slice_height_mm

    return circuit


def render_floating_part(floating: FloatingPart) -> Circuit:
    """Render a FloatingPart as an empty Circuit (for linter pickup only)."""
    del floating
    return Circuit()
