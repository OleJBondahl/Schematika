"""
Tests for the P&ID diagram container, bounding box utility,
pipe routing, and placement resolution.
"""

import pytest

from schematika.core.bbox import BoundingBox, compute_bounding_box
from schematika.core.geometry import Point, Vector
from schematika.core.primitives import Circle, Line, Polygon, Text
from schematika.core.symbol import Port, Symbol
from schematika.pid.connections import (
    PROCESS_PIPE,
    SIGNAL_LINE,
    PipeStyle,
    create_flow_arrow,
    manhattan_route,
    render_pipe,
)
from schematika.pid.diagram import PIDDiagram, add_equipment, merge_diagrams
from schematika.pid.layout import Placement, resolve_placements

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_symbol(label: str | None = None, ports: dict | None = None) -> Symbol:
    """Minimal symbol with one line element centred at origin."""
    elems = [Line(start=Point(-5, 0), end=Point(5, 0))]
    p = ports or {"out": Port("out", Point(5, 0), Vector(1, 0))}
    return Symbol(elements=elems, ports=p, label=label)


# ---------------------------------------------------------------------------
# BoundingBox unit tests
# ---------------------------------------------------------------------------


class TestBoundingBox:
    def test_properties(self):
        bb = BoundingBox(min_x=10.0, max_x=30.0, min_y=5.0, max_y=25.0)
        assert bb.width == 20.0
        assert bb.height == 20.0
        assert bb.center == Point(20.0, 15.0)

    def test_zero_size(self):
        bb = BoundingBox(0.0, 0.0, 0.0, 0.0)
        assert bb.width == 0.0
        assert bb.height == 0.0

    def test_immutable(self):
        bb = BoundingBox(0.0, 10.0, 0.0, 10.0)
        with pytest.raises((AttributeError, TypeError)):
            bb.min_x = 5.0  # type: ignore[misc]


class TestComputeBoundingBox:
    def test_line(self):
        line = Line(start=Point(0, 0), end=Point(10, 5))
        bb = compute_bounding_box([line])
        assert bb.min_x == 0.0
        assert bb.max_x == 10.0
        assert bb.min_y == 0.0
        assert bb.max_y == 5.0

    def test_circle(self):
        circle = Circle(center=Point(10, 10), radius=5.0)
        bb = compute_bounding_box([circle])
        assert bb.min_x == 5.0
        assert bb.max_x == 15.0
        assert bb.min_y == 5.0
        assert bb.max_y == 15.0

    def test_polygon(self):
        poly = Polygon(points=[Point(0, 0), Point(10, 0), Point(5, 8)])
        bb = compute_bounding_box([poly])
        assert bb.min_x == 0.0
        assert bb.max_x == 10.0
        assert bb.min_y == 0.0
        assert bb.max_y == 8.0

    def test_text_uses_position(self):
        text = Text(content="hello", position=Point(3, 7))
        bb = compute_bounding_box([text])
        assert bb.min_x == 3.0
        assert bb.max_x == 3.0
        assert bb.min_y == 7.0
        assert bb.max_y == 7.0

    def test_empty_list_returns_zero(self):
        bb = compute_bounding_box([])
        assert bb == BoundingBox(0.0, 0.0, 0.0, 0.0)

    def test_symbol(self):
        sym = _make_symbol()
        bb = compute_bounding_box(sym)
        assert bb.min_x == -5.0
        assert bb.max_x == 5.0
        assert bb.min_y == 0.0
        assert bb.max_y == 0.0

    def test_multiple_elements(self):
        elems = [
            Line(start=Point(0, 0), end=Point(10, 0)),
            Circle(center=Point(15, 5), radius=3.0),
        ]
        bb = compute_bounding_box(elems)
        assert bb.min_x == 0.0
        assert bb.max_x == 18.0  # circle right edge: 15+3
        assert bb.min_y == 0.0  # line is at y=0, circle top is 5-3=2
        assert bb.max_y == 8.0  # circle bottom: 5+3


# ---------------------------------------------------------------------------
# PIDDiagram tests
# ---------------------------------------------------------------------------


class TestPIDDiagram:
    def test_empty_diagram(self):
        d = PIDDiagram()
        assert d.equipment == []
        assert d.elements == []

    def test_add_equipment_translates(self):
        sym = _make_symbol("P-101")
        d = PIDDiagram()
        placed = add_equipment(d, sym, x=50.0, y=100.0)
        # The line in the template goes from (-5,0) to (5,0).
        # After translation to (50, 100) it should be at (45,100)-(55,100).
        line = placed.elements[0]
        assert isinstance(line, Line)
        assert line.start == Point(45.0, 100.0)
        assert line.end == Point(55.0, 100.0)

    def test_add_equipment_appended_to_diagram(self):
        sym = _make_symbol()
        d = PIDDiagram()
        placed = add_equipment(d, sym, 0, 0)
        assert len(d.equipment) == 1
        assert len(d.elements) == 1
        assert d.equipment[0] is placed

    def test_get_equipment_by_tag_found(self):
        d = PIDDiagram()
        add_equipment(d, _make_symbol("P-101"), 0, 0)
        add_equipment(d, _make_symbol("T-201"), 0, 0)
        result = d.get_equipment_by_tag("T-201")
        assert result is not None
        assert result.label == "T-201"

    def test_get_equipment_by_tag_not_found(self):
        d = PIDDiagram()
        add_equipment(d, _make_symbol("P-101"), 0, 0)
        assert d.get_equipment_by_tag("X-999") is None

    def test_merge_diagrams(self):
        d1 = PIDDiagram()
        d2 = PIDDiagram()
        add_equipment(d1, _make_symbol("A"), 0, 0)
        add_equipment(d2, _make_symbol("B"), 10, 10)

        merge_diagrams(d1, d2)

        assert len(d1.equipment) == 2
        assert len(d1.elements) == 2
        # d2 unchanged
        assert len(d2.equipment) == 1

    def test_merge_does_not_modify_source(self):
        d1 = PIDDiagram()
        d2 = PIDDiagram()
        add_equipment(d2, _make_symbol("B"), 0, 0)
        original_len = len(d2.equipment)
        merge_diagrams(d1, d2)
        assert len(d2.equipment) == original_len


# ---------------------------------------------------------------------------
# Manhattan routing tests
# ---------------------------------------------------------------------------


class TestManhattanRoute:
    def test_same_point_returns_single(self):
        p = Point(5, 5)
        result = manhattan_route(p, p)
        assert result == [p]

    def test_same_x_straight_vertical(self):
        start = Point(10, 0)
        end = Point(10, 30)
        result = manhattan_route(start, end)
        assert result == [start, end]

    def test_same_y_straight_horizontal(self):
        start = Point(0, 20)
        end = Point(50, 20)
        result = manhattan_route(start, end)
        assert result == [start, end]

    def test_horizontal_first(self):
        start = Point(0, 0)
        end = Point(50, 30)
        result = manhattan_route(start, end, prefer="horizontal")
        assert len(result) == 3
        assert result[0] == start
        assert result[2] == end
        # Bend should share end.x and start.y
        assert result[1] == Point(50, 0)

    def test_vertical_first(self):
        start = Point(0, 0)
        end = Point(50, 30)
        result = manhattan_route(start, end, prefer="vertical")
        assert len(result) == 3
        assert result[0] == start
        assert result[2] == end
        # Bend should share start.x and end.y
        assert result[1] == Point(0, 30)

    def test_default_prefer_horizontal(self):
        result_default = manhattan_route(Point(0, 0), Point(10, 10))
        result_horiz = manhattan_route(Point(0, 0), Point(10, 10), prefer="horizontal")
        assert result_default == result_horiz


# ---------------------------------------------------------------------------
# render_pipe tests
# ---------------------------------------------------------------------------


class TestRenderPipe:
    def test_basic_two_points_produces_one_line(self):
        waypoints = [Point(0, 0), Point(50, 0)]
        elements = render_pipe(waypoints, PROCESS_PIPE)
        lines = [e for e in elements if isinstance(e, Line)]
        assert len(lines) == 1
        assert lines[0].start == Point(0, 0)
        assert lines[0].end == Point(50, 0)

    def test_three_point_path_produces_two_lines(self):
        waypoints = [Point(0, 0), Point(50, 0), Point(50, 30)]
        elements = render_pipe(waypoints, PROCESS_PIPE)
        lines = [e for e in elements if isinstance(e, Line)]
        assert len(lines) == 2

    def test_signal_line_style(self):
        waypoints = [Point(0, 0), Point(20, 0)]
        elements = render_pipe(waypoints, SIGNAL_LINE)
        lines = [e for e in elements if isinstance(e, Line)]
        assert lines[0].style.stroke_width == SIGNAL_LINE.stroke_width
        assert lines[0].style.stroke_dasharray == SIGNAL_LINE.dash_pattern

    def test_flow_arrow_created_when_enabled(self):
        style = PipeStyle(stroke_width=0.7, show_flow_arrow=True)
        waypoints = [Point(0, 0), Point(50, 0)]
        elements = render_pipe(waypoints, style)
        polygons = [e for e in elements if isinstance(e, Polygon)]
        assert len(polygons) == 1

    def test_no_flow_arrow_by_default(self):
        waypoints = [Point(0, 0), Point(50, 0)]
        elements = render_pipe(waypoints, PROCESS_PIPE)
        polygons = [e for e in elements if isinstance(e, Polygon)]
        assert len(polygons) == 0

    def test_label_produces_text_element(self):
        waypoints = [Point(0, 0), Point(50, 0)]
        elements = render_pipe(waypoints, PROCESS_PIPE, label='6"-CS-001')
        texts = [e for e in elements if isinstance(e, Text)]
        assert len(texts) == 1
        assert texts[0].content == '6"-CS-001'

    def test_no_label_no_text(self):
        waypoints = [Point(0, 0), Point(50, 0)]
        elements = render_pipe(waypoints, PROCESS_PIPE)
        texts = [e for e in elements if isinstance(e, Text)]
        assert len(texts) == 0

    def test_single_waypoint_returns_empty(self):
        elements = render_pipe([Point(0, 0)], PROCESS_PIPE)
        assert elements == []

    def test_empty_waypoints_returns_empty(self):
        elements = render_pipe([], PROCESS_PIPE)
        assert elements == []


# ---------------------------------------------------------------------------
# create_flow_arrow tests
# ---------------------------------------------------------------------------


class TestCreateFlowArrow:
    def test_right_arrow_is_polygon(self):
        arrow = create_flow_arrow(Point(10, 10), direction="right")
        assert isinstance(arrow, Polygon)

    def test_all_directions_work(self):
        for d in ("right", "left", "up", "down"):
            arrow = create_flow_arrow(Point(0, 0), direction=d)
            assert isinstance(arrow, Polygon)

    def test_invalid_direction_raises(self):
        with pytest.raises(ValueError, match="direction must be one of"):
            create_flow_arrow(Point(0, 0), direction="diagonal")

    def test_arrow_has_three_vertices(self):
        arrow = create_flow_arrow(Point(5, 5))
        assert isinstance(arrow, Polygon)
        assert len(arrow.points) == 3


# ---------------------------------------------------------------------------
# resolve_placements tests
# ---------------------------------------------------------------------------


def _sym_with_ports(*port_ids: str, label: str | None = None) -> Symbol:
    """Create a symbol with named ports at integer y-offsets for easy testing."""
    ports = {}
    for i, pid in enumerate(port_ids):
        ports[pid] = Port(pid, Point(0, float(i * 10)), Vector(0, 1))
    return Symbol(elements=[], ports=ports, label=label)


class TestResolvePlacements:
    def test_root_only(self):
        syms = {"root": _sym_with_ports("out")}
        placed = resolve_placements(syms, {}, "root", Point(10, 20))
        assert "root" in placed
        # Root port should be translated to (10, 20).
        assert placed["root"].ports["out"].position == Point(10, 20)

    def test_simple_chain(self):
        # root (port "out" at (0,0)) -> pump (port "in" at (0,0))
        syms = {
            "root": _sym_with_ports("out"),
            "pump": _sym_with_ports("in"),
        }
        placements = {
            "pump": Placement(anchor="root", anchor_port="out", my_port="in"),
        }
        placed = resolve_placements(syms, placements, "root", Point(0, 0))
        assert "pump" in placed
        # pump's "in" port should coincide with root's "out" port.
        assert (
            placed["pump"].ports["in"].position == placed["root"].ports["out"].position
        )

    def test_chain_with_offset(self):
        syms = {
            "root": _sym_with_ports("out"),
            "pump": _sym_with_ports("in"),
        }
        placements = {
            "pump": Placement(
                anchor="root",
                anchor_port="out",
                my_port="in",
                offset=Vector(20, 0),
            ),
        }
        placed = resolve_placements(syms, placements, "root", Point(0, 0))
        expected_x = placed["root"].ports["out"].position.x + 20
        assert placed["pump"].ports["in"].position.x == pytest.approx(expected_x)

    def test_branch(self):
        # root -> child_a and root -> child_b
        syms = {
            "root": _sym_with_ports("out_a", "out_b"),
            "child_a": _sym_with_ports("in"),
            "child_b": _sym_with_ports("in"),
        }
        placements = {
            "child_a": Placement(anchor="root", anchor_port="out_a", my_port="in"),
            "child_b": Placement(anchor="root", anchor_port="out_b", my_port="in"),
        }
        placed = resolve_placements(syms, placements, "root", Point(0, 0))
        assert "child_a" in placed
        assert "child_b" in placed

    def test_cycle_detection_self_reference(self):
        # A node whose anchor is itself → children["A"] = ["A"] → DFS detects cycle.
        syms = {
            "root": _sym_with_ports("out"),
            "A": _sym_with_ports("in", "out"),
        }
        placements = {
            "A": Placement(anchor="A", anchor_port="in", my_port="in"),
        }
        with pytest.raises(ValueError, match=r"[Cc]ycle"):
            resolve_placements(syms, placements, "root", Point(0, 0))

    def test_cycle_detection_mutual(self):
        # X.anchor=Y and Y.anchor=X → children["Y"]=["X"], children["X"]=["Y"]
        # → DFS detects a cycle (X→Y→X).
        syms = {
            "root": _sym_with_ports("out"),
            "X": _sym_with_ports("in", "out"),
            "Y": _sym_with_ports("in", "out"),
        }
        placements = {
            "X": Placement(anchor="Y", anchor_port="in", my_port="in"),
            "Y": Placement(anchor="X", anchor_port="out", my_port="in"),
        }
        with pytest.raises(ValueError, match=r"[Cc]ycle"):
            resolve_placements(syms, placements, "root", Point(0, 0))

    def test_missing_anchor_raises(self):
        syms = {
            "root": _sym_with_ports("out"),
            "pump": _sym_with_ports("in"),
        }
        placements = {
            "pump": Placement(anchor="nonexistent", anchor_port="out", my_port="in"),
        }
        with pytest.raises(ValueError, match="unknown anchor"):
            resolve_placements(syms, placements, "root", Point(0, 0))

    def test_missing_anchor_port_raises(self):
        syms = {
            "root": _sym_with_ports("out"),
            "pump": _sym_with_ports("in"),
        }
        placements = {
            "pump": Placement(anchor="root", anchor_port="no_such_port", my_port="in"),
        }
        with pytest.raises(ValueError, match=r"[Pp]ort.*not found"):
            resolve_placements(syms, placements, "root", Point(0, 0))

    def test_missing_my_port_raises(self):
        syms = {
            "root": _sym_with_ports("out"),
            "pump": _sym_with_ports("in"),
        }
        placements = {
            "pump": Placement(anchor="root", anchor_port="out", my_port="wrong_port"),
        }
        with pytest.raises(ValueError, match=r"[Pp]ort.*not found"):
            resolve_placements(syms, placements, "root", Point(0, 0))

    def test_missing_root_raises(self):
        syms = {"pump": _sym_with_ports("in")}
        with pytest.raises(ValueError, match="Root equipment"):
            resolve_placements(syms, {}, "root", Point(0, 0))
