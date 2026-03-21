"""Tests for the block diagram layout validator (schematika.block.validation)."""

from schematika.block.diagram import BlockDiagram
from schematika.block.model import Block
from schematika.block.validation import (
    _block_bbox,
    _check_block_overlap,
    validate_block_diagram,
)
from schematika.core.validation import boxes_overlap, check_page_bounds

# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


def test_boxes_overlap_true() -> None:
    a = (0.0, 0.0, 10.0, 10.0)
    b = (5.0, 5.0, 15.0, 15.0)
    assert boxes_overlap(a, b)


def test_boxes_overlap_false() -> None:
    a = (0.0, 0.0, 10.0, 10.0)
    b = (20.0, 20.0, 30.0, 30.0)
    assert not boxes_overlap(a, b)


def test_block_bbox() -> None:
    b = Block(label="X", x=10.0, y=20.0, width=40.0, height=25.0)
    bbox = _block_bbox(b)
    assert bbox == (10.0, 20.0, 50.0, 45.0)


# ---------------------------------------------------------------------------
# Block overlap (using pre-positioned blocks)
# ---------------------------------------------------------------------------


def test_overlapping_blocks_error() -> None:
    a = Block(label="BLK1", x=100.0, y=100.0, width=40.0, height=25.0)
    b = Block(label="BLK2", x=100.0, y=100.0, width=40.0, height=25.0)
    errors = _check_block_overlap([a, b])
    assert any("overlap" in e.lower() for e in errors)


def test_non_overlapping_blocks_no_error() -> None:
    a = Block(label="BLK1", x=50.0, y=100.0, width=40.0, height=25.0)
    b = Block(label="BLK2", x=200.0, y=100.0, width=40.0, height=25.0)
    errors = _check_block_overlap([a, b])
    assert errors == []


# ---------------------------------------------------------------------------
# Page boundary
# ---------------------------------------------------------------------------


def test_block_outside_page_bounds_error() -> None:
    b = Block(label="BLK-OUT", x=-50.0, y=100.0, width=40.0, height=25.0)
    bbox = _block_bbox(b)
    errors = check_page_bounds([b], [bbox], 420.0, 297.0, 10.0)
    assert any("boundary" in e.lower() for e in errors)


def test_block_inside_page_bounds_no_error() -> None:
    b = Block(label="BLK-IN", x=100.0, y=100.0, width=40.0, height=25.0)
    bbox = _block_bbox(b)
    errors = check_page_bounds([b], [bbox], 420.0, 297.0, 10.0)
    assert errors == []


# ---------------------------------------------------------------------------
# Full validation via diagram
# ---------------------------------------------------------------------------


def test_clean_diagram_passes() -> None:
    d = BlockDiagram()
    d.block("BLK1")
    # Use a large page so the auto-placed block fits within bounds
    result = validate_block_diagram(d, page_width=500, page_height=500, margin=5)
    assert result.passed
    assert result.errors == []


def test_empty_diagram_passes() -> None:
    d = BlockDiagram()
    result = validate_block_diagram(d)
    assert result.passed
    assert result.errors == []
    assert result.warnings == []
