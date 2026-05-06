"""Tests for pack_pages with LayoutSpec and Page.placements."""

from schematika.pcb.layout_spec import LayoutSpec
from schematika.pcb.model import (
    Column,
    ConnectorBlock,
    FloatingPart,
    PinColumns,
    PlacedSlice,
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
