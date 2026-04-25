# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------
from _factories import make_symbol as _canonical_make_symbol
from _factories import port as _port

from schematika.electrical.layout.layout import (
    _find_matching_ports,
    _get_wire_label_spec,
    create_horizontal_layout,
    draw_wire,
    draw_wire_labeled,
    get_connection_ports,
    layout_horizontal,
    layout_vertical_chain,
)
from schematika.electrical.model.core import Point, Port, Symbol, Vector
from schematika.electrical.model.primitives import Line, Text


def _make_symbol(ports: dict[str, Port], label: str | None = None) -> Symbol:
    """Local shim over `_factories.make_symbol` — keeps the (ports, label) order used below."""
    return _canonical_make_symbol(label=label, ports=ports)


def _sym_with_down_up(
    down_x: list[float],
    up_x: list[float],
    y_down: float = 20.0,
    y_up: float = 0.0,
    label: str | None = None,
) -> Symbol:
    """Create a symbol with downward ports at *down_x* and upward ports at *up_x*."""
    ports: dict[str, Port] = {}
    for i, x in enumerate(down_x):
        pid = f"d{i}"
        ports[pid] = _port(pid, x, y_down, 0, 1)
    for i, x in enumerate(up_x):
        pid = f"u{i}"
        ports[pid] = _port(pid, x, y_up, 0, -1)
    return _make_symbol(ports, label=label)


def mock_circuit_generator(state, x, y):
    # Mock generator that increments a counter in state and returns a dummy element
    count = state.get("count", 0)
    new_state = state.copy()
    new_state["count"] = count + 1

    # Return a dummy element with the given position.
    # Element is abstract, but we can't instantiate it
    # directly if it's strictly abstract (dataclass isn't
    # abc usually).
    # But Point is NOT an Element.
    # Let's return a list containing a Point? No, return
    # type says List[Element].
    # But for the test, as long as it returns *something*
    # compatible with list extension.
    element = Point(x, y)
    return new_state, [element]


class TestLayoutUnit:
    def test_layout_horizontal(self):
        state = {"count": 0}

        final_state, elements = layout_horizontal(
            start_state=state,
            start_x=0,
            start_y=0,
            spacing=10,
            count=3,
            generate_func=mock_circuit_generator,
        )

        assert final_state["count"] == 3
        assert len(elements) == 3

        p1 = elements[0]
        p2 = elements[1]
        p3 = elements[2]

        assert isinstance(p1, Point)
        assert isinstance(p2, Point)
        assert isinstance(p3, Point)
        assert p1.x == 0
        assert p2.x == 10
        assert p3.x == 20


# ===================================================================
# get_connection_ports
# ===================================================================


class TestGetConnectionPorts:
    """Tests for get_connection_ports(symbol, direction)."""

    def test_returns_matching_down_ports(self):
        """Ports with direction (0,1) should be returned when queried for down."""
        sym = _make_symbol(
            {
                "1": _port("1", 10, 0, 0, -1),  # up
                "2": _port("2", 10, 20, 0, 1),  # down
                "3": _port("3", 20, 20, 0, 1),  # down
            }
        )
        result = get_connection_ports(sym, Vector(0, 1))
        assert len(result) == 2
        ids = {p.id for p in result}
        assert ids == {"2", "3"}

    def test_returns_matching_up_ports(self):
        """Ports with direction (0,-1) should be returned when queried for up."""
        sym = _make_symbol(
            {
                "1": _port("1", 10, 0, 0, -1),
                "2": _port("2", 20, 0, 0, -1),
                "3": _port("3", 10, 20, 0, 1),
            }
        )
        result = get_connection_ports(sym, Vector(0, -1))
        assert len(result) == 2
        ids = {p.id for p in result}
        assert ids == {"1", "2"}

    def test_returns_matching_right_ports(self):
        """Ports with direction (1,0) should be returned when queried for right."""
        sym = _make_symbol(
            {
                "a": _port("a", 0, 10, 1, 0),
                "b": _port("b", 0, 20, -1, 0),
            }
        )
        result = get_connection_ports(sym, Vector(1, 0))
        assert len(result) == 1
        assert result[0].id == "a"

    def test_returns_empty_when_no_match(self):
        """If no ports match the given direction, return an empty list."""
        sym = _make_symbol(
            {
                "1": _port("1", 10, 0, 0, -1),
            }
        )
        result = get_connection_ports(sym, Vector(0, 1))
        assert result == []

    def test_empty_ports_symbol(self):
        """A symbol with no ports returns an empty list regardless of direction."""
        sym = _make_symbol({})
        result = get_connection_ports(sym, Vector(0, 1))
        assert result == []

    def test_deduplicates_spatially_coincident_ports(self):
        """Two ports at the same position but with the same direction should be de-duped."""
        sym = _make_symbol(
            {
                "1": _port("1", 10, 0, 0, -1),
                "1_alias": _port("1_alias", 10, 0, 0, -1),
            }
        )
        result = get_connection_ports(sym, Vector(0, -1))
        # Only one should come back because they share the same (x, y)
        assert len(result) == 1

    def test_does_not_deduplicate_different_positions(self):
        """Ports at different positions with the same direction are all returned."""
        sym = _make_symbol(
            {
                "1": _port("1", 10, 0, 0, -1),
                "2": _port("2", 20, 0, 0, -1),
                "3": _port("3", 30, 0, 0, -1),
            }
        )
        result = get_connection_ports(sym, Vector(0, -1))
        assert len(result) == 3

    def test_near_zero_direction_matches(self):
        """Directions very close to the target (within tolerance) should match."""
        sym = _make_symbol(
            {
                "1": _port("1", 10, 0, 1e-8, -1 + 1e-8),
            }
        )
        result = get_connection_ports(sym, Vector(0, -1))
        assert len(result) == 1


# ===================================================================
# draw_wire
# ===================================================================


class TestAutoConnect:
    """Tests for draw_wire(sym_above, sym_below)."""

    def test_single_aligned_pair(self):
        """A single down port aligned with a single up port creates one Line."""
        sym_top = _sym_with_down_up(down_x=[10], up_x=[], y_down=20)
        sym_bot = _sym_with_down_up(down_x=[], up_x=[10], y_up=40)

        lines = draw_wire(sym_top, sym_bot)
        assert len(lines) == 1
        assert isinstance(lines[0], Line)
        assert lines[0].start == Point(10, 20)
        assert lines[0].end == Point(10, 40)

    def test_multiple_aligned_pairs(self):
        """Three aligned columns should produce three lines."""
        sym_top = _sym_with_down_up(down_x=[10, 20, 30], up_x=[])
        sym_bot = _sym_with_down_up(down_x=[], up_x=[10, 20, 30], y_up=50)

        lines = draw_wire(sym_top, sym_bot)
        assert len(lines) == 3
        x_values = sorted([line.start.x for line in lines])
        assert x_values == [10, 20, 30]

    def test_no_alignment_no_lines(self):
        """If ports don't align in X, no lines are created."""
        sym_top = _sym_with_down_up(down_x=[10], up_x=[])
        sym_bot = _sym_with_down_up(down_x=[], up_x=[50], y_up=40)

        lines = draw_wire(sym_top, sym_bot)
        assert lines == []

    def test_partial_alignment(self):
        """Only the aligned subset should produce lines."""
        sym_top = _sym_with_down_up(down_x=[10, 20, 30], up_x=[])
        sym_bot = _sym_with_down_up(down_x=[], up_x=[10, 30], y_up=40)

        lines = draw_wire(sym_top, sym_bot)
        assert len(lines) == 2
        x_values = sorted([line.start.x for line in lines])
        assert x_values == [10, 30]

    def test_tolerance_boundary_just_inside(self):
        """Ports whose X differs by less than the tolerance should connect."""
        sym_top = _sym_with_down_up(down_x=[10.0], up_x=[])
        sym_bot = _sym_with_down_up(down_x=[], up_x=[10.05], y_up=40)

        lines = draw_wire(sym_top, sym_bot)
        assert len(lines) == 1

    def test_tolerance_boundary_just_outside(self):
        """Ports whose X differs by >= tolerance should NOT connect."""
        sym_top = _sym_with_down_up(down_x=[10.0], up_x=[])
        sym_bot = _sym_with_down_up(down_x=[], up_x=[10.2], y_up=40)

        lines = draw_wire(sym_top, sym_bot)
        assert len(lines) == 0

    def test_empty_symbols(self):
        """Two empty symbols produce no lines."""
        sym_top = _make_symbol({})
        sym_bot = _make_symbol({})
        lines = draw_wire(sym_top, sym_bot)
        assert lines == []

    def test_ignores_non_matching_directions(self):
        """Ports that face left/right should be ignored by draw_wire."""
        sym_top = _make_symbol(
            {
                "1": _port("1", 10, 20, 1, 0),  # right-facing
            }
        )
        sym_bot = _make_symbol(
            {
                "1": _port("1", 10, 40, -1, 0),  # left-facing
            }
        )
        lines = draw_wire(sym_top, sym_bot)
        assert lines == []

    def test_returned_lines_have_style(self):
        """Lines produced by draw_wire should have standard_style applied."""
        sym_top = _sym_with_down_up(down_x=[10], up_x=[])
        sym_bot = _sym_with_down_up(down_x=[], up_x=[10], y_up=40)

        lines = draw_wire(sym_top, sym_bot)
        assert len(lines) == 1
        # standard_style returns a Style with specific stroke_width
        assert lines[0].style is not None
        assert lines[0].style.stroke == "black"


# ===================================================================
# _find_matching_ports
# ===================================================================


class TestFindMatchingPorts:
    """Tests for _find_matching_ports(down_ports, up_ports)."""

    def test_basic_matching(self):
        """Ports at the same X position should be paired."""
        down = [_port("d1", 10, 20, 0, 1), _port("d2", 20, 20, 0, 1)]
        up = [_port("u1", 10, 40, 0, -1), _port("u2", 20, 40, 0, -1)]

        pairs = _find_matching_ports(down, up)
        assert len(pairs) == 2
        assert pairs[0][0].id == "d1"
        assert pairs[0][1].id == "u1"
        assert pairs[1][0].id == "d2"
        assert pairs[1][1].id == "u2"

    def test_sorted_by_x_position(self):
        """Down ports should be sorted by X position before matching."""
        # Provide them out of order
        down = [_port("d2", 20, 20, 0, 1), _port("d1", 10, 20, 0, 1)]
        up = [_port("u1", 10, 40, 0, -1), _port("u2", 20, 40, 0, -1)]

        pairs = _find_matching_ports(down, up)
        assert len(pairs) == 2
        # First pair should be at x=10, second at x=20
        assert pairs[0][0].position.x == 10
        assert pairs[1][0].position.x == 20

    def test_no_matching_ports(self):
        """Misaligned ports produce no pairs."""
        down = [_port("d1", 10, 20, 0, 1)]
        up = [_port("u1", 50, 40, 0, -1)]

        pairs = _find_matching_ports(down, up)
        assert pairs == []

    def test_empty_lists(self):
        """Empty input lists produce no pairs."""
        assert _find_matching_ports([], []) == []
        down = [_port("d1", 10, 20, 0, 1)]
        assert _find_matching_ports(down, []) == []
        up = [_port("u1", 10, 40, 0, -1)]
        assert _find_matching_ports([], up) == []

    def test_partial_match(self):
        """Only matching subsets should be paired."""
        down = [_port("d1", 10, 20, 0, 1), _port("d2", 30, 20, 0, 1)]
        up = [_port("u1", 10, 40, 0, -1)]

        pairs = _find_matching_ports(down, up)
        assert len(pairs) == 1
        assert pairs[0][0].id == "d1"

    def test_tolerance_matching(self):
        """Ports within DEFAULT_WIRE_ALIGNMENT_TOLERANCE (0.1mm) should match."""
        down = [_port("d1", 10.05, 20, 0, 1)]
        up = [_port("u1", 10.0, 40, 0, -1)]

        pairs = _find_matching_ports(down, up)
        assert len(pairs) == 1

    def test_first_match_wins(self):
        """When multiple up ports could match, the first one found wins."""
        down = [_port("d1", 10, 20, 0, 1)]
        up = [_port("u1", 10, 40, 0, -1), _port("u2", 10, 50, 0, -1)]

        pairs = _find_matching_ports(down, up)
        assert len(pairs) == 1
        # The first up port in the list should be matched
        assert pairs[0][1].id == "u1"


# ===================================================================
# _get_wire_label_spec
# ===================================================================


class TestGetWireLabelSpec:
    """Tests for _get_wire_label_spec(dp, match_index, wire_specs)."""

    def test_none_specs_returns_empty(self):
        """None wire_specs should return ("", "")."""
        dp = _port("d1", 10, 20, 0, 1)
        assert _get_wire_label_spec(dp, 0, None) == ("", "")

    def test_empty_dict_returns_empty(self):
        """Empty dict should return ("", "")."""
        dp = _port("d1", 10, 20, 0, 1)
        assert _get_wire_label_spec(dp, 0, {}) == ("", "")

    def test_empty_list_returns_empty(self):
        """Empty list should return ("", "")."""
        dp = _port("d1", 10, 20, 0, 1)
        assert _get_wire_label_spec(dp, 0, []) == ("", "")

    def test_dict_lookup_by_port_id(self):
        """Dict specs should be looked up by the port's id."""
        dp = _port("L1", 10, 20, 0, 1)
        specs = {"L1": ("RD", "2.5mm²"), "L2": ("BK", "1.5mm²")}
        assert _get_wire_label_spec(dp, 0, specs) == ("RD", "2.5mm²")

    def test_dict_lookup_missing_key(self):
        """Dict specs with missing key should return ("", "")."""
        dp = _port("L3", 10, 20, 0, 1)
        specs = {"L1": ("RD", "2.5mm²")}
        assert _get_wire_label_spec(dp, 0, specs) == ("", "")

    def test_list_lookup_by_index(self):
        """List specs should be looked up by match_index."""
        dp = _port("d1", 10, 20, 0, 1)
        specs = [("RD", "2.5mm²"), ("BK", "1.5mm²"), ("BU", "0.75mm²")]
        assert _get_wire_label_spec(dp, 0, specs) == ("RD", "2.5mm²")
        assert _get_wire_label_spec(dp, 1, specs) == ("BK", "1.5mm²")
        assert _get_wire_label_spec(dp, 2, specs) == ("BU", "0.75mm²")

    def test_list_index_out_of_range(self):
        """List index out of range should return ("", "")."""
        dp = _port("d1", 10, 20, 0, 1)
        specs = [("RD", "2.5mm²")]
        assert _get_wire_label_spec(dp, 5, specs) == ("", "")

    def test_non_tuple_in_dict_returns_empty(self):
        """If a dict value is not a tuple, return ("", "")."""
        dp = _port("L1", 10, 20, 0, 1)
        specs = {"L1": "not_a_tuple"}
        assert _get_wire_label_spec(dp, 0, specs) == ("", "")  # ty: ignore[invalid-argument-type]

    def test_non_tuple_in_list_returns_empty(self):
        """If a list entry is not a tuple, return ("", "")."""
        dp = _port("d1", 10, 20, 0, 1)
        specs = ["not_a_tuple"]
        assert _get_wire_label_spec(dp, 0, specs) == ("", "")  # ty: ignore[invalid-argument-type]


# ===================================================================
# draw_wire_labeled
# ===================================================================


class TestAutoConnectLabeled:
    """Tests for draw_wire_labeled(sym_above, sym_below, labels)."""

    def test_basic_labeled_connection(self):
        """Connect two symbols with wire label specs and verify elements are generated."""
        sym_top = _sym_with_down_up(down_x=[10], up_x=[])
        sym_bot = _sym_with_down_up(down_x=[], up_x=[10], y_up=40)

        specs = [("RD", "2.5mm²")]
        elements = draw_wire_labeled(sym_top, sym_bot, wire_specs=specs)

        # Should have a Line and a Text label
        assert len(elements) == 2
        lines = [e for e in elements if isinstance(e, Line)]
        texts = [e for e in elements if isinstance(e, Text)]
        assert len(lines) == 1
        assert len(texts) == 1
        assert "RD" in texts[0].content

    def test_no_specs_still_creates_lines(self):
        """With None specs, lines should still be created but without labels."""
        sym_top = _sym_with_down_up(down_x=[10], up_x=[])
        sym_bot = _sym_with_down_up(down_x=[], up_x=[10], y_up=40)

        elements = draw_wire_labeled(sym_top, sym_bot, wire_specs=None)

        lines = [e for e in elements if isinstance(e, Line)]
        texts = [e for e in elements if isinstance(e, Text)]
        assert len(lines) == 1
        assert len(texts) == 0

    def test_empty_specs_creates_lines_without_labels(self):
        """With empty dict specs, lines are created without labels."""
        sym_top = _sym_with_down_up(down_x=[10], up_x=[])
        sym_bot = _sym_with_down_up(down_x=[], up_x=[10], y_up=40)

        elements = draw_wire_labeled(sym_top, sym_bot, wire_specs={})

        lines = [e for e in elements if isinstance(e, Line)]
        texts = [e for e in elements if isinstance(e, Text)]
        assert len(lines) == 1
        assert len(texts) == 0

    def test_multiple_connections_with_list_specs(self):
        """Three aligned ports with list specs produce 3 lines and 3 labels."""
        sym_top = _sym_with_down_up(down_x=[10, 20, 30], up_x=[])
        sym_bot = _sym_with_down_up(down_x=[], up_x=[10, 20, 30], y_up=40)

        specs = [("RD", "2.5mm²"), ("BK", "2.5mm²"), ("BU", "2.5mm²")]
        elements = draw_wire_labeled(sym_top, sym_bot, wire_specs=specs)

        lines = [e for e in elements if isinstance(e, Line)]
        texts = [e for e in elements if isinstance(e, Text)]
        assert len(lines) == 3
        assert len(texts) == 3

    def test_dict_specs_keyed_by_port_id(self):
        """Dict-based wire_specs are looked up by port ID of the down port."""
        sym_top = _make_symbol(
            {
                "L1": _port("L1", 10, 20, 0, 1),
                "L2": _port("L2", 20, 20, 0, 1),
            }
        )
        sym_bot = _make_symbol(
            {
                "T1": _port("T1", 10, 40, 0, -1),
                "T2": _port("T2", 20, 40, 0, -1),
            }
        )

        specs = {"L1": ("RD", "2.5mm²"), "L2": ("BK", "1.5mm²")}
        elements = draw_wire_labeled(sym_top, sym_bot, wire_specs=specs)

        lines = [e for e in elements if isinstance(e, Line)]
        texts = [e for e in elements if isinstance(e, Text)]
        assert len(lines) == 2
        assert len(texts) == 2

    def test_no_aligned_ports_produces_nothing(self):
        """If no ports align, no elements should be produced."""
        sym_top = _sym_with_down_up(down_x=[10], up_x=[])
        sym_bot = _sym_with_down_up(down_x=[], up_x=[99], y_up=40)

        elements = draw_wire_labeled(sym_top, sym_bot, wire_specs=[("RD", "2.5mm²")])
        assert elements == []


# ===================================================================
# layout_vertical_chain
# ===================================================================


class TestLayoutVerticalChain:
    """Tests for layout_vertical_chain(symbols, start, spacing)."""

    def test_basic_vertical_chain(self):
        """Two symbols should be placed vertically and connected."""
        sym1 = _sym_with_down_up(down_x=[0], up_x=[0], y_down=5, y_up=-5, label="S1")
        sym2 = _sym_with_down_up(down_x=[0], up_x=[0], y_down=5, y_up=-5, label="S2")

        elements = layout_vertical_chain([sym1, sym2], start=Point(50, 50), spacing=60)

        # Should contain 2 placed symbols + connection lines
        symbols = [e for e in elements if isinstance(e, Symbol)]
        lines = [e for e in elements if isinstance(e, Line)]
        assert len(symbols) == 2
        # The down port of first symbol at y=50+5=55, up port of second at y=110-5=105
        # They share x=50+0=50, so one line should be created
        assert len(lines) == 1

    def test_single_symbol_no_connections(self):
        """A single symbol should produce one placed symbol and no connections."""
        sym = _sym_with_down_up(down_x=[0], up_x=[0], y_down=5, y_up=-5, label="S1")

        elements = layout_vertical_chain([sym], start=Point(10, 20), spacing=60)

        symbols = [e for e in elements if isinstance(e, Symbol)]
        lines = [e for e in elements if isinstance(e, Line)]
        assert len(symbols) == 1
        assert len(lines) == 0

    def test_vertical_positions(self):
        """Symbols should be placed at start_y, start_y+spacing, start_y+2*spacing, etc."""
        sym1 = _make_symbol({"1": _port("1", 0, 0, 0, -1)}, label="S1")
        sym2 = _make_symbol({"1": _port("1", 0, 0, 0, -1)}, label="S2")
        sym3 = _make_symbol({"1": _port("1", 0, 0, 0, -1)}, label="S3")

        elements = layout_vertical_chain(
            [sym1, sym2, sym3], start=Point(100, 0), spacing=50
        )

        symbols = [e for e in elements if isinstance(e, Symbol)]
        assert len(symbols) == 3

        # First symbol port at (100+0, 0+0) = (100, 0)
        assert symbols[0].ports["1"].position == Point(100, 0)
        # Second symbol port at (100+0, 50+0) = (100, 50)
        assert symbols[1].ports["1"].position == Point(100, 50)
        # Third symbol port at (100+0, 100+0) = (100, 100)
        assert symbols[2].ports["1"].position == Point(100, 100)

    def test_empty_list(self):
        """An empty symbols list should return an empty result."""
        elements = layout_vertical_chain([], start=Point(0, 0), spacing=60)
        assert elements == []

    def test_three_symbol_chain_with_connections(self):
        """Three symbols should produce two connection line sets."""
        sym1 = _sym_with_down_up(down_x=[0], up_x=[], y_down=5, label="S1")
        sym2 = _sym_with_down_up(down_x=[0], up_x=[0], y_down=5, y_up=-5, label="S2")
        sym3 = _sym_with_down_up(down_x=[], up_x=[0], y_up=-5, label="S3")

        elements = layout_vertical_chain(
            [sym1, sym2, sym3], start=Point(50, 0), spacing=60
        )

        lines = [e for e in elements if isinstance(e, Line)]
        # sym1 (y=0) -> sym2 (y=60): down port at (50,5) to up port at (50,55) -> 1 line
        # sym2 (y=60) -> sym3 (y=120): down port at (50,65) to up port at (50,115) -> 1 line
        assert len(lines) == 2

    def test_horizontal_position_preserved(self):
        """start.x should be applied to all symbols."""
        sym = _make_symbol(
            {
                "1": _port("1", 0, -5, 0, -1),
                "2": _port("2", 10, -5, 0, -1),
            },
            label="S1",
        )

        elements = layout_vertical_chain([sym], start=Point(100, 200), spacing=60)
        placed = next(e for e in elements if isinstance(e, Symbol))

        assert placed.ports["1"].position == Point(100, 195)
        assert placed.ports["2"].position == Point(110, 195)


# ===================================================================
# layout_horizontal (existing test class + additions)
# ===================================================================


class TestLayoutHorizontalAdditional:
    """Additional tests for layout_horizontal."""

    def test_count_zero_produces_empty(self):
        """count=0 should produce an empty list and unchanged state."""
        state = {"count": 0}
        final_state, elements = layout_horizontal(
            start_state=state,
            start_x=0,
            start_y=0,
            spacing=10,
            count=0,
            generate_func=mock_circuit_generator,
        )
        assert final_state["count"] == 0
        assert elements == []

    def test_y_position_is_constant(self):
        """All elements should have the same y position."""
        state = {}

        def gen(s, x, y):
            return s, [Point(x, y)]

        _, elements = layout_horizontal(
            start_state=state,
            start_x=0,
            start_y=42,
            spacing=10,
            count=5,
            generate_func=gen,
        )
        for p in elements:
            assert isinstance(p, Point)
            assert p.y == 42

    def test_state_threading(self):
        """State should be threaded through sequential calls."""

        def gen(s, x, y):
            new_s = s.copy()
            new_s["tags"] = [*s.get("tags", []), f"K{s.get('n', 0) + 1}"]
            new_s["n"] = s.get("n", 0) + 1
            return new_s, [Point(x, y)]

        final, _ = layout_horizontal(
            start_state={}, start_x=0, start_y=0, spacing=10, count=3, generate_func=gen
        )
        assert final["tags"] == ["K1", "K2", "K3"]

    def test_single_instance(self):
        """count=1 should call the generator once at start_x."""
        state = {"count": 0}
        final_state, elements = layout_horizontal(
            start_state=state,
            start_x=100,
            start_y=200,
            spacing=50,
            count=1,
            generate_func=mock_circuit_generator,
        )
        assert final_state["count"] == 1
        assert len(elements) == 1
        assert isinstance(elements[0], Point)
        assert elements[0].x == 100
        assert elements[0].y == 200


# ===================================================================
# create_horizontal_layout
# ===================================================================


class TestCreateHorizontalLayout:
    """Tests for create_horizontal_layout."""

    @staticmethod
    def _mock_gen_single(state, x, y, tag_generators, terminal_maps, index):
        """Mock generator for create_horizontal_layout."""
        new_state = state.copy()
        count = new_state.get("count", 0)
        new_state["count"] = count + 1
        return new_state, [Point(x, y)]

    def test_basic_horizontal_layout(self):
        """Basic usage with 3 instances."""
        state = {"count": 0}
        final, elements = create_horizontal_layout(
            state=state,
            start_x=0,
            start_y=0,
            count=3,
            spacing=20,
            generator_func_single=self._mock_gen_single,
            default_tag_generators={},
        )
        assert final["count"] == 3
        assert len(elements) == 3
        assert elements[0].x == 0
        assert elements[1].x == 20
        assert elements[2].x == 40

    def test_count_zero(self):
        """count=0 produces no elements."""
        state = {}
        _, elements = create_horizontal_layout(
            state=state,
            start_x=0,
            start_y=0,
            count=0,
            spacing=20,
            generator_func_single=self._mock_gen_single,
            default_tag_generators={},
        )
        assert elements == []

    def test_tag_generators_merging(self):
        """tag_generators should override default_tag_generators."""
        calls = []

        def gen(state, x, y, tag_gens, tm, idx):
            calls.append(tag_gens.copy())
            return state, [Point(x, y)]

        defaults = {"Q": "default_q", "F": "default_f"}
        overrides = {"Q": "custom_q"}

        create_horizontal_layout(
            state={},
            start_x=0,
            start_y=0,
            count=1,
            spacing=20,
            generator_func_single=gen,
            default_tag_generators=defaults,
            tag_generators=overrides,
        )

        # The generator should receive merged dict
        assert calls[0]["Q"] == "custom_q"
        assert calls[0]["F"] == "default_f"

    def test_default_tag_generators_not_mutated(self):
        """default_tag_generators should not be mutated by the merge."""
        defaults = {"Q": "default_q"}
        overrides = {"F": "override_f"}

        def gen(state, x, y, tag_gens, tm, idx):
            return state, []

        create_horizontal_layout(
            state={},
            start_x=0,
            start_y=0,
            count=1,
            spacing=20,
            generator_func_single=gen,
            default_tag_generators=defaults,
            tag_generators=overrides,
        )

        # Original should be untouched
        assert "F" not in defaults

    def test_terminal_maps_default_to_empty(self):
        """When terminal_maps is None, generator should receive empty dict."""
        received_tm = []

        def gen(state, x, y, tag_gens, tm, idx):
            received_tm.append(tm)
            return state, []

        create_horizontal_layout(
            state={},
            start_x=0,
            start_y=0,
            count=1,
            spacing=20,
            generator_func_single=gen,
            default_tag_generators={},
            terminal_maps=None,
        )
        assert received_tm[0] == {}

    def test_terminal_maps_passed_through(self):
        """When terminal_maps is provided, it should be forwarded to the generator."""
        received_tm = []

        def gen(state, x, y, tag_gens, tm, idx):
            received_tm.append(tm)
            return state, []

        my_maps = {"X1": "some_config"}
        create_horizontal_layout(
            state={},
            start_x=0,
            start_y=0,
            count=2,
            spacing=20,
            generator_func_single=gen,
            default_tag_generators={},
            terminal_maps=my_maps,
        )
        assert received_tm[0] == my_maps
        assert received_tm[1] == my_maps

    def test_index_passed_to_generator(self):
        """The instance index should be passed to the generator."""
        indices = []

        def gen(state, x, y, tag_gens, tm, idx):
            indices.append(idx)
            return state, []

        create_horizontal_layout(
            state={},
            start_x=0,
            start_y=0,
            count=4,
            spacing=10,
            generator_func_single=gen,
            default_tag_generators={},
        )
        assert indices == [0, 1, 2, 3]

    def test_state_threading_across_instances(self):
        """State should be threaded through all instances sequentially."""

        def gen(state, x, y, tag_gens, tm, idx):
            new_state = state.copy()
            new_state["sum"] = state.get("sum", 0) + idx
            return new_state, [Point(x, y)]

        final, _ = create_horizontal_layout(
            state={},
            start_x=0,
            start_y=0,
            count=5,
            spacing=10,
            generator_func_single=gen,
            default_tag_generators={},
        )
        # 0 + 1 + 2 + 3 + 4 = 10
        assert final["sum"] == 10

    def test_tag_generators_none(self):
        """tag_generators=None should not cause an error and only use defaults."""
        calls = []

        def gen(state, x, y, tag_gens, tm, idx):
            calls.append(tag_gens.copy())
            return state, []

        defaults = {"Q": "default_q"}
        create_horizontal_layout(
            state={},
            start_x=0,
            start_y=0,
            count=1,
            spacing=20,
            generator_func_single=gen,
            default_tag_generators=defaults,
            tag_generators=None,
        )
        assert calls[0] == {"Q": "default_q"}

    def test_start_position_offset(self):
        """Elements should start at start_x and be spaced by spacing."""
        state = {}
        _, elements = create_horizontal_layout(
            state=state,
            start_x=100,
            start_y=200,
            count=3,
            spacing=50,
            generator_func_single=self._mock_gen_single,
            default_tag_generators={},
        )
        assert elements[0].x == 100
        assert elements[0].y == 200
        assert elements[1].x == 150
        assert elements[2].x == 200
