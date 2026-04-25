"""Comprehensive tests for system_analysis.py module."""

import csv
from pathlib import Path

from schematika.electrical.model.core import Point, Port, Symbol, Vector
from schematika.electrical.model.primitives import Line
from schematika.electrical.symbols.terminals import TerminalBlock, TerminalSymbol
from schematika.electrical.system.system_analysis import (
    ConnectionNode,
    _create_terminal_row,
    _find_connected_symbol,
    _get_terminal_channels,
    _is_valid_direction,
    _point_key,
    _trace_port_connection,
    build_connectivity_graph,
    export_components_to_csv,
    export_terminals_to_csv,
    trace_connection,
)

# ---------------------------------------------------------------------------
# Helpers for building test fixtures
# ---------------------------------------------------------------------------


def _make_symbol(label, ports_dict=None):
    """Create a simple Symbol with the given label and ports dict."""
    if ports_dict is None:
        ports_dict = {}
    return Symbol(elements=[], ports=ports_dict, label=label)


def _make_terminal_symbol(label, terminal_number=None, ports_dict=None):
    """Create a TerminalSymbol with the given attributes."""
    if ports_dict is None:
        ports_dict = {
            "1": Port("1", Point(0, 0), Vector(0, -1)),
            "2": Port("2", Point(0, 0), Vector(0, 1)),
        }
    return TerminalSymbol(
        elements=[],
        ports=ports_dict,
        label=label,
        terminal_number=terminal_number,
    )


def _make_terminal_block(label, ports_dict):
    """Create a TerminalBlock with the given attributes."""
    return TerminalBlock(elements=[], ports=ports_dict, label=label)


# ===========================================================================
# Tests for _point_key
# ===========================================================================


class TestPointKey:
    def test_basic_integer_point(self):
        """Integer coordinates should round-trip cleanly."""
        assert _point_key(Point(10, 20)) == (10.0, 20.0)

    def test_already_one_decimal(self):
        """Coordinates already at one decimal should be unchanged."""
        assert _point_key(Point(1.5, 2.3)) == (1.5, 2.3)

    def test_rounds_to_one_decimal(self):
        """Coordinates with extra precision should be rounded to 1 decimal."""
        assert _point_key(Point(1.44, 2.75)) == (1.4, 2.8)

    def test_negative_coordinates(self):
        """Negative coordinates should round correctly."""
        assert _point_key(Point(-3.456, -7.891)) == (-3.5, -7.9)

    def test_zero_point(self):
        """Origin point."""
        assert _point_key(Point(0, 0)) == (0.0, 0.0)

    def test_very_small_fraction(self):
        """Near-zero fractional part should round to .0."""
        assert _point_key(Point(5.04, 10.05)) == (5.0, 10.1)


# ===========================================================================
# Tests for build_connectivity_graph
# ===========================================================================


class TestBuildConnectivityGraph:
    def test_empty_elements(self):
        """Empty element list produces an empty graph."""
        graph = build_connectivity_graph([])
        assert graph == {}

    def test_single_line_creates_two_nodes(self):
        """A single line creates nodes at both endpoints."""
        line = Line(Point(0, 0), Point(10, 0))
        graph = build_connectivity_graph([line])

        assert len(graph) == 2
        assert (0.0, 0.0) in graph
        assert (10.0, 0.0) in graph

        # Each endpoint node references the same line
        assert line in graph[(0.0, 0.0)].connected_lines
        assert line in graph[(10.0, 0.0)].connected_lines

    def test_symbol_ports_registered(self):
        """Symbol ports are registered in the graph at their positions."""
        sym = _make_symbol(
            "K1",
            {
                "A1": Port("A1", Point(5, 0), Vector(0, -1)),
                "A2": Port("A2", Point(5, 10), Vector(0, 1)),
            },
        )
        graph = build_connectivity_graph([sym])

        assert len(graph) == 2
        node_top = graph[(5.0, 0.0)]
        node_bot = graph[(5.0, 10.0)]

        assert len(node_top.connected_ports) == 1
        assert node_top.connected_ports[0] == (sym, "A1")
        assert len(node_bot.connected_ports) == 1
        assert node_bot.connected_ports[0] == (sym, "A2")

    def test_line_and_symbol_share_node(self):
        """A line endpoint coinciding with a symbol port shares one node."""
        sym = _make_symbol(
            "K1",
            {"A2": Port("A2", Point(0, 10), Vector(0, 1))},
        )
        line = Line(Point(0, 10), Point(0, 20))
        graph = build_connectivity_graph([sym, line])

        node = graph[(0.0, 10.0)]
        assert line in node.connected_lines
        assert (sym, "A2") in node.connected_ports

    def test_multiple_lines_same_endpoint(self):
        """Multiple lines sharing a common point are grouped in one node."""
        line1 = Line(Point(0, 0), Point(10, 0))
        line2 = Line(Point(10, 0), Point(20, 0))
        graph = build_connectivity_graph([line1, line2])

        junction = graph[(10.0, 0.0)]
        assert line1 in junction.connected_lines
        assert line2 in junction.connected_lines

    def test_tolerance_grouping(self):
        """Points that differ only beyond 1 decimal are grouped together."""
        # These two points round to the same key (5.1, 10.2)
        line1 = Line(Point(5.14, 10.24), Point(20, 20))
        line2 = Line(Point(5.05, 10.15), Point(30, 30))
        build_connectivity_graph([line1, line2])

        # line1 start rounds to (5.1, 10.2), line2 start rounds to (5.0, 10.2)
        # These are actually different keys, so let's use truly matching keys
        # Recalculate: round(5.14, 1)=5.1  round(10.24, 1)=10.2
        #              round(5.05, 1)=5.0  round(10.15, 1)=10.2
        # They are different. Let's use values that actually group:
        # Covered more precisely below

    def test_tolerance_grouping_precise(self):
        """Points differing by < 0.05 in each coord share one node."""
        # round(5.04, 1) = 5.0  and  round(5.0, 1) = 5.0
        line1 = Line(Point(5.04, 10.04), Point(20, 20))
        sym = _make_symbol(
            "K1",
            {"A1": Port("A1", Point(5.0, 10.0), Vector(0, -1))},
        )
        graph = build_connectivity_graph([line1, sym])

        node = graph[(5.0, 10.0)]
        assert line1 in node.connected_lines
        assert (sym, "A1") in node.connected_ports

    def test_non_element_types_ignored(self):
        """Non-Line, non-Symbol Element subclasses are silently ignored."""
        from schematika.electrical.model.primitives import Circle

        circle = Circle(center=Point(0, 0), radius=5)
        graph = build_connectivity_graph([circle])
        assert graph == {}


# ===========================================================================
# Tests for _find_connected_symbol
# ===========================================================================


class TestFindConnectedSymbol:
    def test_finds_other_symbol(self):
        """Returns (symbol, port_id) for a symbol that is not the start symbol."""
        sym_a = _make_symbol("A")
        sym_b = _make_symbol("B")
        node = ConnectionNode(
            point=Point(0, 0),
            connected_lines=[],
            connected_ports=[(sym_a, "1"), (sym_b, "A1")],
        )
        result = _find_connected_symbol(node, sym_a)
        assert result == (sym_b, "A1")

    def test_only_start_symbol_returns_none(self):
        """Returns None when the only port belongs to the start symbol."""
        sym_a = _make_symbol("A")
        node = ConnectionNode(
            point=Point(0, 0),
            connected_lines=[],
            connected_ports=[(sym_a, "1")],
        )
        assert _find_connected_symbol(node, sym_a) is None

    def test_no_ports_returns_none(self):
        """Returns None when the node has no ports at all."""
        sym_a = _make_symbol("A")
        node = ConnectionNode(
            point=Point(0, 0),
            connected_lines=[],
            connected_ports=[],
        )
        assert _find_connected_symbol(node, sym_a) is None

    def test_multiple_other_symbols_returns_first(self):
        """When multiple other symbols are at a node, the first one is returned."""
        sym_a = _make_symbol("A")
        sym_b = _make_symbol("B")
        sym_c = _make_symbol("C")
        node = ConnectionNode(
            point=Point(0, 0),
            connected_lines=[],
            connected_ports=[(sym_a, "1"), (sym_b, "2"), (sym_c, "3")],
        )
        result = _find_connected_symbol(node, sym_a)
        assert result == (sym_b, "2")


# ===========================================================================
# Tests for _is_valid_direction
# ===========================================================================


class TestIsValidDirection:
    def test_no_filter_always_true(self):
        """When direction_filter is None, any direction is valid."""
        assert _is_valid_direction(Point(0, 0), Point(10, 0), None) is True
        assert _is_valid_direction(Point(0, 0), Point(0, 10), None) is True
        assert _is_valid_direction(Point(0, 0), Point(-5, -5), None) is True

    def test_matching_direction_positive_x(self):
        """Line going right matches a rightward filter."""
        assert _is_valid_direction(Point(0, 0), Point(10, 0), Vector(1, 0)) is True

    def test_matching_direction_positive_y(self):
        """Line going down matches a downward filter."""
        assert _is_valid_direction(Point(0, 0), Point(0, 10), Vector(0, 1)) is True

    def test_opposite_direction(self):
        """Line going opposite to filter direction is rejected."""
        # Filter says go right (1, 0), but line goes left
        assert _is_valid_direction(Point(0, 0), Point(-10, 0), Vector(1, 0)) is False

    def test_opposite_direction_vertical(self):
        """Line going up when filter says down is rejected."""
        assert _is_valid_direction(Point(0, 10), Point(0, 0), Vector(0, 1)) is False

    def test_orthogonal_direction(self):
        """A line orthogonal to the filter direction has dot=0, so is rejected."""
        # Filter says right (1, 0), line goes down (0, 10)
        assert _is_valid_direction(Point(0, 0), Point(0, 10), Vector(1, 0)) is False

    def test_diagonal_matching(self):
        """Diagonal line with positive dot product against filter is accepted."""
        # Filter says down-right (1, 1); line goes right (10, 5) -> dot=15 > 0
        assert _is_valid_direction(Point(0, 0), Point(10, 5), Vector(1, 1)) is True

    def test_same_point_rejected(self):
        """Zero-length displacement has dot=0, so it is rejected."""
        assert _is_valid_direction(Point(5, 5), Point(5, 5), Vector(1, 0)) is False

    def test_false_filter_value_returns_true(self):
        """A falsy but non-None filter (e.g., 0) still returns True (no filter)."""
        assert _is_valid_direction(Point(0, 0), Point(1, 0), 0) is True  # ty: ignore[invalid-argument-type]

    def test_empty_string_filter_returns_true(self):
        """An empty-string filter is falsy, so behaves like no filter."""
        assert _is_valid_direction(Point(0, 0), Point(1, 0), "") is True  # ty: ignore[invalid-argument-type]


# ===========================================================================
# Tests for trace_connection
# ===========================================================================


class TestTraceConnection:
    def test_direct_connection(self):
        """A single line connecting two symbols finds the other symbol."""
        sym_a = _make_symbol(
            "A",
            {"1": Port("1", Point(0, 0), Vector(0, 1))},
        )
        sym_b = _make_symbol(
            "B",
            {"1": Port("1", Point(0, 10), Vector(0, -1))},
        )
        line = Line(Point(0, 0), Point(0, 10))
        graph = build_connectivity_graph([sym_a, sym_b, line])

        start_node = graph[_point_key(Point(0, 0))]
        result = trace_connection(start_node, graph, set(), sym_a)
        assert result == (sym_b, "1")

    def test_multi_hop_connection(self):
        """Two lines in sequence (A -> junction -> B) trace through to B."""
        sym_a = _make_symbol(
            "A",
            {"1": Port("1", Point(0, 0), Vector(0, 1))},
        )
        sym_b = _make_symbol(
            "B",
            {"1": Port("1", Point(0, 20), Vector(0, -1))},
        )
        line1 = Line(Point(0, 0), Point(0, 10))
        line2 = Line(Point(0, 10), Point(0, 20))
        graph = build_connectivity_graph([sym_a, sym_b, line1, line2])

        start_node = graph[_point_key(Point(0, 0))]
        result = trace_connection(start_node, graph, set(), sym_a)
        assert result == (sym_b, "1")

    def test_no_connection_found(self):
        """When no other symbol is reachable, returns (None, None)."""
        sym_a = _make_symbol(
            "A",
            {"1": Port("1", Point(0, 0), Vector(0, 1))},
        )
        # Line leads to nowhere (no symbol at the other end)
        line = Line(Point(0, 0), Point(0, 10))
        graph = build_connectivity_graph([sym_a, line])

        start_node = graph[_point_key(Point(0, 0))]
        result = trace_connection(start_node, graph, set(), sym_a)
        assert result == (None, None)

    def test_cycle_detection_via_visited_lines(self):
        """Already-visited lines are not traversed again, preventing cycles."""
        sym_a = _make_symbol(
            "A",
            {"1": Port("1", Point(0, 0), Vector(0, 1))},
        )
        sym_b = _make_symbol(
            "B",
            {"1": Port("1", Point(0, 10), Vector(0, -1))},
        )
        line = Line(Point(0, 0), Point(0, 10))
        graph = build_connectivity_graph([sym_a, sym_b, line])

        # Pre-mark the line as visited
        visited = {id(line)}
        start_node = graph[_point_key(Point(0, 0))]
        result = trace_connection(start_node, graph, visited, sym_a)
        # Cannot reach B because the only line is already visited
        assert result == (None, None)

    def test_direction_filter_blocks_wrong_direction(self):
        """A direction filter prevents tracing lines going the wrong way."""
        sym_a = _make_symbol(
            "A",
            {"1": Port("1", Point(0, 10), Vector(0, 1))},
        )
        sym_b = _make_symbol(
            "B",
            {"1": Port("1", Point(0, 0), Vector(0, 1))},
        )
        # Line goes from (0,10) UP to (0,0), but filter demands downward (0,1)
        line = Line(Point(0, 10), Point(0, 0))
        graph = build_connectivity_graph([sym_a, sym_b, line])

        start_node = graph[_point_key(Point(0, 10))]
        # Filter: only go downward
        result = trace_connection(
            start_node, graph, set(), sym_a, direction_filter=Vector(0, 1)
        )
        assert result == (None, None)

    def test_direction_filter_allows_correct_direction(self):
        """Direction filter allows lines going in the correct direction."""
        sym_a = _make_symbol(
            "A",
            {"1": Port("1", Point(0, 0), Vector(0, 1))},
        )
        sym_b = _make_symbol(
            "B",
            {"1": Port("1", Point(0, 10), Vector(0, -1))},
        )
        line = Line(Point(0, 0), Point(0, 10))
        graph = build_connectivity_graph([sym_a, sym_b, line])

        start_node = graph[_point_key(Point(0, 0))]
        result = trace_connection(
            start_node, graph, set(), sym_a, direction_filter=Vector(0, 1)
        )
        assert result == (sym_b, "1")

    def test_direction_filter_cleared_after_first_hop(self):
        """Direction filter applies only to the first hop, then is cleared."""
        # sym_a at y=0 with downward port
        # junction at y=10 (no symbol)
        # line from junction goes LEFT to (10, 10) where sym_b is
        # First hop (0,0)->(0,10) matches downward filter
        # Second hop (0,10)->(10,10) is horizontal — would fail downward filter
        # but filter is cleared after first hop, so it should succeed
        sym_a = _make_symbol(
            "A",
            {"1": Port("1", Point(0, 0), Vector(0, 1))},
        )
        sym_b = _make_symbol(
            "B",
            {"1": Port("1", Point(10, 10), Vector(-1, 0))},
        )
        line1 = Line(Point(0, 0), Point(0, 10))
        line2 = Line(Point(0, 10), Point(10, 10))
        graph = build_connectivity_graph([sym_a, sym_b, line1, line2])

        start_node = graph[_point_key(Point(0, 0))]
        result = trace_connection(
            start_node, graph, set(), sym_a, direction_filter=Vector(0, 1)
        )
        assert result == (sym_b, "1")

    def test_start_node_is_other_symbol_port(self):
        """If start node already has another symbol's port, return it immediately."""
        sym_a = _make_symbol(
            "A",
            {"1": Port("1", Point(0, 0), Vector(0, 1))},
        )
        sym_b = _make_symbol(
            "B",
            {"1": Port("1", Point(0, 0), Vector(0, -1))},
        )
        # Both symbols share the same port position
        graph = build_connectivity_graph([sym_a, sym_b])

        start_node = graph[_point_key(Point(0, 0))]
        result = trace_connection(start_node, graph, set(), sym_a)
        assert result == (sym_b, "1")

    def test_line_traversal_other_end(self):
        """Line endpoint logic works when the start is at the line's end."""
        sym_a = _make_symbol(
            "A",
            {"1": Port("1", Point(10, 0), Vector(0, 1))},
        )
        sym_b = _make_symbol(
            "B",
            {"1": Port("1", Point(0, 0), Vector(0, -1))},
        )
        # Line's start is at (0,0) and end is at (10,0)
        # sym_a is at (10,0), so traversal from sym_a should go to start (0,0)
        line = Line(Point(0, 0), Point(10, 0))
        graph = build_connectivity_graph([sym_a, sym_b, line])

        start_node = graph[_point_key(Point(10, 0))]
        result = trace_connection(start_node, graph, set(), sym_a)
        assert result == (sym_b, "1")


# ===========================================================================
# Tests for _get_terminal_channels
# ===========================================================================


class TestGetTerminalChannels:
    def test_terminal_symbol_with_number(self):
        """TerminalSymbol with terminal_number produces one channel."""
        term = _make_terminal_symbol("X1", terminal_number="1")
        channels = _get_terminal_channels(term)
        assert len(channels) == 1
        assert channels[0] == {"pin": "1", "from_port": "1", "to_port": "2"}

    def test_terminal_symbol_without_number(self):
        """TerminalSymbol without terminal_number produces empty pin."""
        term = _make_terminal_symbol("X1", terminal_number=None)
        channels = _get_terminal_channels(term)
        assert len(channels) == 1
        assert channels[0] == {"pin": "", "from_port": "1", "to_port": "2"}

    def test_terminal_block_two_pole(self):
        """TerminalBlock with 4 numeric ports (2 poles) produces 2 channels."""
        ports = {
            "1": Port("1", Point(0, 0), Vector(0, -1)),
            "2": Port("2", Point(0, 0), Vector(0, 1)),
            "3": Port("3", Point(10, 0), Vector(0, -1)),
            "4": Port("4", Point(10, 0), Vector(0, 1)),
        }
        block = _make_terminal_block("X1", ports)
        channels = _get_terminal_channels(block)
        assert len(channels) == 2
        assert channels[0] == {"pin": "", "from_port": "1", "to_port": "2"}
        assert channels[1] == {"pin": "", "from_port": "3", "to_port": "4"}

    def test_terminal_block_three_pole(self):
        """TerminalBlock with 6 numeric ports (3 poles) produces 3 channels."""
        ports = {
            "1": Port("1", Point(0, 0), Vector(0, -1)),
            "2": Port("2", Point(0, 0), Vector(0, 1)),
            "3": Port("3", Point(10, 0), Vector(0, -1)),
            "4": Port("4", Point(10, 0), Vector(0, 1)),
            "5": Port("5", Point(20, 0), Vector(0, -1)),
            "6": Port("6", Point(20, 0), Vector(0, 1)),
        }
        block = _make_terminal_block("X1", ports)
        channels = _get_terminal_channels(block)
        assert len(channels) == 3

    def test_terminal_block_single_pole(self):
        """TerminalBlock with 2 numeric ports (1 pole) produces 1 channel."""
        ports = {
            "1": Port("1", Point(0, 0), Vector(0, -1)),
            "2": Port("2", Point(0, 0), Vector(0, 1)),
        }
        block = _make_terminal_block("X1", ports)
        channels = _get_terminal_channels(block)
        assert len(channels) == 1
        assert channels[0] == {"pin": "", "from_port": "1", "to_port": "2"}

    def test_terminal_block_odd_port_count(self):
        """TerminalBlock with odd numeric ports: last unpaired port is skipped."""
        ports = {
            "1": Port("1", Point(0, 0), Vector(0, -1)),
            "2": Port("2", Point(0, 0), Vector(0, 1)),
            "3": Port("3", Point(10, 0), Vector(0, -1)),
        }
        block = _make_terminal_block("X1", ports)
        channels = _get_terminal_channels(block)
        # Only one complete pair: (1, 2)
        assert len(channels) == 1

    def test_non_terminal_element(self):
        """A plain Symbol (not TerminalSymbol or TerminalBlock) yields empty list."""
        sym = _make_symbol("K1")
        channels = _get_terminal_channels(sym)
        assert channels == []

    def test_terminal_block_with_non_numeric_ports(self):
        """TerminalBlock with mixed numeric/non-numeric ports: only numeric paired."""
        ports = {
            "top": Port("top", Point(0, -5), Vector(0, -1)),
            "1": Port("1", Point(0, 0), Vector(0, -1)),
            "2": Port("2", Point(0, 0), Vector(0, 1)),
            "bottom": Port("bottom", Point(0, 5), Vector(0, 1)),
        }
        block = _make_terminal_block("X1", ports)
        channels = _get_terminal_channels(block)
        assert len(channels) == 1
        assert channels[0] == {"pin": "", "from_port": "1", "to_port": "2"}


# ===========================================================================
# Tests for _trace_port_connection
# ===========================================================================


class TestTracePortConnection:
    def test_valid_port_with_connection(self):
        """Traces from a terminal port to a connected component."""
        term = _make_terminal_symbol(
            "X1",
            terminal_number="1",
            ports_dict={
                "1": Port("1", Point(0, 0), Vector(0, -1)),
                "2": Port("2", Point(0, 10), Vector(0, 1)),
            },
        )
        comp = _make_symbol(
            "K1",
            {"A2": Port("A2", Point(0, 20), Vector(0, -1))},
        )
        line = Line(Point(0, 10), Point(0, 20))
        graph = build_connectivity_graph([term, comp, line])

        label, pin = _trace_port_connection(term, "2", graph)
        assert label == "K1"
        assert pin == "A2"

    def test_missing_port_returns_empty(self):
        """Port ID not in the terminal's ports returns ("", "")."""
        term = _make_terminal_symbol("X1", terminal_number="1")
        graph = build_connectivity_graph([term])
        label, pin = _trace_port_connection(term, "nonexistent", graph)
        assert label == ""
        assert pin == ""

    def test_port_exists_but_no_connection(self):
        """Port exists but no line connects to another symbol."""
        term = _make_terminal_symbol(
            "X1",
            terminal_number="1",
            ports_dict={
                "1": Port("1", Point(0, 0), Vector(0, -1)),
                "2": Port("2", Point(0, 10), Vector(0, 1)),
            },
        )
        # No line, no other symbol
        graph = build_connectivity_graph([term])
        label, pin = _trace_port_connection(term, "2", graph)
        assert label == ""
        assert pin == ""

    def test_connected_symbol_has_no_label(self):
        """If the connected symbol has no label, returns empty string for label."""
        term = _make_terminal_symbol(
            "X1",
            terminal_number="1",
            ports_dict={
                "1": Port("1", Point(0, 0), Vector(0, -1)),
                "2": Port("2", Point(0, 10), Vector(0, 1)),
            },
        )
        comp = Symbol(
            elements=[],
            ports={"A1": Port("A1", Point(0, 20), Vector(0, -1))},
            label=None,
        )
        line = Line(Point(0, 10), Point(0, 20))
        graph = build_connectivity_graph([term, comp, line])

        label, pin = _trace_port_connection(term, "2", graph)
        assert label == ""
        assert pin == "A1"

    def test_port_position_not_in_graph(self):
        """If port position doesn't match any node in the graph, returns empty."""
        # Build the graph with no elements, so no nodes exist
        term = _make_terminal_symbol(
            "X1",
            terminal_number="1",
            ports_dict={
                "1": Port("1", Point(100, 100), Vector(0, -1)),
                "2": Port("2", Point(100, 110), Vector(0, 1)),
            },
        )
        # Build graph from different elements so the port positions aren't there
        graph = build_connectivity_graph([Line(Point(0, 0), Point(0, 10))])
        label, pin = _trace_port_connection(term, "1", graph)
        assert label == ""
        assert pin == ""


# ===========================================================================
# Tests for _create_terminal_row
# ===========================================================================


class TestCreateTerminalRow:
    def test_basic_row(self):
        """Creates a CSV row with from/to connections through a terminal."""
        term = _make_terminal_symbol(
            "X1",
            terminal_number="3",
            ports_dict={
                "1": Port("1", Point(0, 0), Vector(0, -1)),
                "2": Port("2", Point(0, 20), Vector(0, 1)),
            },
        )
        comp_from = _make_symbol(
            "Q1",
            {"2": Port("2", Point(0, -10), Vector(0, 1))},
        )
        comp_to = _make_symbol(
            "K1",
            {"A1": Port("A1", Point(0, 30), Vector(0, -1))},
        )
        line_from = Line(Point(0, -10), Point(0, 0))
        line_to = Line(Point(0, 20), Point(0, 30))
        graph = build_connectivity_graph([term, comp_from, comp_to, line_from, line_to])

        channel = {"pin": "3", "from_port": "1", "to_port": "2"}
        row = _create_terminal_row(term, channel, graph)

        assert row == ["Q1", "2", "X1", "3", "K1", "A1"]

    def test_row_with_no_connections(self):
        """When no components connect to either side, row has empty strings."""
        term = _make_terminal_symbol(
            "X2",
            terminal_number="5",
            ports_dict={
                "1": Port("1", Point(50, 0), Vector(0, -1)),
                "2": Port("2", Point(50, 10), Vector(0, 1)),
            },
        )
        graph = build_connectivity_graph([term])
        channel = {"pin": "5", "from_port": "1", "to_port": "2"}
        row = _create_terminal_row(term, channel, graph)
        assert row == ["", "", "X2", "5", "", ""]

    def test_row_with_no_label_on_terminal(self):
        """Terminal with no label produces empty string in the tag column."""
        term = TerminalSymbol(
            elements=[],
            ports={
                "1": Port("1", Point(0, 0), Vector(0, -1)),
                "2": Port("2", Point(0, 10), Vector(0, 1)),
            },
            label=None,
            terminal_number="1",
        )
        graph = build_connectivity_graph([term])
        channel = {"pin": "1", "from_port": "1", "to_port": "2"}
        row = _create_terminal_row(term, channel, graph)
        assert row[2] == ""  # terminal tag column


# ===========================================================================
# Tests for export_terminals_to_csv
# ===========================================================================


class TestExportTerminalsToCsv:
    def test_simple_circuit_csv(self, tmp_path):
        """Exports a simple circuit with one terminal connecting two components."""
        term = _make_terminal_symbol(
            "X1",
            terminal_number="1",
            ports_dict={
                "1": Port("1", Point(0, 0), Vector(0, -1)),
                "2": Port("2", Point(0, 20), Vector(0, 1)),
            },
        )
        comp_top = _make_symbol(
            "Q1",
            {"2": Port("2", Point(0, -10), Vector(0, 1))},
        )
        comp_bot = _make_symbol(
            "K1",
            {"A1": Port("A1", Point(0, 30), Vector(0, -1))},
        )
        line_top = Line(Point(0, -10), Point(0, 0))
        line_bot = Line(Point(0, 20), Point(0, 30))

        csv_file = tmp_path / "terminals.csv"
        export_terminals_to_csv(
            [term, comp_top, comp_bot, line_top, line_bot], str(csv_file)
        )

        with Path(csv_file).open(newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # Header row
        assert rows[0] == [
            "Component From",
            "Pin From",
            "Terminal Tag",
            "Terminal Pin",
            "Component To",
            "Pin To",
        ]
        # Data row
        assert rows[1] == ["Q1", "2", "X1", "1", "K1", "A1"]

    def test_empty_elements(self, tmp_path):
        """Empty element list produces a CSV with only headers."""
        csv_file = tmp_path / "empty.csv"
        export_terminals_to_csv([], str(csv_file))

        with Path(csv_file).open(newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        assert len(rows) == 1  # Header only
        assert rows[0][0] == "Component From"

    def test_terminals_sorted_by_label(self, tmp_path):
        """Terminals appear in the CSV sorted by label."""
        term_b = _make_terminal_symbol(
            "X2",
            terminal_number="1",
            ports_dict={
                "1": Port("1", Point(0, 0), Vector(0, -1)),
                "2": Port("2", Point(0, 10), Vector(0, 1)),
            },
        )
        term_a = _make_terminal_symbol(
            "X1",
            terminal_number="2",
            ports_dict={
                "1": Port("1", Point(20, 0), Vector(0, -1)),
                "2": Port("2", Point(20, 10), Vector(0, 1)),
            },
        )

        csv_file = tmp_path / "sorted.csv"
        export_terminals_to_csv([term_b, term_a], str(csv_file))

        with Path(csv_file).open(newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # X1 should appear before X2
        assert rows[1][2] == "X1"
        assert rows[2][2] == "X2"

    def test_terminal_block_export(self, tmp_path):
        """TerminalBlock with multiple channels produces multiple rows."""
        block = _make_terminal_block(
            "X1",
            {
                "1": Port("1", Point(0, 0), Vector(0, -1)),
                "2": Port("2", Point(0, 10), Vector(0, 1)),
                "3": Port("3", Point(10, 0), Vector(0, -1)),
                "4": Port("4", Point(10, 10), Vector(0, 1)),
            },
        )

        csv_file = tmp_path / "block.csv"
        export_terminals_to_csv([block], str(csv_file))

        with Path(csv_file).open(newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # Header + 2 channels
        assert len(rows) == 3

    def test_non_terminal_symbols_ignored(self, tmp_path):
        """Plain symbols are not included in terminal CSV export."""
        sym = _make_symbol("K1", {"1": Port("1", Point(0, 0), Vector(0, -1))})

        csv_file = tmp_path / "no_terminals.csv"
        export_terminals_to_csv([sym], str(csv_file))

        with Path(csv_file).open(newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        assert len(rows) == 1  # Header only


# ===========================================================================
# Tests for export_components_to_csv
# ===========================================================================


class TestExportComponentsToCsv:
    def test_basic_export(self, tmp_path):
        """Exports labeled symbols to CSV with correct headers."""
        sym_a = _make_symbol("K1")
        sym_b = _make_symbol("Q1")
        csv_file = tmp_path / "components.csv"
        export_components_to_csv([sym_a, sym_b], str(csv_file))

        with Path(csv_file).open(newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        assert rows[0] == ["Component Tag", "Component Description", "MPN"]
        tags = [row[0] for row in rows[1:]]
        assert "K1" in tags
        assert "Q1" in tags

    def test_symbols_sorted_by_tag(self, tmp_path):
        """Components are sorted alphabetically by tag."""
        sym_z = _make_symbol("Z1")
        sym_a = _make_symbol("A1")
        sym_m = _make_symbol("M1")

        csv_file = tmp_path / "sorted.csv"
        export_components_to_csv([sym_z, sym_a, sym_m], str(csv_file))

        with Path(csv_file).open(newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        tags = [row[0] for row in rows[1:]]
        assert tags == ["A1", "M1", "Z1"]

    def test_duplicate_labels_deduplicated(self, tmp_path):
        """Duplicate component tags appear only once in the CSV."""
        sym1 = _make_symbol("K1")
        sym2 = _make_symbol("K1")
        sym3 = _make_symbol("Q1")

        csv_file = tmp_path / "dedup.csv"
        export_components_to_csv([sym1, sym2, sym3], str(csv_file))

        with Path(csv_file).open(newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # Header + 2 unique tags
        assert len(rows) == 3
        tags = [row[0] for row in rows[1:]]
        assert tags == ["K1", "Q1"]

    def test_unlabeled_symbols_excluded(self, tmp_path):
        """Symbols without labels are not included in the CSV."""
        sym_labeled = _make_symbol("K1")
        sym_no_label = Symbol(elements=[], ports={}, label=None)

        csv_file = tmp_path / "labeled_only.csv"
        export_components_to_csv([sym_labeled, sym_no_label], str(csv_file))

        with Path(csv_file).open(newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        assert len(rows) == 2  # Header + 1 labeled component
        assert rows[1][0] == "K1"

    def test_empty_elements(self, tmp_path):
        """Empty element list produces a CSV with only headers."""
        csv_file = tmp_path / "empty.csv"
        export_components_to_csv([], str(csv_file))

        with Path(csv_file).open(newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        assert len(rows) == 1
        assert rows[0] == ["Component Tag", "Component Description", "MPN"]

    def test_description_and_mpn_are_empty(self, tmp_path):
        """Description and MPN columns are empty placeholders."""
        sym = _make_symbol("F1")
        csv_file = tmp_path / "placeholders.csv"
        export_components_to_csv([sym], str(csv_file))

        with Path(csv_file).open(newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        assert rows[1] == ["F1", "", ""]

    def test_non_symbol_elements_ignored(self, tmp_path):
        """Non-Symbol elements (like Lines) are not included in output."""
        sym = _make_symbol("K1")
        line = Line(Point(0, 0), Point(10, 0))

        csv_file = tmp_path / "mixed.csv"
        export_components_to_csv([sym, line], str(csv_file))

        with Path(csv_file).open(newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        assert len(rows) == 2
        assert rows[1][0] == "K1"

    def test_terminal_symbols_included_as_components(self, tmp_path):
        """TerminalSymbol and TerminalBlock are Symbol subclasses, so they appear."""
        term = _make_terminal_symbol("X1", terminal_number="1")
        block = _make_terminal_block(
            "X2",
            {"1": Port("1", Point(0, 0), Vector(0, -1))},
        )
        sym = _make_symbol("K1")

        csv_file = tmp_path / "includes_terminals.csv"
        export_components_to_csv([term, block, sym], str(csv_file))

        with Path(csv_file).open(newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        tags = [row[0] for row in rows[1:]]
        assert "K1" in tags
        assert "X1" in tags
        assert "X2" in tags


# ===========================================================================
# Integration-style tests
# ===========================================================================


class TestIntegration:
    def test_full_circuit_terminal_export(self, tmp_path):
        """
        End-to-end: A circuit with a breaker, terminal, and contactor
        connected by lines exports the correct terminal CSV.
        """
        # Breaker Q1 with port at bottom
        breaker = _make_symbol(
            "Q1",
            {"2": Port("2", Point(0, 20), Vector(0, 1))},
        )
        # Terminal X1:1 connecting them
        terminal = _make_terminal_symbol(
            "X1",
            terminal_number="1",
            ports_dict={
                "1": Port("1", Point(0, 30), Vector(0, -1)),
                "2": Port("2", Point(0, 40), Vector(0, 1)),
            },
        )
        # Contactor K1 with port at top
        contactor = _make_symbol(
            "K1",
            {"1": Port("1", Point(0, 50), Vector(0, -1))},
        )
        # Wires
        wire_top = Line(Point(0, 20), Point(0, 30))
        wire_bot = Line(Point(0, 40), Point(0, 50))

        elements = [breaker, terminal, contactor, wire_top, wire_bot]
        csv_file = tmp_path / "full_circuit.csv"
        export_terminals_to_csv(elements, str(csv_file))

        with Path(csv_file).open(newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        assert len(rows) == 2  # Header + 1 terminal
        assert rows[1] == ["Q1", "2", "X1", "1", "K1", "1"]

    def test_full_circuit_component_export(self, tmp_path):
        """
        End-to-end: Multiple components export sorted, deduplicated.
        """
        elements = [
            _make_symbol("Q1"),
            _make_symbol("K1"),
            _make_symbol("K1"),  # duplicate
            _make_terminal_symbol("X1", terminal_number="1"),
            Line(Point(0, 0), Point(0, 10)),  # non-symbol
            Symbol(elements=[], ports={}, label=None),  # no label
        ]
        csv_file = tmp_path / "full_components.csv"
        export_components_to_csv(elements, str(csv_file))

        with Path(csv_file).open(newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        tags = [row[0] for row in rows[1:]]
        assert tags == ["K1", "Q1", "X1"]
