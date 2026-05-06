"""Tests for pack_pages with LayoutSpec and Page.placements."""

from schematika.pcb.layout_spec import LayoutSpec
from schematika.pcb.model import (
    Column,
    ConnectorBlock,
    FloatingPart,
    PinColumns,
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
    pages = pack_pages((b,), (), page_size=(250.0, 297.0), layout=layout)
    assert len(pages) == 1
    assert pages[0].placements == (("J1", 0.0),)


def test_placements_second_block_offset() -> None:
    """Second block origin_x = width_of_first + inter_block_gap."""
    b1 = _block("J1", 2)
    b2 = _block("J2", 2)
    layout = LayoutSpec()
    pages = pack_pages((b1, b2), (), page_size=(250.0, 297.0), layout=layout)
    # 2-pin block width = 5+5+2*10 = 30mm; gap = 20mm; second at 50mm
    assert len(pages) == 1
    assert pages[0].placements == (("J1", 0.0), ("J2", 50.0))


def test_overflow_onto_new_page() -> None:
    """Blocks exceeding available_width go to a new page."""
    # available_width = 250 - 2*30 = 190mm
    # A 10-pin block = 5+5+10*10 = 110mm each
    # Two blocks + gap: 110 + 20 + 110 = 240 > 190 → overflow
    b1 = _block("J1", 10)
    b2 = _block("J2", 10)
    layout = LayoutSpec()
    pages = pack_pages((b1, b2), (), page_size=(250.0, 297.0), layout=layout)
    assert len(pages) == 2
    assert pages[0].placements == (("J1", 0.0),)
    assert pages[1].placements == (("J2", 0.0),)


def test_single_block_wider_than_page_still_gets_its_own_page() -> None:
    """A single block too wide for the page does not error."""
    # available_width = 100 - 2*30 = 40mm
    # 10-pin block = 110mm > 40mm → still placed (no error)
    b = _block("J1", 10)
    layout = LayoutSpec()
    pages = pack_pages((b,), (), page_size=(100.0, 297.0), layout=layout)
    assert len(pages) == 1
    assert pages[0].placements == (("J1", 0.0),)


def test_floating_parts_appended_to_last_page() -> None:
    """Floating parts are appended to the last connector page."""
    b = _block("J1", 2)
    fp = FloatingPart(part_ref="F1")
    layout = LayoutSpec()
    pages = pack_pages((b,), (fp,), page_size=(250.0, 297.0), layout=layout)
    assert len(pages) == 1
    assert pages[0].floating_part_refs == ("F1",)
    assert pages[0].placements == (("J1", 0.0),)


def test_floating_parts_only_get_their_own_page() -> None:
    """With no blocks, floating parts go on a dedicated page."""
    fp = FloatingPart(part_ref="F1")
    layout = LayoutSpec()
    pages = pack_pages((), (fp,), page_size=(250.0, 297.0), layout=layout)
    assert len(pages) == 1
    assert pages[0].placements == ()
    assert pages[0].floating_part_refs == ("F1",)


def test_empty_returns_empty() -> None:
    layout = LayoutSpec()
    pages = pack_pages((), (), page_size=(250.0, 297.0), layout=layout)
    assert pages == ()
