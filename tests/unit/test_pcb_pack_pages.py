"""Tests for pack_pages with LayoutSpec and Page.placements."""

from types import SimpleNamespace

from schematika.core.geometry import Point, Vector
from schematika.core.symbol import Port, Symbol
from schematika.pcb.adapter import CircuitIR, NetRef, PartRef, PinRef
from schematika.pcb.layout_spec import LayoutSpec
from schematika.pcb.model import (
    Column,
    ConnectorBlock,
    ConnectorMap,
    FloatingPart,
    PinColumns,
    PlacedSlice,
    SymbolMap,
    SymbolMapping,
    SymbolSlice,
    Terminator,
)
from schematika.pcb.walk import pack_pages


def _block(ref: str, n_pins: int) -> ConnectorBlock:
    pin_columns = tuple(
        PinColumns(
            pin_id=str(i),
            columns=(Column(slices=(), terminator=Terminator.NC),),
        )
        for i in range(n_pins)
    )
    return ConnectorBlock(
        connector_ref=ref, functional_label=None, pin_columns=pin_columns
    )


# With LayoutSpec defaults: side_padding_mm=5, pin_spacing_mm=10, inter_block_gap_mm=20
# A 2-pin block width = 5 + 5 + 2*10 = 30mm
# Second block origin_x = 30 + 20 = 50mm
# available_width = 250 - 2*30 = 190mm


def test_placements_first_block_at_origin() -> None:
    """First block always starts at x=0."""
    b = _block("J1", 2)
    layout = LayoutSpec()
    _, pages = pack_pages((b,), (), page_size=(250.0, 297.0), layout=layout)
    assert len(pages) == 1
    assert pages[0].placements == (("J1", 0.0, 30.0),)


def test_placements_second_block_offset() -> None:
    """Second block origin_x = width_of_first + inter_block_gap."""
    b1 = _block("J1", 2)
    b2 = _block("J2", 2)
    layout = LayoutSpec()
    _, pages = pack_pages((b1, b2), (), page_size=(250.0, 297.0), layout=layout)
    # 2-pin block width = 5+5+2*10 = 30mm; gap = 20mm; second at 50mm
    assert len(pages) == 1
    assert pages[0].placements == (("J1", 0.0, 30.0), ("J2", 50.0, 30.0))


def test_overflow_onto_row2_same_page() -> None:
    """Blocks exceeding row-1 width with short chains move to row-2 on the same page."""
    # available_width = 250 - 2*30 = 190mm
    # A 10-pin block = 5+5+10*10 = 110mm each
    # Two blocks + gap: 110 + 20 + 110 = 240 > 190 → row-1 full.
    # NC blocks have 10mm chain depth << row1_chain_budget(108.5mm), so row-2 opens.
    b1 = _block("J1", 10)
    b2 = _block("J2", 10)
    layout = LayoutSpec()
    _, pages = pack_pages((b1, b2), (), page_size=(250.0, 297.0), layout=layout)
    assert len(pages) == 1
    assert pages[0].placements[0] == ("J1", 0.0, 30.0)
    assert pages[0].placements[1] == ("J2", 0.0, 168.5)


def test_single_block_wider_than_page_still_gets_its_own_page() -> None:
    """A single block too wide for the page does not error."""
    # available_width = 100 - 2*30 = 40mm
    # 10-pin block = 110mm > 40mm → still placed (no error)
    b = _block("J1", 10)
    layout = LayoutSpec()
    _, pages = pack_pages((b,), (), page_size=(100.0, 297.0), layout=layout)
    assert len(pages) == 1
    assert pages[0].placements == (("J1", 0.0, 30.0),)


def test_floating_parts_appended_to_last_page() -> None:
    """Floating parts are appended to the last connector page."""
    b = _block("J1", 2)
    fp = FloatingPart(part_ref="F1")
    layout = LayoutSpec()
    _, pages = pack_pages((b,), (fp,), page_size=(250.0, 297.0), layout=layout)
    assert len(pages) == 1
    assert pages[0].floating_part_refs == ("F1",)
    assert pages[0].placements == (("J1", 0.0, 30.0),)


def test_floating_parts_only_get_their_own_page() -> None:
    """With no blocks, floating parts go on a dedicated page."""
    fp = FloatingPart(part_ref="F1")
    layout = LayoutSpec()
    _, pages = pack_pages((), (fp,), page_size=(250.0, 297.0), layout=layout)
    assert len(pages) == 1
    assert pages[0].placements == ()
    assert pages[0].floating_part_refs == ("F1",)


def test_empty_returns_empty() -> None:
    layout = LayoutSpec()
    _, pages = pack_pages((), (), page_size=(250.0, 297.0), layout=layout)
    assert pages == ()


def test_pack_pages_two_row_when_chains_fit() -> None:
    """Short-chain connectors that overflow row-1 width drop into row-2 same page."""
    # Make 4 blocks each 16 pins wide => 5+5+16*10 = 170mm. Two fit per row:
    # 170 + 20 + 170 = 360 == available width. Third would overflow.
    # Page A3 (420, 297): available_width=360, row1_y=30, row2_y=148.5+20=168.5.
    # NC columns => chain depth = block_height = 10mm << row1_chain_budget=108.5.
    blocks = tuple(_block(f"J{i}", 16) for i in range(1, 5))
    layout = LayoutSpec()
    _, pages = pack_pages(blocks, (), page_size=(420.0, 297.0), layout=layout)
    assert len(pages) == 1, f"Expected 1 page, got {len(pages)}: {pages}"
    refs = [(p[0], p[2]) for p in pages[0].placements]
    # Row 1 should have J1, J2 at y=30; row 2 J3, J4 at y=168.5.
    assert refs == [("J1", 30.0), ("J2", 30.0), ("J3", 168.5), ("J4", 168.5)]


def test_pack_pages_single_row_when_chains_too_tall() -> None:
    """A row-1 connector with a tall chain prevents row-2; remaining blocks spill to page 2."""
    # 2 slices => chain_y(120) + 2*15 = 160mm depth > row1_chain_budget=108.5mm.
    # Build a block whose pin has a 2-slice column. Make it wide (33 pins) to fill row1.
    # 33 pins: 5+5+33*10 = 340mm. J2 (30mm): 340+20+30=390 > 360 → J2 doesn't fit row1.
    # Since tall.max_chain_height > budget, row2 stays closed → J2 goes to page 2.
    placed = (
        PlacedSlice(
            part_ref="K1",
            slice_index=0,
            symbol=None,  # ty: ignore[invalid-argument-type]
            pins=(),
        ),
        PlacedSlice(
            part_ref="K1",
            slice_index=1,
            symbol=None,  # ty: ignore[invalid-argument-type]
            pins=(),
        ),
    )
    col = Column(slices=placed, terminator=Terminator.NC)
    # Build tall block with 33 pins, each with the same 2-slice column.
    tall_pcs = tuple(PinColumns(pin_id=str(i), columns=(col,)) for i in range(33))
    tall = ConnectorBlock(
        connector_ref="J1", functional_label=None, pin_columns=tall_pcs
    )
    short = _block("J2", 2)
    layout = LayoutSpec()
    _, pages = pack_pages((tall, short), (), page_size=(420.0, 297.0), layout=layout)
    # tall chain 160mm > row1_chain_budget=108.5mm -> row 2 stays closed -> J2 on page 2.
    assert len(pages) == 2
    assert pages[0].placements[0][0] == "J1"
    assert pages[0].placements[0][2] == 30.0
    assert pages[1].placements == (("J2", 0.0, 30.0),)


def test_pack_pages_bottom_terminator_excludes_two_row() -> None:
    """A connector with PIN_AT_BOTTOM exceeds the row-1 chain budget; row-2 never opens."""
    # Make bot wide (33 pins) to fill row1 alone, ensuring J2 cannot also go to row1.
    # 33 pins: 5+5+33*10=340mm. J2 (30mm): 340+20+30=390 > 360 → J2 doesn't fit row1.
    # Since bot.max_chain_height >= 260 > row1_chain_budget=108.5, row2 stays closed.
    # J2 must then go to a new page (page 2).
    bot_col = Column(
        slices=(), terminator=Terminator.PIN_AT_BOTTOM, terminator_label="K1:1"
    )
    bot_pcs = tuple(PinColumns(pin_id=str(i), columns=(bot_col,)) for i in range(33))
    bot = ConnectorBlock(connector_ref="J1", functional_label=None, pin_columns=bot_pcs)
    short = _block("J2", 2)
    layout = LayoutSpec()  # bottom_terminator_y_mm=260
    _, pages = pack_pages((bot, short), (), page_size=(420.0, 297.0), layout=layout)
    # max_chain_height_mm of bot >= 260mm > row1_chain_budget=108.5mm.
    # Row 2 stays closed; J2 spills to its own page.
    assert len(pages) == 2
    assert pages[1].placements == (("J2", 0.0, 30.0),)


def test_layout_spec_row2_origin_offset_default() -> None:
    """row2_origin_y_offset_mm defaults to 20.0."""
    s = LayoutSpec()
    assert s.row2_origin_y_offset_mm == 20.0


# ---------------------------------------------------------------------------
# Inline floating-slice placement tests
# ---------------------------------------------------------------------------

# Shared symbol + template factories for inline-placement fixtures.

_conn_tmpl = type(
    "conn_inline", (), {"name": "conn_inline", "pins": [SimpleNamespace(num="1")]}
)()
_relay_tmpl = type(
    "relay_inline",
    (),
    {
        "name": "relay_inline",
        "pins": [
            SimpleNamespace(num="A1"),
            SimpleNamespace(num="A2"),
            SimpleNamespace(num="11"),
            SimpleNamespace(num="14"),
        ],
    },
)()


def _sym_factory(label: str = "") -> Symbol:
    return Symbol(
        elements=[],
        ports={
            "top": Port("top", Point(0, -2.5), Vector(0, -1)),
            "bottom": Port("bottom", Point(0, 2.5), Vector(0, 1)),
        },
        label=label or "slice",
    )


def _inline_mapping() -> SymbolMapping:
    return SymbolMapping(
        symbols=(
            SymbolMap(
                template=_relay_tmpl,
                slices=(
                    SymbolSlice(
                        symbol=_sym_factory, pin_map={"A1": "top", "A2": "bottom"}
                    ),
                    SymbolSlice(
                        symbol=_sym_factory, pin_map={"11": "top", "14": "bottom"}
                    ),
                ),
            ),
        ),
        connectors=(ConnectorMap(template=_conn_tmpl),),
        power_nets=(),
    )


def _two_connector_blocks() -> tuple[ConnectorBlock, ConnectorBlock]:
    """J1 and J4 as 1-pin connector blocks."""
    pc = PinColumns(pin_id="1", columns=(Column(slices=(), terminator=Terminator.NC),))
    j1 = ConnectorBlock(connector_ref="J1", functional_label=None, pin_columns=(pc,))
    j4 = ConnectorBlock(connector_ref="J4", functional_label=None, pin_columns=(pc,))
    return j1, j4


def test_pack_pages_anchors_floating_to_top_pin_net_connector() -> None:
    """A floating slice whose top-pin net contains J4's pin lands next to J4."""
    mapping = _inline_mapping()
    j1, j4 = _two_connector_blocks()
    blocks = (j1, j4)
    # K1 coil slice (index 0): top pin A1 on Q_PLS_DO_HS which has J4[1].
    ir = CircuitIR(
        parts=(
            PartRef(ref="J1", template_name="conn_inline", pin_numbers=("1",)),
            PartRef(ref="J4", template_name="conn_inline", pin_numbers=("1",)),
            PartRef(
                ref="K1",
                template_name="relay_inline",
                pin_numbers=("A1", "A2", "11", "14"),
            ),
        ),
        nets=(
            NetRef(name="/Q_PLS_DO_HS", pins=(PinRef("J4", "1"), PinRef("K1", "A1"))),
            NetRef(name="/coil_ret", pins=(PinRef("K1", "A2"),)),
            NetRef(name="/contact_in", pins=(PinRef("K1", "11"),)),
            NetRef(name="/contact_out", pins=(PinRef("K1", "14"),)),
        ),
    )
    # K1 coil is unowned; contact is owned by J1.
    ownership: dict[tuple[str, int], str] = {("K1", 1): "J1"}
    floating = (FloatingPart(part_ref="K1", slice_indices=(0,)),)

    _, pages = pack_pages(
        blocks,
        floating,
        page_size=(420.0, 297.0),
        layout=LayoutSpec(),
        ir=ir,
        mapping=mapping,
        slice_ownership=ownership,
    )
    j4_page = next(p for p in pages if any(ref == "J4" for ref, _, _ in p.placements))
    k1_placement = next(
        fp
        for fp in j4_page.floating_placements
        if fp.part_ref == "K1" and fp.slice_index == 0
    )
    j4_x = next(x for ref, x, _ in j4_page.placements if ref == "J4")
    assert k1_placement.x_mm > j4_x


def test_pack_pages_anchors_floating_to_sibling_owner_when_top_net_has_no_connector() -> (
    None
):
    """K3 no_13_14 (top pin on em_stop_chain — no connector pin) anchors to J1 (K3 coil owner)."""
    mapping = _inline_mapping()
    j1, j4 = _two_connector_blocks()
    blocks = (j1, j4)
    # K3: coil (A1,A2) owned by J1; contact (11,14) unowned. Top pin 11 on em_stop_chain (no J pin).
    ir = CircuitIR(
        parts=(
            PartRef(ref="J1", template_name="conn_inline", pin_numbers=("1",)),
            PartRef(ref="J4", template_name="conn_inline", pin_numbers=("1",)),
            PartRef(
                ref="K3",
                template_name="relay_inline",
                pin_numbers=("A1", "A2", "11", "14"),
            ),
        ),
        nets=(
            NetRef(name="/coil_drive", pins=(PinRef("J1", "1"), PinRef("K3", "A1"))),
            NetRef(name="/coil_ret", pins=(PinRef("K3", "A2"),)),
            NetRef(
                name="/em_stop_chain", pins=(PinRef("K3", "11"), PinRef("K3", "14"))
            ),
        ),
    )
    # K3 coil is owned by J1; K3 contact (slice 1) is unowned.
    ownership: dict[tuple[str, int], str] = {("K3", 0): "J1"}
    floating = (FloatingPart(part_ref="K3", slice_indices=(1,)),)

    _, pages = pack_pages(
        blocks,
        floating,
        page_size=(420.0, 297.0),
        layout=LayoutSpec(),
        ir=ir,
        mapping=mapping,
        slice_ownership=ownership,
    )
    j1_page = next(p for p in pages if any(ref == "J1" for ref, _, _ in p.placements))
    k3_placement = next(
        fp
        for fp in j1_page.floating_placements
        if fp.part_ref == "K3" and fp.slice_index == 1
    )
    j1_x = next(x for ref, x, _ in j1_page.placements if ref == "J1")
    assert k3_placement.x_mm > j1_x


def test_pack_pages_two_floats_at_same_anchor_sort_by_part_ref_then_index() -> None:
    """K1 coil (slice 0) and K2 coil (slice 0) both anchor to J4 → K1 first (lower x)."""
    _relay2_tmpl = type(
        "relay_inline2",
        (),
        {
            "name": "relay_inline2",
            "pins": [
                SimpleNamespace(num="A1"),
                SimpleNamespace(num="A2"),
                SimpleNamespace(num="11"),
                SimpleNamespace(num="14"),
            ],
        },
    )()
    mapping2 = SymbolMapping(
        symbols=(
            SymbolMap(
                template=_relay_tmpl,
                slices=(
                    SymbolSlice(
                        symbol=_sym_factory, pin_map={"A1": "top", "A2": "bottom"}
                    ),
                    SymbolSlice(
                        symbol=_sym_factory, pin_map={"11": "top", "14": "bottom"}
                    ),
                ),
            ),
            SymbolMap(
                template=_relay2_tmpl,
                slices=(
                    SymbolSlice(
                        symbol=_sym_factory, pin_map={"A1": "top", "A2": "bottom"}
                    ),
                    SymbolSlice(
                        symbol=_sym_factory, pin_map={"11": "top", "14": "bottom"}
                    ),
                ),
            ),
        ),
        connectors=(ConnectorMap(template=_conn_tmpl),),
        power_nets=(),
    )
    j4_pc = PinColumns(
        pin_id="1", columns=(Column(slices=(), terminator=Terminator.NC),)
    )
    j4 = ConnectorBlock(connector_ref="J4", functional_label=None, pin_columns=(j4_pc,))
    ir = CircuitIR(
        parts=(
            PartRef(ref="J4", template_name="conn_inline", pin_numbers=("1",)),
            PartRef(
                ref="K1",
                template_name="relay_inline",
                pin_numbers=("A1", "A2", "11", "14"),
            ),
            PartRef(
                ref="K2",
                template_name="relay_inline2",
                pin_numbers=("A1", "A2", "11", "14"),
            ),
        ),
        nets=(
            NetRef(
                name="/Q_PLS_DO_HS",
                pins=(PinRef("J4", "1"), PinRef("K1", "A1"), PinRef("K2", "A1")),
            ),
            NetRef(name="/k1_ret", pins=(PinRef("K1", "A2"),)),
            NetRef(name="/k2_ret", pins=(PinRef("K2", "A2"),)),
            NetRef(name="/k1_c", pins=(PinRef("K1", "11"),)),
            NetRef(name="/k1_d", pins=(PinRef("K1", "14"),)),
            NetRef(name="/k2_c", pins=(PinRef("K2", "11"),)),
            NetRef(name="/k2_d", pins=(PinRef("K2", "14"),)),
        ),
    )
    ownership: dict[tuple[str, int], str] = {}
    floating = (
        FloatingPart(part_ref="K1", slice_indices=(0,)),
        FloatingPart(part_ref="K2", slice_indices=(0,)),
    )

    _, pages = pack_pages(
        (j4,),
        floating,
        page_size=(420.0, 297.0),
        layout=LayoutSpec(),
        ir=ir,
        mapping=mapping2,
        slice_ownership=ownership,
    )
    j4_page = pages[0]
    j4_floats = sorted(
        [fp for fp in j4_page.floating_placements if fp.part_ref in {"K1", "K2"}],
        key=lambda fp: fp.x_mm,
    )
    assert [fp.part_ref for fp in j4_floats] == ["K1", "K2"]


def test_pack_pages_no_dedicated_floating_page_when_all_anchored() -> None:
    """If every floating slice resolves an anchor, no overflow page appears."""
    mapping = _inline_mapping()
    j1, j4 = _two_connector_blocks()
    blocks = (j1, j4)
    ir = CircuitIR(
        parts=(
            PartRef(ref="J1", template_name="conn_inline", pin_numbers=("1",)),
            PartRef(ref="J4", template_name="conn_inline", pin_numbers=("1",)),
            PartRef(
                ref="K1",
                template_name="relay_inline",
                pin_numbers=("A1", "A2", "11", "14"),
            ),
        ),
        nets=(
            NetRef(name="/Q_PLS_DO_HS", pins=(PinRef("J4", "1"), PinRef("K1", "A1"))),
            NetRef(name="/coil_ret", pins=(PinRef("K1", "A2"),)),
            NetRef(name="/contact_in", pins=(PinRef("K1", "11"),)),
            NetRef(name="/contact_out", pins=(PinRef("K1", "14"),)),
        ),
    )
    ownership: dict[tuple[str, int], str] = {("K1", 1): "J1"}
    floating = (FloatingPart(part_ref="K1", slice_indices=(0,)),)

    _, pages = pack_pages(
        blocks,
        floating,
        page_size=(420.0, 297.0),
        layout=LayoutSpec(),
        ir=ir,
        mapping=mapping,
        slice_ownership=ownership,
    )
    assert all("overflow" not in p.title.lower() for p in pages)
    # floating_part_refs stays empty (all slices anchored inline).
    for p in pages:
        assert p.floating_part_refs == ()
