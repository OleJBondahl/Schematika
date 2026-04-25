"""Tests for the P&ID layout validator (schematika.pid.validation)."""

from schematika.core import Line, Point, Port, Style, Symbol, Text, Vector
from schematika.pid.constants import (
    PID_EQUIPMENT_STROKE,
    PID_LINE_WEIGHT,
    PID_SIGNAL_LINE_WEIGHT,
)
from schematika.pid.diagram import PIDDiagram
from schematika.pid.validation import validate_pid


def _make_symbol(x: float, y: float, label: str = "EQ") -> Symbol:
    """Create a simple test symbol (10mm square) at position (x, y)."""
    style = Style(stroke="black", stroke_width=PID_EQUIPMENT_STROKE, fill="none")
    elements = [
        Line(Point(x - 5, y - 5), Point(x + 5, y - 5), style),
        Line(Point(x + 5, y - 5), Point(x + 5, y + 5), style),
        Line(Point(x - 5, y + 5), Point(x + 5, y + 5), style),
        Line(Point(x - 5, y - 5), Point(x - 5, y + 5), style),
    ]
    ports = {"in": Port("in", Point(x - 5, y), Vector(-1, 0))}
    return Symbol(elements, ports, label=label)  # ty: ignore[invalid-argument-type]


def _make_line(
    x1: float, y1: float, x2: float, y2: float, stroke_width: float = PID_LINE_WEIGHT
) -> Line:
    style = Style(stroke="black", stroke_width=stroke_width)
    return Line(Point(x1, y1), Point(x2, y2), style)


def _make_text(x: float, y: float, content: str = "Label") -> Text:
    return Text(content, Point(x, y))


# ---------------------------------------------------------------------------
# Empty diagram
# ---------------------------------------------------------------------------


def test_empty_diagram_passes() -> None:
    diagram = PIDDiagram()
    result = validate_pid(diagram)
    assert result.passed
    assert result.errors == []
    assert result.warnings == []


# ---------------------------------------------------------------------------
# Equipment overlap
# ---------------------------------------------------------------------------


def test_no_overlap_passes() -> None:
    diagram = PIDDiagram()
    diagram.equipment.append(_make_symbol(50, 100, "EQ1"))
    diagram.equipment.append(_make_symbol(150, 100, "EQ2"))
    result = validate_pid(diagram)
    overlap_errors = [e for e in result.errors if "overlap" in e.lower()]
    assert overlap_errors == []


def test_equipment_overlap_detected() -> None:
    diagram = PIDDiagram()
    diagram.equipment.append(_make_symbol(100, 100, "EQ1"))
    diagram.equipment.append(_make_symbol(100, 100, "EQ2"))
    result = validate_pid(diagram)
    assert not result.passed
    assert any("overlap" in e.lower() for e in result.errors)


# ---------------------------------------------------------------------------
# Text overlap
# ---------------------------------------------------------------------------


def test_text_overlap_detected() -> None:
    diagram = PIDDiagram()
    # Two texts at almost identical positions — bounding boxes will overlap
    diagram.elements.append(_make_text(100, 100, "Label A"))
    diagram.elements.append(_make_text(101, 100, "Label B"))
    result = validate_pid(diagram)
    assert any("text overlap" in w.lower() for w in result.warnings)


# ---------------------------------------------------------------------------
# Page boundary
# ---------------------------------------------------------------------------


def test_page_boundary_violation() -> None:
    diagram = PIDDiagram()
    diagram.equipment.append(_make_symbol(-50, 100, "EQ-OUT"))
    result = validate_pid(diagram)
    assert not result.passed
    assert any("boundary" in e.lower() for e in result.errors)


def test_within_page_boundary_passes() -> None:
    diagram = PIDDiagram()
    diagram.equipment.append(_make_symbol(50, 50, "EQ-IN"))
    result = validate_pid(diagram)
    boundary_errors = [e for e in result.errors if "boundary" in e.lower()]
    assert boundary_errors == []


# ---------------------------------------------------------------------------
# Duplicate lines
# ---------------------------------------------------------------------------


def test_duplicate_lines_detected() -> None:
    diagram = PIDDiagram()
    line = _make_line(10, 10, 50, 10)
    diagram.elements.append(line)
    diagram.elements.append(line)
    result = validate_pid(diagram)
    assert any("duplicate" in w.lower() for w in result.warnings)


# ---------------------------------------------------------------------------
# Stroke weight consistency
# ---------------------------------------------------------------------------


def test_unexpected_stroke_weight() -> None:
    diagram = PIDDiagram()
    diagram.elements.append(_make_line(10, 10, 50, 10, stroke_width=1.5))
    result = validate_pid(diagram)
    assert any("stroke" in w.lower() for w in result.warnings)


def test_standard_stroke_weights_pass() -> None:
    diagram = PIDDiagram()
    diagram.elements.append(_make_line(10, 10, 50, 10, stroke_width=PID_LINE_WEIGHT))
    diagram.elements.append(
        _make_line(10, 30, 50, 30, stroke_width=PID_EQUIPMENT_STROKE)
    )
    diagram.elements.append(
        _make_line(10, 50, 50, 50, stroke_width=PID_SIGNAL_LINE_WEIGHT)
    )
    result = validate_pid(diagram)
    stroke_warnings = [w for w in result.warnings if "stroke" in w.lower()]
    assert stroke_warnings == []
