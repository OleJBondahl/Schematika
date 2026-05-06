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
    gap = layout.connector_to_first_symbol_gap_mm  # default 120
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
    gap = layout.connector_to_first_symbol_gap_mm
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
    gap = layout.connector_to_first_symbol_gap_mm
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


def test_nc_terminator_renders_at_pin_anchor_y() -> None:
    """NC cross and label must be placed flush at pin_anchor_y (no extra gap)."""
    layout = LayoutSpec()
    origin_y = 0.0
    col = Column(slices=(), terminator=Terminator.NC)
    pc = PinColumns(pin_id="1", columns=(col,))
    block = ConnectorBlock(connector_ref="J1", functional_label=None, pin_columns=(pc,))

    circuit = render_connector_block(block, origin_y_mm=origin_y, layout=layout)

    pin_anchor_y = origin_y + layout.block_height_mm
    tol = 0.5

    lines = [el for el in circuit.elements if isinstance(el, Line)]
    # NC cross arms: two diagonal lines whose midpoint y must equal pin_anchor_y.
    nc_diags = [
        ln
        for ln in lines
        if abs(ln.end.x - ln.start.x) > tol and abs(ln.end.y - ln.start.y) > tol
    ]
    mid_ys = [(ln.start.y + ln.end.y) / 2 for ln in nc_diags]
    assert any(abs(my - pin_anchor_y) < tol for my in mid_ys), (
        f"NC cross midpoint not at pin_anchor_y={pin_anchor_y}; "
        f"diagonals: {[(ln.start.y, ln.end.y) for ln in nc_diags]}"
    )

    # NC text should be close to pin_anchor_y (within font-size + cross-arm height)
    texts = [el for el in circuit.elements if isinstance(el, Text)]
    nc_texts = [t for t in texts if t.content == "NC"]
    assert nc_texts, "Expected NC label text"
    nc_y = nc_texts[0].position.y
    assert abs(nc_y - pin_anchor_y) < layout.slice_height_mm, (
        f"NC label y={nc_y} too far from pin_anchor_y={pin_anchor_y}"
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
    chain_y = pin_anchor_y + layout.connector_to_first_symbol_gap_mm
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


def test_pin_at_bottom_port_at_bottom_y_and_body_below() -> None:
    """PIN_AT_BOTTOM: port must land exactly at bottom_terminator_y_mm and
    every box element's bbox must be at world Y >= bottom_terminator_y_mm."""
    from schematika.core.primitives import Polygon

    bottom_y = 200.0
    layout = LayoutSpec(bottom_terminator_y_mm=bottom_y)
    label = "J7:2"
    col = Column(
        slices=(),
        terminator=Terminator.PIN_AT_BOTTOM,
        terminator_label=label,
    )
    pc = PinColumns(pin_id="1", columns=(col,))
    block = ConnectorBlock(connector_ref="J1", functional_label=None, pin_columns=(pc,))

    circuit = render_connector_block(block, origin_y_mm=0.0, layout=layout)

    pin_syms = [s for s in circuit.symbols if s.label == label]
    assert pin_syms, f"Expected connector_pin symbol with label {label!r}"
    sym = pin_syms[0]

    # Port must be at world y = bottom_y
    port = sym.ports["1"]
    assert abs(port.position.y - bottom_y) < 0.01, (
        f"Port y={port.position.y} != bottom_y={bottom_y}"
    )

    # All box polygons must have every vertex at y >= bottom_y
    boxes = [el for el in sym.elements if isinstance(el, Polygon)]
    tol = 1e-9
    for poly in boxes:
        for pt in poly.points:
            assert pt.y >= bottom_y - tol, (
                f"Box vertex y={pt.y} is above bottom_y={bottom_y}"
            )


# ---------------------------------------------------------------------------
# Top chain label tests
# ---------------------------------------------------------------------------


def test_top_chain_label_renders_for_chain_with_slice() -> None:
    layout = LayoutSpec()
    placed = _make_placed_slice()
    col = Column(slices=(placed,), terminator=Terminator.NC, chain_net_name="test_net")
    pc = PinColumns(pin_id="1", columns=(col,))
    block = ConnectorBlock(
        connector_ref="J1",
        functional_label=None,
        pin_columns=(pc,),
        bottom_terminator=False,
    )
    origin_y = 0.0
    circuit = render_connector_block(block, origin_y_mm=origin_y, layout=layout)

    pin_x = layout.side_padding_mm + 0.5 * layout.pin_spacing_mm
    pin_anchor_y = origin_y + layout.block_height_mm

    rotated_texts = [
        el
        for el in circuit.elements
        if isinstance(el, Text) and getattr(el, "rotation", 0) == 90
    ]
    net_labels = [t for t in rotated_texts if t.content == "test_net"]
    assert len(net_labels) == 1, (
        f"Expected exactly one 'test_net' label, got {net_labels}"
    )
    label = net_labels[0]
    assert abs(label.position.x - (pin_x - layout.wire_to_label_gap_mm)) < 1e-9
    assert (
        abs(label.position.y - (pin_anchor_y + layout.connector_to_first_label_gap_mm))
        < 1e-9
    )


def test_top_chain_label_skipped_for_label_terminator_no_slice() -> None:
    layout = LayoutSpec()
    col = Column(
        slices=(),
        terminator=Terminator.LABEL,
        terminator_label="net_a",
        chain_net_name="net_a",
    )
    pc = PinColumns(pin_id="1", columns=(col,))
    block = ConnectorBlock(connector_ref="J1", functional_label=None, pin_columns=(pc,))
    origin_y = 0.0
    circuit = render_connector_block(block, origin_y_mm=origin_y, layout=layout)

    # The new top-chain label would be at pin_x - wire_to_label_gap_mm; terminator
    # outgoing label sits at pin_x. Distinguish by x position.
    pin_x = layout.side_padding_mm + 0.5 * layout.pin_spacing_mm
    label_x = pin_x - layout.wire_to_label_gap_mm
    pin_anchor_y = origin_y + layout.block_height_mm
    expected_y = pin_anchor_y + layout.connector_to_first_label_gap_mm
    rotated_at_label_pos = [
        el
        for el in circuit.elements
        if isinstance(el, Text)
        and getattr(el, "rotation", 0) == 90
        and abs(el.position.x - label_x) < 1e-9
        and abs(el.position.y - expected_y) < 1e-9
        and el.content == "net_a"
    ]
    assert rotated_at_label_pos == [], (
        f"Expected no net-name label at offset-x position, got {rotated_at_label_pos}"
    )


def test_top_chain_label_skipped_for_power_terminator_no_slice() -> None:
    layout = LayoutSpec()
    col = Column(
        slices=(),
        terminator=Terminator.POWER,
        terminator_label="+24V",
        chain_net_name=None,
    )
    pc = PinColumns(pin_id="1", columns=(col,))
    block = ConnectorBlock(connector_ref="J1", functional_label=None, pin_columns=(pc,))
    circuit = render_connector_block(block, origin_y_mm=0.0, layout=layout)

    # The new top-chain label would be at pin_x - wire_to_label_gap_mm.
    # POWER terminator with chain_net_name=None should not produce a label at that x.
    pin_x = layout.side_padding_mm + 0.5 * layout.pin_spacing_mm
    label_x = pin_x - layout.wire_to_label_gap_mm
    rotated_at_label_x = [
        el
        for el in circuit.elements
        if isinstance(el, Text)
        and getattr(el, "rotation", 0) == 90
        and abs(el.position.x - label_x) < 1e-9
    ]
    assert rotated_at_label_x == [], (
        f"Expected no rotated net-name label at offset-x for POWER-no-slice, got {rotated_at_label_x}"
    )


def test_top_chain_label_skipped_for_nc_no_slice() -> None:
    layout = LayoutSpec()
    col = Column(slices=(), terminator=Terminator.NC, chain_net_name=None)
    pc = PinColumns(pin_id="1", columns=(col,))
    block = ConnectorBlock(connector_ref="J1", functional_label=None, pin_columns=(pc,))
    circuit = render_connector_block(block, origin_y_mm=0.0, layout=layout)

    rotated_net_labels = [
        el
        for el in circuit.elements
        if isinstance(el, Text)
        and getattr(el, "rotation", 0) == 90
        and el.content not in ("NC",)
    ]
    assert rotated_net_labels == [], (
        f"Expected no rotated net-name label for NC-no-slice, got {rotated_net_labels}"
    )


def test_top_chain_label_renders_for_pin_at_bottom_no_slice() -> None:
    layout = LayoutSpec()
    col = Column(
        slices=(),
        terminator=Terminator.PIN_AT_BOTTOM,
        terminator_label="J7:2",
        chain_net_name="em_stop_chain",
    )
    pc = PinColumns(pin_id="1", columns=(col,))
    block = ConnectorBlock(
        connector_ref="J1",
        functional_label=None,
        pin_columns=(pc,),
        bottom_terminator=False,
    )
    origin_y = 0.0
    circuit = render_connector_block(block, origin_y_mm=origin_y, layout=layout)

    pin_x = layout.side_padding_mm + 0.5 * layout.pin_spacing_mm
    pin_anchor_y = origin_y + layout.block_height_mm

    rotated_texts = [
        el
        for el in circuit.elements
        if isinstance(el, Text) and getattr(el, "rotation", 0) == 90
    ]
    net_labels = [t for t in rotated_texts if t.content == "em_stop_chain"]
    assert len(net_labels) == 1, f"Expected one 'em_stop_chain' label, got {net_labels}"
    label = net_labels[0]
    assert abs(label.position.x - (pin_x - layout.wire_to_label_gap_mm)) < 1e-9
    assert (
        abs(label.position.y - (pin_anchor_y + layout.connector_to_first_label_gap_mm))
        < 1e-9
    )


def test_top_chain_label_skipped_for_bottom_terminator_connector() -> None:
    layout = LayoutSpec()
    placed = _make_placed_slice()
    col = Column(slices=(placed,), terminator=Terminator.NC, chain_net_name="net_x")
    pc = PinColumns(pin_id="1", columns=(col,))
    block = ConnectorBlock(
        connector_ref="J1",
        functional_label=None,
        pin_columns=(pc,),
        bottom_terminator=True,
    )
    circuit = render_connector_block(block, origin_y_mm=0.0, layout=layout)

    rotated_texts = [
        el
        for el in circuit.elements
        if isinstance(el, Text) and getattr(el, "rotation", 0) == 90
    ]
    net_labels = [t for t in rotated_texts if t.content == "net_x"]
    assert net_labels == [], (
        f"Expected no net-name label for bottom_terminator block, got {net_labels}"
    )


def test_top_chain_label_skipped_for_non_first_column() -> None:
    layout = LayoutSpec()
    placed1 = _make_placed_slice()
    placed2 = PlacedSlice(
        part_ref="F2",
        slice_index=0,
        symbol=_two_port_symbol(),
        pins=(
            PinPlacement(pin_id="1", port_name="1"),
            PinPlacement(pin_id="2", port_name="2"),
        ),
    )
    col0 = Column(
        slices=(placed1,),
        terminator=Terminator.LABEL,
        terminator_label="net_col0",
        chain_net_name="net_col0",
    )
    col1 = Column(
        slices=(placed2,), terminator=Terminator.NC, chain_net_name="net_col1"
    )
    pc = PinColumns(pin_id="1", columns=(col0, col1))
    block = ConnectorBlock(connector_ref="J1", functional_label=None, pin_columns=(pc,))
    circuit = render_connector_block(block, origin_y_mm=0.0, layout=layout)

    # The new top-chain label (when rendered) sits at pin_x - wire_to_label_gap_mm.
    pin_x = layout.side_padding_mm + 0.5 * layout.pin_spacing_mm
    label_x = pin_x - layout.wire_to_label_gap_mm

    # col1 is non-first → no top-chain label at label_x for "net_col1"
    col1_top_labels = [
        el
        for el in circuit.elements
        if isinstance(el, Text)
        and getattr(el, "rotation", 0) == 90
        and abs(el.position.x - label_x) < 1e-9
        and el.content == "net_col1"
    ]
    assert col1_top_labels == [], (
        f"Expected no net-name label for non-first column, got {col1_top_labels}"
    )

    # col0 is first and has slices → top-chain label at label_x for "net_col0"
    col0_top_labels = [
        el
        for el in circuit.elements
        if isinstance(el, Text)
        and getattr(el, "rotation", 0) == 90
        and abs(el.position.x - label_x) < 1e-9
        and el.content == "net_col0"
    ]
    assert len(col0_top_labels) == 1, (
        f"Expected top-chain label for first column, got {col0_top_labels}"
    )


def test_top_chain_label_text_position() -> None:
    layout = LayoutSpec(wire_to_label_gap_mm=2.0, connector_to_first_label_gap_mm=5.0)
    placed = _make_placed_slice()
    col = Column(slices=(placed,), terminator=Terminator.NC, chain_net_name="mynet")
    pc = PinColumns(pin_id="1", columns=(col,))
    block = ConnectorBlock(connector_ref="J1", functional_label=None, pin_columns=(pc,))
    origin_y = 0.0
    circuit = render_connector_block(block, origin_y_mm=origin_y, layout=layout)

    pin_x = layout.side_padding_mm + 0.5 * layout.pin_spacing_mm
    pin_anchor_y = origin_y + layout.block_height_mm

    rotated_texts = [
        el
        for el in circuit.elements
        if isinstance(el, Text) and getattr(el, "rotation", 0) == 90
    ]
    net_labels = [t for t in rotated_texts if t.content == "mynet"]
    assert len(net_labels) == 1
    label = net_labels[0]
    assert abs(label.position.x - (pin_x - 2.0)) < 1e-9, f"x={label.position.x}"
    assert abs(label.position.y - (pin_anchor_y + 5.0)) < 1e-9, f"y={label.position.y}"


def test_render_two_row_page_uses_per_row_origin_y() -> None:
    """A page with two rows places row-2 block anchors at the row-2 Y."""
    from schematika.core.primitives import Polygon

    # Call render_connector_block twice with different origin_y_mm and assert
    # the connector polygon top-edge moves accordingly.
    block = _make_block_one_slice()
    layout = LayoutSpec()
    c1 = render_connector_block(block, layout=layout, origin_x_mm=0, origin_y_mm=30.0)
    c2 = render_connector_block(block, layout=layout, origin_x_mm=0, origin_y_mm=168.5)
    anchor1 = c1.symbols[0]
    anchor2 = c2.symbols[0]
    polys1 = [el for el in anchor1.elements if isinstance(el, Polygon)]
    polys2 = [el for el in anchor2.elements if isinstance(el, Polygon)]
    assert polys1, "Expected polygon in row-1 anchor symbol"
    assert polys2, "Expected polygon in row-2 anchor symbol"
    top1 = min(p.y for p in polys1[0].points)
    top2 = min(p.y for p in polys2[0].points)
    assert abs(top1 - 30.0) < 1e-6
    assert abs(top2 - 168.5) < 1e-6
