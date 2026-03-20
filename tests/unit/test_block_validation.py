"""Tests for the block diagram layout validator (schematika.block.validation)."""

from schematika.block.constants import BLOCK_TEXT_SIZE_CABLE
from schematika.block.diagram import BlockDiagram
from schematika.block.validation import validate_block_diagram
from schematika.core import Line, Point, Port, Style, Symbol, Text, Vector


def _make_block(x: float, y: float, label: str = "BLK", size: float = 10.0) -> Symbol:
    """Create a simple test block (square) at position (x, y)."""
    half = size / 2
    style = Style(stroke="black", stroke_width=0.5, fill="none")
    elements = [
        Line(Point(x - half, y - half), Point(x + half, y - half), style),
        Line(Point(x + half, y - half), Point(x + half, y + half), style),
        Line(Point(x - half, y + half), Point(x + half, y + half), style),
        Line(Point(x - half, y - half), Point(x - half, y + half), style),
    ]
    ports = {"in": Port("in", Point(x - half, y), Vector(-1, 0))}
    return Symbol(elements, ports, label=label)


def _make_text(
    x: float,
    y: float,
    content: str = "Label",
    font_size: float = 3.0,
) -> Text:
    return Text(content, Point(x, y), font_size=font_size)


# ---------------------------------------------------------------------------
# Block overlap
# ---------------------------------------------------------------------------


def test_overlapping_blocks_error() -> None:
    diagram = BlockDiagram()
    diagram.blocks.append(_make_block(100, 100, "BLK1"))
    diagram.blocks.append(_make_block(100, 100, "BLK2"))
    diagram.elements.extend(diagram.blocks)
    result = validate_block_diagram(diagram)
    assert not result.passed
    assert any("overlap" in e.lower() for e in result.errors)


def test_non_overlapping_blocks_no_error() -> None:
    diagram = BlockDiagram()
    diagram.blocks.append(_make_block(50, 100, "BLK1"))
    diagram.blocks.append(_make_block(200, 100, "BLK2"))
    diagram.elements.extend(diagram.blocks)
    result = validate_block_diagram(diagram)
    overlap_errors = [e for e in result.errors if "overlap" in e.lower()]
    assert overlap_errors == []


# ---------------------------------------------------------------------------
# Page boundary
# ---------------------------------------------------------------------------


def test_block_outside_page_bounds_error() -> None:
    diagram = BlockDiagram()
    diagram.blocks.append(_make_block(-50, 100, "BLK-OUT"))
    diagram.elements.extend(diagram.blocks)
    result = validate_block_diagram(diagram)
    assert not result.passed
    assert any("boundary" in e.lower() for e in result.errors)


def test_block_inside_page_bounds_no_error() -> None:
    diagram = BlockDiagram()
    diagram.blocks.append(_make_block(100, 100, "BLK-IN"))
    diagram.elements.extend(diagram.blocks)
    result = validate_block_diagram(diagram)
    boundary_errors = [e for e in result.errors if "boundary" in e.lower()]
    assert boundary_errors == []


# ---------------------------------------------------------------------------
# Text overlap
# ---------------------------------------------------------------------------


def test_text_overlap_warning() -> None:
    diagram = BlockDiagram()
    diagram.elements.append(_make_text(100, 100, "Label A"))
    diagram.elements.append(_make_text(101, 100, "Label B"))
    result = validate_block_diagram(diagram)
    assert any("text overlap" in w.lower() for w in result.warnings)


# ---------------------------------------------------------------------------
# Minimum spacing
# ---------------------------------------------------------------------------


def test_blocks_too_close_warning() -> None:
    diagram = BlockDiagram()
    # Two 10mm blocks with gap smaller than BLOCK_MIN_GAP (20mm)
    # Block 1 spans x=[95,105], Block 2 spans x=[110,120] => gap = 5mm
    diagram.blocks.append(_make_block(100, 100, "BLK1"))
    diagram.blocks.append(_make_block(115, 100, "BLK2"))
    diagram.elements.extend(diagram.blocks)
    result = validate_block_diagram(diagram)
    assert any("spacing" in w.lower() for w in result.warnings)


# ---------------------------------------------------------------------------
# Cable label collision
# ---------------------------------------------------------------------------


def test_cable_label_collision_warning() -> None:
    diagram = BlockDiagram()
    diagram.elements.append(
        _make_text(100, 100, "W001", font_size=BLOCK_TEXT_SIZE_CABLE)
    )
    diagram.elements.append(
        _make_text(101, 101, "W002", font_size=BLOCK_TEXT_SIZE_CABLE)
    )
    result = validate_block_diagram(diagram)
    assert any("cable label" in w.lower() for w in result.warnings)


# ---------------------------------------------------------------------------
# Clean diagram
# ---------------------------------------------------------------------------


def test_clean_diagram_passes() -> None:
    diagram = BlockDiagram()
    # Place two blocks well inside bounds and far apart
    diagram.blocks.append(_make_block(100, 100, "BLK1"))
    diagram.blocks.append(_make_block(300, 100, "BLK2"))
    diagram.elements.extend(diagram.blocks)
    result = validate_block_diagram(diagram)
    assert result.passed
    assert result.errors == []


def test_empty_diagram_passes() -> None:
    diagram = BlockDiagram()
    result = validate_block_diagram(diagram)
    assert result.passed
    assert result.errors == []
    assert result.warnings == []
