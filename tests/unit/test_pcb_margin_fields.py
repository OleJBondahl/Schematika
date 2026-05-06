"""Tests for horizontal_margin_mm and vertical_margin_mm on LayoutSpec."""

from schematika.pcb.layout_spec import LayoutSpec
from schematika.pcb.model import (
    Column,
    ConnectorBlock,
    PinColumns,
    Terminator,
)
from schematika.pcb.render import render_connector_block
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


def test_layout_spec_margin_defaults() -> None:
    """Both margin fields default to 30.0."""
    s = LayoutSpec()
    assert s.horizontal_margin_mm == 30.0
    assert s.vertical_margin_mm == 30.0


def test_pack_pages_respects_horizontal_margin() -> None:
    """Margin reduces available_width, causing row-1 to hold fewer blocks."""
    # A 9-pin block width = 2*5 + 9*10 = 100mm.
    # Two such blocks + gap: 100 + 20 + 100 = 220mm.
    # page_width = 250mm; usable with margin=0 → 250mm; both fit on row 1.
    # With horizontal_margin_mm=30 → usable = 250 - 60 = 190mm; 220 > 190 → row 1 full.
    # NC blocks (chain depth=10mm) qualify for row 2; J2 ends up in row 2, same page.
    b1 = _block("J1", 9)
    b2 = _block("J2", 9)

    layout_zero = LayoutSpec(horizontal_margin_mm=0.0)
    _, pages_zero = pack_pages(
        (b1, b2), (), page_size=(250.0, 297.0), layout=layout_zero
    )
    # Both fit on row 1.
    assert len(pages_zero) == 1, "Both blocks should fit with no margin"
    row1_refs = [r for r, _, y in pages_zero[0].placements if y == 30.0]
    assert row1_refs == ["J1", "J2"], "Both should be on row 1 with zero margin"

    layout_30 = LayoutSpec(horizontal_margin_mm=30.0)
    _, pages_30 = pack_pages((b1, b2), (), page_size=(250.0, 297.0), layout=layout_30)
    # Row 1 fits only J1; J2 goes to row 2 on the same page.
    assert len(pages_30) == 1, "With two-row packing J2 goes to row 2, not a new page"
    all_refs = [r for r, _, _ in pages_30[0].placements]
    assert all_refs == ["J1", "J2"], "Both blocks must appear on the single page"
    row1_only = [r for r, _, y in pages_30[0].placements if y == 30.0]
    assert row1_only == ["J1"], "Only J1 fits row 1 with 30mm margin"


def test_render_offsets_content_by_margins() -> None:
    """Anchor symbol is placed at (horizontal_margin_mm, vertical_margin_mm)."""
    h_margin = 25.0
    v_margin = 20.0
    layout = LayoutSpec(horizontal_margin_mm=h_margin, vertical_margin_mm=v_margin)

    # One-pin block, no slices — simplest possible render.
    block = _block("J1", 1)
    circuit = render_connector_block(
        block,
        origin_x_mm=h_margin,
        origin_y_mm=v_margin,
        layout=layout,
    )

    assert circuit.symbols, "Expected at least one placed symbol"
    anchor = circuit.symbols[0]

    # The connector-block symbol is placed at (h_margin, v_margin).
    # Its port positions in world space reflect the placement origin.
    # At minimum, some port should have world y >= v_margin (the box sits at v_margin).
    from schematika.core.primitives import Polygon

    box_ys: list[float] = []
    for el in anchor.elements:
        if isinstance(el, Polygon):
            box_ys.extend(pt.y for pt in el.points)

    # Connector-block box top edge (min y of the polygon) must be at v_margin.
    assert box_ys, "Expected polygon in anchor symbol"
    top_edge = min(box_ys)
    assert abs(top_edge - v_margin) < 0.1, (
        f"Connector box top edge {top_edge:.2f} != vertical_margin_mm {v_margin}"
    )

    # Also confirm leftmost point is at h_margin.
    box_xs = [
        pt.x for el in anchor.elements if isinstance(el, Polygon) for pt in el.points
    ]
    assert min(box_xs) >= h_margin - 0.1, (
        f"Leftmost box x {min(box_xs):.2f} < horizontal_margin_mm {h_margin}"
    )
