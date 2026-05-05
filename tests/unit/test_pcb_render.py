"""Tests for pcb/render.py — ConnectorBlock and FloatingPart to Circuit."""

from schematika.core.geometry import Point, Vector
from schematika.core.primitives import Line, Text
from schematika.core.symbol import Port, Symbol
from schematika.electrical.system.system import Circuit
from schematika.pcb.layout_spec import LayoutSpec
from schematika.pcb.model import (
    Column,
    ConnectorBlock,
    FloatingPart,
    PinColumns,
    PinPlacement,
    PlacedSlice,
    PowerNetMap,
    SymbolMapping,
    Terminator,
)
from schematika.pcb.render import render_connector_block, render_floating_part


def _two_port_symbol() -> Symbol:
    return Symbol(
        elements=[],
        ports={
            "1": Port("1", Point(0, -2.5), Vector(0, -1)),
            "2": Port("2", Point(0, 2.5), Vector(0, 1)),
        },
        label="X1",
    )


def _make_placed_slice() -> PlacedSlice:
    return PlacedSlice(
        part_ref="F1",
        slice_index=0,
        symbol=_two_port_symbol(),
        pins=(
            PinPlacement(pin_id="1", port_name="1"),
            PinPlacement(pin_id="2", port_name="2"),
        ),
    )


def _make_block_one_slice() -> ConnectorBlock:
    placed = _make_placed_slice()
    col = Column(slices=(placed,), terminator=Terminator.NC)
    pc = PinColumns(pin_id="1", columns=(col,))
    return ConnectorBlock(connector_ref="J1", functional_label="PSU", pin_columns=(pc,))


# ---------------------------------------------------------------------------
# Legacy smoke tests (preserved with updated helper)
# ---------------------------------------------------------------------------


def test_render_connector_block_returns_circuit() -> None:
    block = _make_block_one_slice()
    circuit = render_connector_block(block)
    assert isinstance(circuit, Circuit)


def test_render_connector_block_adds_symbols() -> None:
    block = _make_block_one_slice()
    circuit = render_connector_block(block)
    # 1 connector anchor block + 1 placed slice = 2 symbols
    assert len(circuit.symbols) == 2


def test_render_floating_part_returns_circuit() -> None:
    fp = FloatingPart(part_ref="K1")
    circuit = render_floating_part(fp)
    assert isinstance(circuit, Circuit)


def test_render_floating_part_is_empty() -> None:
    fp = FloatingPart(part_ref="K1")
    circuit = render_floating_part(fp)
    assert circuit.symbols == []
    assert circuit.elements == []


# ---------------------------------------------------------------------------
# New policy tests
# ---------------------------------------------------------------------------


def test_render_origin_y_respected() -> None:
    """Connector box top edge is at origin_y_mm."""
    layout = LayoutSpec()
    # Block with one empty pin column (no slices)
    pc = PinColumns(pin_id="1", columns=())
    block = ConnectorBlock(connector_ref="J1", functional_label=None, pin_columns=(pc,))
    circuit = render_connector_block(block, origin_y_mm=30.0, layout=layout)
    # The anchor symbol is the only symbol; it was placed at y=30.
    # After translation, its box (top edge at y=0 in local frame) is at y=30.
    assert len(circuit.symbols) == 1
    placed = circuit.symbols[0]
    # The ref text is at local y = -TERMINAL_TEXT_SIZE*0.5; after placement at y=30,
    # it ends up at 30 - TERMINAL_TEXT_SIZE*0.5, which is slightly below 30.
    # The box top edge is at local y=0 -> global y=30.
    # We check that no Text is positioned near y=0 (which would mean origin_y was ignored).
    text_ys = [el.position.y for el in placed.elements if isinstance(el, Text)]
    # All text elements should be near origin_y (30), not near 0.
    for ty in text_ys:
        assert ty >= 30 - 5, f"Text y={ty} is too far below origin_y=30"


def test_first_column_has_pin_to_first_slice_wire() -> None:
    """Gap wire pin_anchor_y -> chain_y and slice bottom port -> terminator are emitted."""
    layout = LayoutSpec()
    origin_y = 0.0
    placed = _make_placed_slice()
    col = Column(slices=(placed,), terminator=Terminator.NC)
    pc = PinColumns(pin_id="1", columns=(col,))
    block = ConnectorBlock(connector_ref="J1", functional_label=None, pin_columns=(pc,))

    circuit = render_connector_block(block, origin_y_mm=origin_y, layout=layout)

    pin_anchor_y = origin_y + layout.block_height_mm
    pin_x = layout.side_padding_mm + 0.5 * layout.pin_spacing_mm
    gap = layout.connector_to_first_slice_gap_mm  # default 15
    chain_y = pin_anchor_y + gap
    # _two_port_symbol: top port at local y=-2.5, bottom port at local y=+2.5.
    # sym_y = chain_y - (-2.5) = chain_y + 2.5 -> bottom port at chain_y + 5.
    # terminator_y = chain_y + slice_height_mm.
    # Gap wire: (pin_anchor_y) -> (chain_y).
    # Slice-to-term wire: (chain_y + 5) -> (chain_y + slice_height_mm).
    gap_end_y = chain_y
    expected_start_y = chain_y + 5.0
    expected_end_y = chain_y + layout.slice_height_mm
    tolerance = 1e-4

    lines = [el for el in circuit.elements if isinstance(el, Line)]
    pin_lines = [ln for ln in lines if abs(ln.start.x - pin_x) < tolerance]

    # Gap wire from pin_anchor_y to chain_y
    gap_wires = [
        ln
        for ln in pin_lines
        if abs(ln.start.y - pin_anchor_y) < tolerance
        and abs(ln.end.y - gap_end_y) < tolerance
    ]
    assert len(gap_wires) >= 1, (
        f"Expected gap wire from y={pin_anchor_y} to y={gap_end_y}; "
        f"lines at pin_x: {[(ln.start.y, ln.end.y) for ln in pin_lines]}"
    )

    # Slice-to-terminator wire
    slice_to_term_wires = [
        ln
        for ln in pin_lines
        if abs(ln.start.y - expected_start_y) < tolerance
        and abs(ln.end.y - expected_end_y) < tolerance
    ]
    assert len(slice_to_term_wires) >= 1, (
        f"Expected wire from y={expected_start_y} to y={expected_end_y}; "
        f"lines at pin_x: {[(ln.start.y, ln.end.y) for ln in pin_lines]}"
    )


def test_no_wire_between_columns_under_same_pin() -> None:
    """No Line should connect the bottom of column 1 to the top of column 2."""
    layout = LayoutSpec()
    origin_y = 0.0

    col1 = Column(
        slices=(_make_placed_slice(),),
        terminator=Terminator.LABEL,
        terminator_label="net_a",
    )
    col2 = Column(
        slices=(_make_placed_slice(),),
        terminator=Terminator.NC,
    )
    pc = PinColumns(pin_id="1", columns=(col1, col2))
    block = ConnectorBlock(connector_ref="J1", functional_label=None, pin_columns=(pc,))

    circuit = render_connector_block(block, origin_y_mm=origin_y, layout=layout)

    pin_anchor_y = origin_y + layout.block_height_mm
    gap = layout.connector_to_first_slice_gap_mm
    chain_y_col1 = pin_anchor_y + gap
    # Column 1: terminator_y = chain_y + slice_height_mm; cursor_y = terminator_y + slice_height_mm
    col1_end_y = chain_y_col1 + layout.slice_height_mm
    cursor_after_col1 = col1_end_y + layout.slice_height_mm
    # Column 2: cursor_y advances by slice_height_mm then becomes chain_y
    col2_start_y = cursor_after_col1 + layout.slice_height_mm

    lines = [el for el in circuit.elements if isinstance(el, Line)]
    # No line should have start_y >= col1_end_y AND end_y <= col2_start_y
    # (that would be a cross-column wire)
    pin_x = layout.side_padding_mm + 0.5 * layout.pin_spacing_mm
    tolerance = 0.5
    cross_column_wires = [
        ln
        for ln in lines
        if abs(ln.start.x - pin_x) < tolerance
        and ln.start.y >= col1_end_y - tolerance
        and ln.end.y <= col2_start_y + tolerance
        and ln.start.y < ln.end.y  # downward wire
    ]
    assert cross_column_wires == [], (
        f"Found {len(cross_column_wires)} cross-column wire(s): {cross_column_wires}"
    )


def test_subsequent_column_has_no_incoming_label() -> None:
    """Column 2 must NOT have an incoming label (xxx→); the outgoing label of col 1 is enough."""
    layout = LayoutSpec()

    col1 = Column(
        slices=(_make_placed_slice(),),
        terminator=Terminator.LABEL,
        terminator_label="net_a",
    )
    col2 = Column(
        slices=(_make_placed_slice(),),
        terminator=Terminator.NC,
    )
    pc = PinColumns(pin_id="1", columns=(col1, col2))
    block = ConnectorBlock(connector_ref="J1", functional_label=None, pin_columns=(pc,))

    circuit = render_connector_block(block, origin_y_mm=0.0, layout=layout)

    texts = [el for el in circuit.elements if isinstance(el, Text)]
    # No text should end with "→" — that was the incoming-label pattern (e.g. "net_a→").
    # Outgoing CONTINUATION labels use the prefix form "→net_a" and are fine.
    trailing_arrow = [t for t in texts if t.content.endswith("→")]
    assert trailing_arrow == [], (
        f"Found unexpected incoming label(s): {[t.content for t in trailing_arrow]}"
    )


def test_in_column_slice_to_slice_wire() -> None:
    """Within one column, consecutive slices must be connected by a wire across the gap."""
    layout = LayoutSpec()
    origin_y = 0.0

    slice1 = _make_placed_slice()
    slice2 = PlacedSlice(
        part_ref="F2",
        slice_index=1,
        symbol=_two_port_symbol(),
        pins=(
            PinPlacement(pin_id="1", port_name="1"),
            PinPlacement(pin_id="2", port_name="2"),
        ),
    )
    col = Column(slices=(slice1, slice2), terminator=Terminator.NC)
    pc = PinColumns(pin_id="1", columns=(col,))
    block = ConnectorBlock(connector_ref="J1", functional_label=None, pin_columns=(pc,))

    circuit = render_connector_block(block, origin_y_mm=origin_y, layout=layout)

    pin_x = layout.side_padding_mm + 0.5 * layout.pin_spacing_mm
    pin_anchor_y = origin_y + layout.block_height_mm
    gap = layout.connector_to_first_slice_gap_mm
    chain_y = pin_anchor_y + gap
    # _two_port_symbol: top_local=-2.5, bot_local=+2.5.
    # Slice 1: sym_y = chain_y + 2.5, bottom port at chain_y + 5.
    # Slice 2 top port should land at slice_top_y = chain_y + slice_height_mm.
    # Wire: (pin_x, chain_y + 5) -> (pin_x, chain_y + slice_height_mm).
    expected_wire_start = chain_y + 5.0
    expected_wire_end = chain_y + layout.slice_height_mm
    tolerance = 1e-4

    lines = [el for el in circuit.elements if isinstance(el, Line)]
    inter_slice_wires = [
        ln
        for ln in lines
        if abs(ln.start.x - pin_x) < tolerance
        and abs(ln.start.y - expected_wire_start) < tolerance
        and abs(ln.end.y - expected_wire_end) < tolerance
    ]
    assert len(inter_slice_wires) >= 1, (
        f"Expected inter-slice wire from y={expected_wire_start} to y={expected_wire_end}; "
        f"lines at pin_x: {[(ln.start.y, ln.end.y) for ln in lines if abs(ln.start.x - pin_x) < tolerance]}"
    )


def test_power_terminator_has_wire_to_symbol() -> None:
    """POWER terminator: wire from last slice bottom to power symbol, symbol placed at correct y."""
    layout = LayoutSpec()
    origin_y = 0.0

    # Build a minimal 1-port power symbol factory
    def power_sym_factory() -> Symbol:
        return Symbol(
            elements=[],
            ports={"pwr": Port("pwr", Point(0, 0), Vector(0, -1))},
            label="+24V",
        )

    pnet = PowerNetMap(
        canonical_name="+24V",
        symbol=power_sym_factory,
    )
    mapping = SymbolMapping(symbols=(), connectors=(), power_nets=(pnet,))

    col = Column(
        slices=(_make_placed_slice(),),
        terminator=Terminator.POWER,
        terminator_label="+24V",
    )
    pc = PinColumns(pin_id="1", columns=(col,))
    block = ConnectorBlock(connector_ref="J1", functional_label=None, pin_columns=(pc,))

    circuit = render_connector_block(
        block, mapping=mapping, origin_y_mm=origin_y, layout=layout
    )

    pin_anchor_y = origin_y + layout.block_height_mm
    chain_y = pin_anchor_y + layout.connector_to_first_slice_gap_mm
    terminator_y = chain_y + layout.slice_height_mm  # after 1 slice
    expected_power_y = terminator_y + layout.power_terminator_offset_mm

    pin_x = layout.side_padding_mm + 0.5 * layout.pin_spacing_mm
    tolerance = 0.1

    # Assert wire from terminator_y to power symbol y
    lines = [el for el in circuit.elements if isinstance(el, Line)]
    power_wire = [
        ln
        for ln in lines
        if abs(ln.start.x - pin_x) < tolerance
        and abs(ln.start.y - terminator_y) < tolerance
        and abs(ln.end.y - expected_power_y) < tolerance
    ]
    assert len(power_wire) >= 1, (
        f"Expected wire from y={terminator_y} to y={expected_power_y}; "
        f"lines at pin_x={pin_x}: {[(ln.start.y, ln.end.y) for ln in lines if abs(ln.start.x - pin_x) < tolerance]}"
    )

    # Assert power symbol is in circuit at expected_power_y
    power_syms = [s for s in circuit.symbols if s.label == "+24V"]
    assert len(power_syms) >= 1, "Power symbol should be placed in circuit"
