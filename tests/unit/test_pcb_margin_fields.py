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
    """Blocks that fit with margin=0 spill to a second page with horizontal_margin_mm=30."""
    # A 9-pin block width = 2*5 + 9*10 = 100mm.
    # Two such blocks + gap: 100 + 20 + 100 = 220mm.
    # page_width = 250mm; usable with margin=0 → 250mm; both fit.
    # With horizontal_margin_mm=30 → usable = 250 - 60 = 190mm; 220 > 190 → spills.
    b1 = _block("J1", 9)
    b2 = _block("J2", 9)

    layout_zero = LayoutSpec(horizontal_margin_mm=0.0)
    pages_zero = pack_pages((b1, b2), (), page_size=(250.0, 297.0), layout=layout_zero)
    assert len(pages_zero) == 1, "Both blocks should fit with no margin"

    layout_30 = LayoutSpec(horizontal_margin_mm=30.0)
    pages_30 = pack_pages((b1, b2), (), page_size=(250.0, 297.0), layout=layout_30)
    assert len(pages_30) == 2, "Second block should spill to page 2 with 30mm margin"


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
