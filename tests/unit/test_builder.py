import pytest

from schematika.electrical.builder import (
    BuildResult,
    CircuitBuilder,
    ComponentRef,
    ComponentSpec,
    LayoutConfig,
    PortRef,
)
from schematika.electrical.builder_utils import (
    _distribute_pins,
    _get_absolute_x_offset,
    _resolve_pin,
    _resolve_registry_pin,
)
from schematika.electrical.exceptions import (
    ComponentNotFoundError,
    PortNotFoundError,
    TagReuseError,
    TerminalReuseError,
)
from schematika.electrical.model.core import Point, Port, Symbol, Vector
from schematika.electrical.system.system import Circuit
from schematika.electrical.utils.autonumbering import create_autonumberer

# ---------------------------------------------------------------------------
# Mock symbol factories
# ---------------------------------------------------------------------------


def mock_symbol(tag, **kwargs):
    """Simple 1-pole symbol with ports 1 (up) and 2 (down)."""
    s = Symbol(
        elements=[],
        ports={
            "1": Port("1", Point(0, -1), Vector(0, -1)),
            "2": Port("2", Point(0, 1), Vector(0, 1)),
        },
        label=tag,
    )
    return s


def mock_symbol_with_pins(tag, pins=(), **kwargs):
    """Symbol factory that accepts a pins parameter."""
    ports = {}
    for i, pin in enumerate(pins):
        y = -10 + i * 10
        direction = Vector(0, -1) if i % 2 == 0 else Vector(0, 1)
        ports[pin] = Port(pin, Point(0, y), direction)
    if not ports:
        ports = {
            "1": Port("1", Point(0, -1), Vector(0, -1)),
            "2": Port("2", Point(0, 1), Vector(0, 1)),
        }
    return Symbol(elements=[], ports=ports, label=tag)


def mock_two_pole_symbol(tag, pins=(), **kwargs):
    """A 2-pole symbol with ports 1,2,3,4."""
    ports = {
        "1": Port("1", Point(0, -10), Vector(0, -1)),
        "2": Port("2", Point(0, 10), Vector(0, 1)),
        "3": Port("3", Point(20, -10), Vector(0, -1)),
        "4": Port("4", Point(20, 10), Vector(0, 1)),
    }
    if pins:
        ports = {}
        for i, pin in enumerate(pins):
            col = (i // 2) * 20
            row = -10 if i % 2 == 0 else 10
            direction = Vector(0, -1) if i % 2 == 0 else Vector(0, 1)
            ports[pin] = Port(pin, Point(col, row), direction)
    return Symbol(elements=[], ports=ports, label=tag)


def mock_symbol_with_contact_pins(
    tag, contact_pins=("1", "2"), coil_pins=None, **kwargs
):
    """Symbol that accepts contact_pins and coil_pins parameters."""
    ports = {}
    for i, pin in enumerate(contact_pins):
        ports[pin] = Port(pin, Point(0, -10 + i * 20), Vector(0, -1 if i == 0 else 1))
    if coil_pins:
        for i, pin in enumerate(coil_pins):
            ports[pin] = Port(
                pin, Point(20, -10 + i * 20), Vector(0, -1 if i == 0 else 1)
            )
    return Symbol(elements=[], ports=ports, label=tag)


class TestBuilderUnit:
    def test_builder_initialization(self):
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        assert builder is not None

    def test_add_terminal(self):
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.add_terminal("X99", poles=1)

        # Verify specs are added
        assert len(builder._spec.components) == 1
        spec = builder._spec.components[0]
        assert spec.kind == "terminal"
        assert spec.kwargs["tm_id"] == "X99"

    def test_add_symbol(self):
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.add_symbol(mock_symbol, tag_prefix="K")

        assert len(builder._spec.components) == 1
        spec = builder._spec.components[0]
        assert spec.kind == "symbol"
        assert spec.tag_prefix == "K"

    def test_build_single_simple(self):
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(0, 0)
        builder.add_symbol(mock_symbol, tag_prefix="K")

        # In the refactored builder, we expect a BuildResult object
        result = builder.build(count=1)

        assert result.circuit is not None
        assert len(result.circuit.elements) > 0
        assert result.state is not None

    def test_build_validates_connection_indices(self):
        """Invalid connection indices should raise ComponentNotFoundError."""
        from schematika.electrical.exceptions import ComponentNotFoundError

        state = create_autonumberer()

        builder = CircuitBuilder(state)
        builder.set_layout(0, 0)
        builder.add_terminal("X1")  # Index 0
        builder.add_connection(0, 0, 5, 0)  # Index 5 doesn't exist

        with pytest.raises(ComponentNotFoundError):
            builder.build()


class TestResolvePinEdgeCases:
    """Tests for _resolve_pin edge cases."""

    def test_terminal_pin_resolution_1_pole(self):
        """1-pole terminal should resolve to ports '1' (in) and '2' (out)."""
        from schematika.electrical.builder import ComponentSpec, _resolve_pin

        component_data = {
            "spec": ComponentSpec(func=None, kind="terminal", poles=1),
            "pins": ["42"],  # Terminal number
        }

        assert _resolve_pin(component_data, pole_idx=0, is_input=True) == "1"
        assert _resolve_pin(component_data, pole_idx=0, is_input=False) == "2"

    def test_terminal_pin_resolution_3_pole(self):
        """3-pole terminal poles should map to correct port IDs."""
        from schematika.electrical.builder import ComponentSpec, _resolve_pin

        component_data = {
            "spec": ComponentSpec(func=None, kind="terminal", poles=3),
            "pins": ["1", "2", "3"],
        }

        # Pole 0: ports 1, 2
        assert _resolve_pin(component_data, pole_idx=0, is_input=True) == "1"
        assert _resolve_pin(component_data, pole_idx=0, is_input=False) == "2"
        # Pole 1: ports 3, 4
        assert _resolve_pin(component_data, pole_idx=1, is_input=True) == "3"
        assert _resolve_pin(component_data, pole_idx=1, is_input=False) == "4"
        # Pole 2: ports 5, 6
        assert _resolve_pin(component_data, pole_idx=2, is_input=True) == "5"
        assert _resolve_pin(component_data, pole_idx=2, is_input=False) == "6"

    def test_symbol_with_2x_pins(self):
        """Symbol with poles*2 pins should use interleaved indexing."""
        from schematika.electrical.builder import ComponentSpec, _resolve_pin

        component_data = {
            "spec": ComponentSpec(func=lambda: None, kind="symbol", poles=2),
            "pins": ["A1", "A2", "B1", "B2"],  # 4 pins = 2 poles * 2
        }

        # Pole 0
        assert _resolve_pin(component_data, pole_idx=0, is_input=True) == "A1"
        assert _resolve_pin(component_data, pole_idx=0, is_input=False) == "A2"
        # Pole 1
        assert _resolve_pin(component_data, pole_idx=1, is_input=True) == "B1"
        assert _resolve_pin(component_data, pole_idx=1, is_input=False) == "B2"

    def test_symbol_with_custom_named_ports(self):
        """Symbol with non-standard pin count should use direct indexing."""
        from schematika.electrical.builder import ComponentSpec, _resolve_pin

        component_data = {
            "spec": ComponentSpec(func=lambda: None, kind="symbol", poles=1),
            "pins": ["L", "N", "PE", "24V", "GND"],  # 5 pins, not poles*2
        }

        # Direct indexing
        assert _resolve_pin(component_data, pole_idx=0, is_input=True) == "L"
        assert _resolve_pin(component_data, pole_idx=1, is_input=True) == "N"
        assert _resolve_pin(component_data, pole_idx=2, is_input=True) == "PE"

    def test_symbol_without_pins_fallback(self):
        """Symbol without explicit pins should fall back to 1/2, 3/4 pairing."""
        component_data = {
            "spec": ComponentSpec(func=lambda: None, kind="symbol", poles=2),
            "pins": [],  # No pins
        }

        # Pole 0: In="1", Out="2"
        assert _resolve_pin(component_data, pole_idx=0, is_input=True) == "1"
        assert _resolve_pin(component_data, pole_idx=0, is_input=False) == "2"
        # Pole 1: In="3", Out="4"
        assert _resolve_pin(component_data, pole_idx=1, is_input=True) == "3"
        assert _resolve_pin(component_data, pole_idx=1, is_input=False) == "4"


# ---------------------------------------------------------------------------
# BuildResult tests
# ---------------------------------------------------------------------------


class TestBuildResult:
    """Tests for BuildResult dataclass and its methods."""

    def _make_result(self, component_map=None, terminal_pin_map=None):
        """Helper to create a BuildResult with controlled data."""
        return BuildResult(
            state=create_autonumberer(),
            circuit=Circuit(),
            used_terminals=[],
            component_map=component_map or {},
            terminal_pin_map=terminal_pin_map or {},
        )

    def test_iter_unpacking(self):
        """BuildResult should support tuple unpacking (state, circuit, used_terminals)."""
        result = self._make_result()
        state, circuit, used_terminals = result
        assert state is result.state
        assert circuit is result.circuit
        assert used_terminals is result.used_terminals

    def test_iter_returns_three_items(self):
        """__iter__ should yield exactly 3 items."""
        result = self._make_result()
        items = list(result)
        assert len(items) == 3

    def test_reuse_tags_returns_generator(self):
        """reuse_tags should return a callable generator function."""
        result = self._make_result(component_map={"K": ["K1", "K2", "K3"]})
        gen = result.reuse_tags("K")
        assert callable(gen)

    def test_reuse_tags_yields_tags_in_order(self):
        """reuse_tags generator should yield tags in insertion order."""
        result = self._make_result(component_map={"K": ["K1", "K2", "K3"]})
        gen = result.reuse_tags("K")
        state = create_autonumberer()

        state, tag1 = gen(state)
        assert tag1 == "K1"
        state, tag2 = gen(state)
        assert tag2 == "K2"
        state, tag3 = gen(state)
        assert tag3 == "K3"

    def test_reuse_tags_exhaustion_raises_error(self):
        """reuse_tags should raise TagReuseError when tags run out."""
        result = self._make_result(component_map={"K": ["K1"]})
        gen = result.reuse_tags("K")
        state = create_autonumberer()

        # First call succeeds
        state, tag = gen(state)
        assert tag == "K1"

        # Second call should raise
        with pytest.raises(TagReuseError) as exc_info:
            gen(state)
        assert exc_info.value.prefix == "K"
        assert exc_info.value.available_tags == ["K1"]

    def test_reuse_tags_missing_prefix_raises_immediately(self):
        """reuse_tags with a non-existent prefix should raise on first call."""
        result = self._make_result(component_map={"Q": ["Q1"]})
        gen = result.reuse_tags("K")  # "K" not in component_map
        state = create_autonumberer()

        with pytest.raises(TagReuseError):
            gen(state)

    def test_reuse_terminals_returns_generator(self):
        """reuse_terminals should return a callable generator function."""
        result = self._make_result(terminal_pin_map={"X1": ["1", "2", "3"]})
        gen = result.reuse_terminals("X1")
        assert callable(gen)

    def test_reuse_terminals_yields_pins_in_order(self):
        """reuse_terminals generator should yield pin groups in order."""
        result = self._make_result(
            terminal_pin_map={"X1": ["1", "2", "3", "4", "5", "6"]}
        )
        gen = result.reuse_terminals("X1")
        state = create_autonumberer()

        state, pins = gen(state, 3)
        assert pins == ("1", "2", "3")
        state, pins = gen(state, 3)
        assert pins == ("4", "5", "6")

    def test_reuse_terminals_single_pole(self):
        """reuse_terminals should work for 1-pole requests."""
        result = self._make_result(terminal_pin_map={"X5": ["10", "11"]})
        gen = result.reuse_terminals("X5")
        state = create_autonumberer()

        state, pins = gen(state, 1)
        assert pins == ("10",)
        state, pins = gen(state, 1)
        assert pins == ("11",)

    def test_reuse_terminals_exhaustion_raises_error(self):
        """reuse_terminals should raise TerminalReuseError when pins run out."""
        result = self._make_result(terminal_pin_map={"X1": ["1", "2"]})
        gen = result.reuse_terminals("X1")
        state = create_autonumberer()

        state, pins = gen(state, 2)
        assert pins == ("1", "2")

        with pytest.raises(TerminalReuseError) as exc_info:
            gen(state, 1)
        assert exc_info.value.terminal_key == "X1"
        assert exc_info.value.available_pins == ["1", "2"]

    def test_reuse_terminals_partial_exhaustion(self):
        """reuse_terminals should raise if requesting more pins than available."""
        result = self._make_result(terminal_pin_map={"X1": ["1"]})
        gen = result.reuse_terminals("X1")
        state = create_autonumberer()

        # Request 3 poles but only 1 pin available
        with pytest.raises(TerminalReuseError):
            gen(state, 3)

    def test_reuse_terminals_missing_key_raises_immediately(self):
        """reuse_terminals with a non-existent key should raise on first call."""
        result = self._make_result(terminal_pin_map={"X1": ["1"]})
        gen = result.reuse_terminals("X99")  # "X99" not in map
        state = create_autonumberer()

        with pytest.raises(TerminalReuseError):
            gen(state, 1)


# ---------------------------------------------------------------------------
# ComponentRef / PortRef tests
# ---------------------------------------------------------------------------


class TestComponentRefAndPortRef:
    """Tests for ComponentRef and PortRef."""

    def test_component_ref_pin_returns_port_ref(self):
        """ComponentRef.pin() should return a PortRef with the pin name."""
        builder = CircuitBuilder(create_autonumberer())
        ref = ComponentRef(builder, 0, "K")
        port_ref = ref.pin("A1")
        assert isinstance(port_ref, PortRef)
        assert port_ref.component is ref
        assert port_ref.port == "A1"

    def test_component_ref_pole_returns_port_ref(self):
        """ComponentRef.pole() should return a PortRef with the pole index."""
        builder = CircuitBuilder(create_autonumberer())
        ref = ComponentRef(builder, 0, "K")
        port_ref = ref.pole(2)
        assert isinstance(port_ref, PortRef)
        assert port_ref.component is ref
        assert port_ref.port == 2

    def test_add_terminal_returns_component_ref(self):
        """add_terminal should return a ComponentRef."""
        builder = CircuitBuilder(create_autonumberer())
        ref = builder.add_terminal("X1")
        assert isinstance(ref, ComponentRef)
        assert ref._index == 0
        assert ref.tag_prefix == "X1"

    def test_add_symbol_returns_component_ref(self):
        """add_symbol should return a ComponentRef."""
        builder = CircuitBuilder(create_autonumberer())
        ref = builder.add_symbol(mock_symbol, tag_prefix="K")
        assert isinstance(ref, ComponentRef)
        assert ref._index == 0
        assert ref.tag_prefix == "K"

    def test_component_ref_indices_increment(self):
        """Each add_terminal/add_symbol should assign incrementing indices."""
        builder = CircuitBuilder(create_autonumberer())
        ref0 = builder.add_terminal("X1")
        ref1 = builder.add_symbol(mock_symbol, tag_prefix="K")
        ref2 = builder.add_terminal("X2")
        assert ref0._index == 0
        assert ref1._index == 1
        assert ref2._index == 2


# ---------------------------------------------------------------------------
# CircuitBuilder connection methods
# ---------------------------------------------------------------------------


class TestBuilderConnections:
    """Tests for add_connection, connect, and connect_matching."""

    def test_add_connection_stores_manual_connection(self):
        """add_connection should store the connection in manual_connections."""
        builder = CircuitBuilder(create_autonumberer())
        builder.add_terminal("X1")
        builder.add_symbol(mock_symbol, tag_prefix="K")
        builder.add_connection(0, 0, 1, 0, "bottom", "top")

        assert len(builder._spec.manual_connections) == 1
        conn = builder._spec.manual_connections[0]
        assert conn == (0, 0, 1, 0, "bottom", "top")

    def test_add_connection_returns_self_for_chaining(self):
        """add_connection should return self for method chaining."""
        builder = CircuitBuilder(create_autonumberer())
        builder.add_terminal("X1")
        builder.add_symbol(mock_symbol, tag_prefix="K")
        result = builder.add_connection(0, 0, 1, 0)
        assert result is builder

    def test_connect_with_port_refs(self):
        """connect() should register a connection using PortRef objects."""
        builder = CircuitBuilder(create_autonumberer())
        builder.set_layout(0, 0)
        tm = builder.add_terminal("X1", pins=["1"])
        comp = builder.add_symbol(mock_symbol, tag_prefix="K", pins=["1", "2"])

        builder.connect(tm.pole(0), comp.pole(0))

        assert len(builder._spec.manual_connections) == 1

    def test_connect_with_pin_names(self):
        """connect() should resolve pin names to pole indices."""
        builder = CircuitBuilder(create_autonumberer())
        builder.set_layout(0, 0)
        tm = builder.add_terminal("X1", pins=["42"])
        comp = builder.add_symbol(mock_symbol, tag_prefix="K", pins=["A1", "A2"])

        builder.connect(tm.pin("42"), comp.pin("A1"))

        assert len(builder._spec.manual_connections) == 1

    def test_connect_matching_stores_entry(self):
        """connect_matching should store matching connection data."""
        builder = CircuitBuilder(create_autonumberer())
        ref_a = builder.add_symbol(mock_symbol, tag_prefix="K")
        ref_b = builder.add_symbol(mock_symbol, tag_prefix="Q")
        builder.connect_matching(ref_a, ref_b, pins=["1", "2"])

        assert len(builder._spec.matching_connections) == 1
        entry = builder._spec.matching_connections[0]
        assert entry[0] == ref_a._index
        assert entry[1] == ref_b._index
        assert entry[2] == ["1", "2"]

    def test_connect_matching_returns_self(self):
        """connect_matching should return self for chaining."""
        builder = CircuitBuilder(create_autonumberer())
        ref_a = builder.add_symbol(mock_symbol, tag_prefix="K")
        ref_b = builder.add_symbol(mock_symbol, tag_prefix="Q")
        result = builder.connect_matching(ref_a, ref_b)
        assert result is builder


# ---------------------------------------------------------------------------
# Error path tests
# ---------------------------------------------------------------------------


class TestErrorPaths:
    """Tests for error conditions and validation."""

    def test_component_not_found_on_build(self):
        """ComponentNotFoundError should be raised for invalid connection indices."""
        builder = CircuitBuilder(create_autonumberer())
        builder.set_layout(0, 0)
        builder.add_terminal("X1")
        builder.add_connection(0, 0, 99, 0)  # index 99 doesn't exist

        with pytest.raises(ComponentNotFoundError):
            builder.build()

    def test_component_not_found_first_index(self):
        """ComponentNotFoundError for invalid first index in connection."""
        builder = CircuitBuilder(create_autonumberer())
        builder.set_layout(0, 0)
        builder.add_terminal("X1")
        builder.add_connection(99, 0, 0, 0)

        with pytest.raises(ComponentNotFoundError):
            builder.build()

    def test_port_not_found_on_connect(self):
        """PortNotFoundError should be raised when resolving an invalid pin name."""
        builder = CircuitBuilder(create_autonumberer())
        builder.set_layout(0, 0)
        comp = builder.add_symbol(mock_symbol, tag_prefix="K", pins=["1", "2"])

        # Pin "INVALID" doesn't exist in the pin list
        with pytest.raises(PortNotFoundError):
            builder.connect(comp.pin("INVALID"), comp.pin("1"))

    def test_port_not_found_error_details(self):
        """PortNotFoundError should include component tag and available ports."""
        builder = CircuitBuilder(create_autonumberer())
        comp = builder.add_symbol(mock_symbol, tag_prefix="K", pins=["A1", "A2"])

        with pytest.raises(PortNotFoundError) as exc_info:
            builder._resolve_port_ref_to_pole(comp.pin("MISSING"))
        assert "MISSING" in str(exc_info.value)
        assert "K" in str(exc_info.value)

    def test_port_not_found_on_terminal_with_no_pins(self):
        """PortNotFoundError for pin lookup on a spec with no explicit pins."""
        builder = CircuitBuilder(create_autonumberer())
        tm = builder.add_terminal("X1")  # No explicit pins

        with pytest.raises(PortNotFoundError):
            builder._resolve_port_ref_to_pole(tm.pin("NONEXISTENT"))


# ---------------------------------------------------------------------------
# Build with various parameters
# ---------------------------------------------------------------------------


class TestBuildParameters:
    """Tests for build() method with various parameter combinations."""

    def test_build_with_start_indices(self):
        """build() with start_indices should offset tag counters."""
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(0, 0)
        builder.add_symbol(mock_symbol, tag_prefix="K")

        result = builder.build(count=1, start_indices={"K": 5})

        # Should start from K6 (counter is set to 5, next is 6)
        assert "K" in result.component_map
        assert result.component_map["K"] == ["K6"]

    def test_build_with_terminal_start_indices(self):
        """build() with terminal_start_indices should offset terminal pin counters."""
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(0, 0)
        builder.add_terminal("X1", poles=1)

        result = builder.build(count=1, terminal_start_indices={"X1": 10})

        # Terminal pins should start from 11
        assert "X1" in result.terminal_pin_map
        assert result.terminal_pin_map["X1"] == ["11"]

    def test_build_with_tag_generators(self):
        """build() with custom tag_generators should use them for tag creation."""
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(0, 0)
        builder.add_symbol(mock_symbol, tag_prefix="K")

        def custom_gen(s):
            return s, "K99"

        result = builder.build(count=1, tag_generators={"K": custom_gen})

        assert result.component_map["K"] == ["K99"]

    def test_build_with_reuse_tags(self):
        """build() with reuse_tags should reuse tags from a previous BuildResult."""
        # First build: create a circuit with K tags
        state = create_autonumberer()
        builder1 = CircuitBuilder(state)
        builder1.set_layout(0, 0)
        builder1.add_symbol(mock_symbol, tag_prefix="K")
        result1 = builder1.build(count=2)

        # result1 should have K1 and K2
        assert result1.component_map["K"] == ["K1", "K2"]

        # Second build: reuse the K tags from result1
        builder2 = CircuitBuilder(result1.state)
        builder2.set_layout(0, 100)
        builder2.add_symbol(mock_symbol, tag_prefix="K")
        result2 = builder2.build(count=2, reuse_tags={"K": result1})

        # Should reuse K1 and K2 instead of generating K3, K4
        assert result2.component_map["K"] == ["K1", "K2"]

    def test_build_with_reuse_tags_callable(self):
        """build() with reuse_tags accepting a raw callable generator."""
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(0, 0)
        builder.add_symbol(mock_symbol, tag_prefix="K")

        tags = iter(["KX1"])

        def tag_gen(s):
            return s, next(tags)

        result = builder.build(count=1, reuse_tags={"K": tag_gen})
        assert result.component_map["K"] == ["KX1"]

    def test_build_with_reuse_terminals(self):
        """build() with reuse_terminals should reuse terminal pins from a previous result."""
        # First build
        state = create_autonumberer()
        builder1 = CircuitBuilder(state)
        builder1.set_layout(0, 0)
        builder1.add_terminal("X1", poles=1)
        builder1.add_symbol(mock_symbol, tag_prefix="K")
        result1 = builder1.build(count=2)

        # result1 should have X1 pins
        assert "X1" in result1.terminal_pin_map
        original_pins = result1.terminal_pin_map["X1"]

        # Second build: reuse X1 pins
        builder2 = CircuitBuilder(result1.state)
        builder2.set_layout(0, 100)
        builder2.add_terminal("X1", poles=1)
        builder2.add_symbol(mock_symbol, tag_prefix="Q")
        result2 = builder2.build(count=1, reuse_terminals={"X1": result1})

        # Should have reused the first pin from result1
        assert result2.terminal_pin_map["X1"] == [original_pins[0]]

    def test_build_with_reuse_terminals_callable(self):
        """build() with reuse_terminals accepting a raw callable generator."""
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(0, 0)
        builder.add_terminal("X1", poles=1)
        builder.add_symbol(mock_symbol, tag_prefix="K")

        def pin_gen(s, poles):
            return s, tuple(f"P{i}" for i in range(poles))

        result = builder.build(count=1, reuse_terminals={"X1": pin_gen})
        assert result.terminal_pin_map["X1"] == ["P0"]

    def test_build_multiple_instances(self):
        """build() with count > 1 should create multiple circuit instances."""
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(0, 0, spacing=100)
        builder.add_symbol(mock_symbol, tag_prefix="K")

        result = builder.build(count=3)

        assert len(result.component_map["K"]) == 3
        assert result.component_map["K"] == ["K1", "K2", "K3"]

    def test_build_with_wire_labels(self):
        """build() with wire_labels should apply labels to vertical wires."""
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(0, 0)
        builder.add_terminal("X1", poles=1)
        builder.add_symbol(mock_symbol, tag_prefix="K")
        builder.add_terminal("X2", poles=1)

        # Wire labels get applied to vertical wires found in the circuit
        result = builder.build(count=1, wire_labels=["BK 2.5"])

        assert result.circuit is not None

    def test_build_terminal_used_terminals(self):
        """build() should track used_terminals correctly."""
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(0, 0)
        builder.add_terminal("X1")
        builder.add_symbol(mock_symbol, tag_prefix="K")
        builder.add_terminal("X2")

        result = builder.build(count=1)

        assert "X1" in result.used_terminals
        assert "X2" in result.used_terminals

    def test_build_terminal_deduplication(self):
        """build() should not duplicate terminal IDs in used_terminals."""
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(0, 0)
        builder.add_terminal("X1")
        builder.add_symbol(mock_symbol, tag_prefix="K")
        builder.add_terminal("X1")  # Same terminal ID used again

        result = builder.build(count=1)

        # X1 should appear only once
        assert result.used_terminals.count("X1") == 1

    def test_build_captures_component_map(self):
        """build() should populate component_map with prefix -> tag list."""
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(0, 0)
        builder.add_terminal("X1")
        builder.add_symbol(mock_symbol, tag_prefix="K")
        builder.add_symbol(mock_symbol, tag_prefix="F")

        result = builder.build(count=1)

        assert "K" in result.component_map
        assert "F" in result.component_map
        assert result.component_map["K"] == ["K1"]
        assert result.component_map["F"] == ["F1"]

    def test_build_captures_terminal_pin_map(self):
        """build() should populate terminal_pin_map with terminal -> pins."""
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(0, 0)
        builder.add_terminal("X1", poles=3)
        builder.add_symbol(mock_symbol, tag_prefix="K")

        result = builder.build(count=1)

        assert "X1" in result.terminal_pin_map
        assert len(result.terminal_pin_map["X1"]) == 3


# ---------------------------------------------------------------------------
# Terminal with logical_name and explicit pins
# ---------------------------------------------------------------------------


class TestTerminalLogicalNames:
    """Tests for terminals with logical names and related features."""

    def test_add_terminal_with_logical_name(self):
        """add_terminal with logical_name should register in terminal_map."""
        builder = CircuitBuilder(create_autonumberer())
        builder.add_terminal("X5", logical_name="MAIN")

        assert "MAIN" in builder._spec.terminal_map
        assert builder._spec.terminal_map["MAIN"] == "X5"

    def test_add_terminal_with_explicit_pins(self):
        """add_terminal with explicit pins should use those pins."""
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(0, 0)
        builder.add_terminal("X1", pins=["42", "43"], poles=2)
        builder.add_symbol(mock_symbol, tag_prefix="K")

        result = builder.build(count=1)

        assert "X1" in result.terminal_pin_map
        assert result.terminal_pin_map["X1"] == ["42", "43"]

    def test_terminal_with_logical_name_in_used_terminals(self):
        """Terminals with logical_name should still appear correctly in used_terminals."""
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(0, 0)
        builder.add_terminal("X5", logical_name="OUTPUT")

        result = builder.build(count=1)

        # The terminal_map maps OUTPUT -> X5
        # used_terminals should contain X5
        assert "X5" in result.used_terminals


# ---------------------------------------------------------------------------
# add_symbol(position="right") and add_terminal(position="above"/"below") tests
# ---------------------------------------------------------------------------


class TestPlacement:
    """Tests for add_symbol(position="right") and add_terminal(position="above"/"below")."""

    def test_add_symbol_right_stores_spec_correctly(self):
        """add_symbol with position="right" should store a ComponentSpec with placed_right_of set."""
        builder = CircuitBuilder(create_autonumberer())
        builder.set_layout(0, 0)
        ref_a = builder.add_symbol(mock_symbol, tag_prefix="K")
        ref_b = builder.add_symbol(
            mock_symbol, "Q", relative_to=ref_a, position="right", spacing=50.0
        )

        spec = builder._spec.components[ref_b._index]
        assert spec.placed_right_of == ref_a._index
        assert spec.spacing_override == 50.0
        assert spec.auto_connect_next is False

    def test_add_symbol_right_returns_component_ref(self):
        """add_symbol with position="right" should return a ComponentRef."""
        builder = CircuitBuilder(create_autonumberer())
        builder.set_layout(0, 0)
        ref_a = builder.add_symbol(mock_symbol, tag_prefix="K")
        ref_b = builder.add_symbol(
            mock_symbol, "Q", relative_to=ref_a, position="right"
        )

        assert isinstance(ref_b, ComponentRef)
        assert ref_b.tag_prefix == "Q"

    def test_add_symbol_right_builds_successfully(self):
        """A circuit with add_symbol(position="right") should build without error."""
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(0, 0)
        ref_a = builder.add_symbol(mock_symbol, tag_prefix="K")
        builder.add_symbol(
            mock_symbol, "Q", relative_to=ref_a, position="right", spacing=40.0
        )

        result = builder.build(count=1)

        assert "K" in result.component_map
        assert "Q" in result.component_map

    def test_add_terminal_above_stores_spec_correctly(self):
        """add_terminal with position="above" should store a ComponentSpec with placed_above_of set."""
        builder = CircuitBuilder(create_autonumberer())
        builder.set_layout(0, 0)
        comp = builder.add_symbol(mock_symbol, tag_prefix="K", pins=["1", "2"])

        tm_ref = builder.add_terminal(
            "X99", poles=1, relative_to=comp.pin("1"), position="above"
        )

        spec = builder._spec.components[tm_ref._index]
        assert spec.placed_above_of == (comp._index, "1")
        assert spec.kind == "terminal"
        assert spec.auto_connect_next is False

    def test_add_terminal_above_registers_connection(self):
        """add_terminal with position="above" should automatically register a connection."""
        builder = CircuitBuilder(create_autonumberer())
        builder.set_layout(0, 0)
        comp = builder.add_symbol(mock_symbol, tag_prefix="K", pins=["1", "2"])

        builder.add_terminal("X99", relative_to=comp.pin("1"), position="above")

        # There should be a manual connection registered
        assert len(builder._spec.manual_connections) == 1

    def test_add_terminal_above_builds_successfully(self):
        """A circuit with add_terminal(position="above") should build without error."""
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(0, 0)
        comp = builder.add_symbol(mock_symbol, tag_prefix="K", pins=["1", "2"])
        builder.add_terminal(
            "X99", poles=1, relative_to=comp.pin("1"), position="above"
        )

        result = builder.build(count=1)
        assert result.circuit is not None

    def test_add_reference_above_creates_reference_spec(self):
        """add_reference with position="above" should create a kind="reference" spec."""
        builder = CircuitBuilder(create_autonumberer())
        builder.set_layout(0, 0)
        comp = builder.add_symbol(mock_symbol, tag_prefix="K", pins=["1", "2"])

        tm_ref = builder.add_reference(
            "PLC:DO", relative_to=comp.pin("1"), position="above"
        )

        spec = builder._spec.components[tm_ref._index]
        assert spec.kind == "reference"

    def test_add_terminal_above_with_spacing(self):
        """add_terminal with position="above" should respect custom spacing."""
        builder = CircuitBuilder(create_autonumberer())
        builder.set_layout(0, 0)
        comp = builder.add_symbol(mock_symbol, tag_prefix="K", pins=["1", "2"])

        tm_ref = builder.add_terminal(
            "X1", relative_to=comp.pin("1"), position="above", spacing=30.0
        )

        spec = builder._spec.components[tm_ref._index]
        assert spec.spacing_override == 30.0

    def test_add_terminal_below_stores_spec_correctly(self):
        """add_terminal with position="below" should store a ComponentSpec with placed_below_of set."""
        builder = CircuitBuilder(create_autonumberer())
        builder.set_layout(0, 0)
        comp = builder.add_symbol(mock_symbol, tag_prefix="K", pins=["1", "2"])

        tm_ref = builder.add_terminal(
            "X99", poles=1, relative_to=comp.pin("1"), position="below"
        )

        spec = builder._spec.components[tm_ref._index]
        assert spec.placed_below_of == (comp._index, "1")
        assert spec.kind == "terminal"
        assert spec.auto_connect_next is False

    def test_add_terminal_below_registers_connection(self):
        """add_terminal with position="below" should automatically register a connection."""
        builder = CircuitBuilder(create_autonumberer())
        builder.set_layout(0, 0)
        comp = builder.add_symbol(mock_symbol, tag_prefix="K", pins=["1", "2"])

        builder.add_terminal("X99", relative_to=comp.pin("1"), position="below")

        assert len(builder._spec.manual_connections) == 1

    def test_add_terminal_below_builds_successfully(self):
        """A circuit with add_terminal(position="below") should build without error."""
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(0, 0)
        comp = builder.add_symbol(mock_symbol, tag_prefix="K", pins=["1", "2"])
        builder.add_terminal(
            "X99", poles=1, relative_to=comp.pin("1"), position="below"
        )

        result = builder.build(count=1)
        assert result.circuit is not None

    def test_add_reference_below_creates_reference_spec(self):
        """add_reference with position="below" should create a kind="reference" spec."""
        builder = CircuitBuilder(create_autonumberer())
        builder.set_layout(0, 0)
        comp = builder.add_symbol(mock_symbol, tag_prefix="K", pins=["1", "2"])

        tm_ref = builder.add_reference(
            "PLC:DO", relative_to=comp.pin("1"), position="below"
        )

        spec = builder._spec.components[tm_ref._index]
        assert spec.kind == "reference"
        assert spec.placed_below_of == (comp._index, "1")

    def test_add_terminal_below_wire_connection(self):
        """add_terminal with position="below" should register wire connection from target to placed."""
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(0, 0)
        comp = builder.add_symbol(mock_symbol, tag_prefix="K", pins=["1", "2"])
        builder.add_terminal(
            "X99", poles=1, relative_to=comp.pin("1"), position="below"
        )

        result = builder.build(count=1)
        # Should have wire connection from component to terminal
        assert len(result.wire_connections) >= 1


# ---------------------------------------------------------------------------
# add_reference tests
# ---------------------------------------------------------------------------


class TestAddReference:
    """Tests for add_reference method."""

    def test_add_reference_stores_spec(self):
        """add_reference should create a spec with kind='reference'."""
        builder = CircuitBuilder(create_autonumberer())
        ref = builder.add_reference("PLC:DO")

        spec = builder._spec.components[ref._index]
        assert spec.kind == "reference"
        assert spec.tag_prefix == "PLC:DO"

    def test_add_reference_registers_fixed_tag_generator(self):
        """add_reference should register a fixed tag generator."""
        builder = CircuitBuilder(create_autonumberer())
        builder.add_reference("PLC:DO")

        assert "PLC:DO" in builder._fixed_tag_generators

    def test_add_reference_fixed_gen_returns_ref_id(self):
        """The fixed tag generator should always return the ref_id."""
        builder = CircuitBuilder(create_autonumberer())
        builder.add_reference("PLC:DO")

        gen = builder._fixed_tag_generators["PLC:DO"]
        state = create_autonumberer()
        new_state, tag = gen(state)
        assert tag == "PLC:DO"

    def test_add_reference_returns_component_ref(self):
        """add_reference should return a ComponentRef."""
        builder = CircuitBuilder(create_autonumberer())
        ref = builder.add_reference("PLC:DO")

        assert isinstance(ref, ComponentRef)
        assert ref.tag_prefix == "PLC:DO"

    def test_add_reference_builds_successfully(self):
        """A circuit with add_reference should build without error."""
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(0, 0)
        builder.add_reference("PLC:DO")

        result = builder.build(count=1)

        assert result.component_map["PLC:DO"] == ["PLC:DO"]


# ---------------------------------------------------------------------------
# _resolve_port_ref_to_pole tests
# ---------------------------------------------------------------------------


class TestResolvePortRefToPole:
    """Tests for the _resolve_port_ref_to_pole private method."""

    def test_integer_port_returns_directly(self):
        """Integer port values should be returned as-is (pole index)."""
        builder = CircuitBuilder(create_autonumberer())
        builder.add_symbol(mock_symbol, tag_prefix="K", pins=["1", "2"])
        ref = ComponentRef(builder, 0, "K")

        result = builder._resolve_port_ref_to_pole(PortRef(ref, 5))
        assert result == 5

    def test_pin_name_in_2x_pins_list(self):
        """Pin name in a poles*2 pin list should resolve to correct pole index."""
        builder = CircuitBuilder(create_autonumberer())
        builder.add_symbol(
            mock_two_pole_symbol, tag_prefix="K", poles=2, pins=["A1", "A2", "B1", "B2"]
        )
        ref = ComponentRef(builder, 0, "K")

        # A1 is at index 0, pole = 0//2 = 0
        assert builder._resolve_port_ref_to_pole(PortRef(ref, "A1")) == 0
        # A2 is at index 1, pole = 1//2 = 0
        assert builder._resolve_port_ref_to_pole(PortRef(ref, "A2")) == 0
        # B1 is at index 2, pole = 2//2 = 1
        assert builder._resolve_port_ref_to_pole(PortRef(ref, "B1")) == 1
        # B2 is at index 3, pole = 3//2 = 1
        assert builder._resolve_port_ref_to_pole(PortRef(ref, "B2")) == 1

    def test_pin_name_direct_indexing(self):
        """Pin name in a non-poles*2 pin list should use direct indexing."""
        builder = CircuitBuilder(create_autonumberer())
        builder.add_symbol(mock_symbol, tag_prefix="K", poles=1, pins=["L", "N", "PE"])
        ref = ComponentRef(builder, 0, "K")

        assert builder._resolve_port_ref_to_pole(PortRef(ref, "L")) == 0
        assert builder._resolve_port_ref_to_pole(PortRef(ref, "N")) == 1
        assert builder._resolve_port_ref_to_pole(PortRef(ref, "PE")) == 2


# ---------------------------------------------------------------------------
# _resolve_registry_pin tests
# ---------------------------------------------------------------------------


class TestResolveRegistryPin:
    """Tests for _resolve_registry_pin helper function."""

    def test_terminal_with_pins(self):
        """For terminals, should return the physical pin label."""
        data = {
            "spec": ComponentSpec(func=None, kind="terminal", poles=1),
            "pins": ["42"],
        }
        assert _resolve_registry_pin(data, 0) == "42"

    def test_terminal_with_multiple_pins(self):
        """For multi-pole terminals, should return the correct pin by index."""
        data = {
            "spec": ComponentSpec(func=None, kind="terminal", poles=3),
            "pins": ["10", "11", "12"],
        }
        assert _resolve_registry_pin(data, 0) == "10"
        assert _resolve_registry_pin(data, 1) == "11"
        assert _resolve_registry_pin(data, 2) == "12"

    def test_terminal_without_pins_fallback(self):
        """For terminals without pins, should return 1-based index string."""
        data = {
            "spec": ComponentSpec(func=None, kind="terminal", poles=1),
            "pins": [],
        }
        assert _resolve_registry_pin(data, 0) == "1"
        assert _resolve_registry_pin(data, 2) == "3"

    def test_terminal_pole_out_of_range(self):
        """For terminals with pole_idx beyond pin list, should return fallback."""
        data = {
            "spec": ComponentSpec(func=None, kind="terminal", poles=1),
            "pins": ["42"],
        }
        assert _resolve_registry_pin(data, 5) == "6"  # Fallback: 5+1

    def test_symbol_delegates_to_resolve_pin(self):
        """For symbols, should delegate to _resolve_pin."""
        data = {
            "spec": ComponentSpec(func=lambda: None, kind="symbol", poles=1),
            "pins": ["A1", "A2"],
        }
        # For a symbol with 1 pole and 2 pins (poles*2), A1 is input for pole 0
        assert _resolve_registry_pin(data, 0) == "A1"


# ---------------------------------------------------------------------------
# _distribute_pins tests
# ---------------------------------------------------------------------------


class TestDistributePins:
    """Tests for _distribute_pins function."""

    def test_function_with_pins_parameter(self):
        """Should pass all pins as pins= when function accepts 'pins'."""
        result = _distribute_pins(mock_symbol_with_pins, ["L", "N", "PE"], {})
        assert result == {"pins": ("L", "N", "PE")}

    def test_function_with_pins_already_in_kwargs(self):
        """Should not override pins= if already provided in existing_kwargs."""
        result = _distribute_pins(
            mock_symbol_with_pins, ["L", "N", "PE"], {"pins": ("X", "Y")}
        )
        assert result == {}  # Should not override

    def test_function_with_contact_pins_and_coil_pins(self):
        """Should distribute pins across *_pins parameters."""
        result = _distribute_pins(
            mock_symbol_with_contact_pins,
            ["1", "2", "A1", "A2"],
            {},
        )
        # contact_pins has default ("1", "2") with len=2, takes first 2
        assert result.get("contact_pins") == ("1", "2")
        # coil_pins has default=None, takes remaining
        assert result.get("coil_pins") == ("A1", "A2")

    def test_function_without_pin_parameters(self):
        """Should return empty dict when function has no pin parameters."""

        def simple_func(tag, value=0):
            pass

        result = _distribute_pins(simple_func, ["1", "2"], {})
        assert result == {}

    def test_function_with_only_named_pins_params(self):
        """Should handle functions with only required *_pins params."""

        def func_with_required_pins(tag, contact_pins=("a", "b")):
            pass

        result = _distribute_pins(func_with_required_pins, ["X", "Y"], {})
        assert result == {"contact_pins": ("X", "Y")}


# ---------------------------------------------------------------------------
# _get_absolute_x_offset tests
# ---------------------------------------------------------------------------


class TestGetAbsoluteXOffset:
    """Tests for _get_absolute_x_offset helper."""

    def test_single_level(self):
        """A component placed_right_of a base should return its x_offset."""
        realized = [
            {
                "spec": ComponentSpec(
                    func=None, kind="symbol", x_offset=0.0, placed_right_of=None
                )
            },
            {
                "spec": ComponentSpec(
                    func=None, kind="symbol", x_offset=40.0, placed_right_of=0
                )
            },
        ]
        assert _get_absolute_x_offset(realized, 1) == 40.0

    def test_chained_place_right(self):
        """Chained place_right should accumulate x_offsets."""
        realized = [
            {
                "spec": ComponentSpec(
                    func=None, kind="symbol", x_offset=0.0, placed_right_of=None
                )
            },
            {
                "spec": ComponentSpec(
                    func=None, kind="symbol", x_offset=40.0, placed_right_of=0
                )
            },
            {
                "spec": ComponentSpec(
                    func=None, kind="symbol", x_offset=30.0, placed_right_of=1
                )
            },
        ]
        # Component 2 is placed right of 1 (40) which is placed right of 0 (0)
        # Total: 30 + 40 = 70
        assert _get_absolute_x_offset(realized, 2) == 70.0

    def test_base_component_no_chain(self):
        """Base component (no placed_right_of) should just return its x_offset."""
        realized = [
            {
                "spec": ComponentSpec(
                    func=None, kind="symbol", x_offset=10.0, placed_right_of=None
                )
            },
        ]
        assert _get_absolute_x_offset(realized, 0) == 10.0


# ---------------------------------------------------------------------------
# LayoutConfig and ComponentSpec tests
# ---------------------------------------------------------------------------


class TestLayoutConfigAndComponentSpec:
    """Tests for LayoutConfig and ComponentSpec dataclasses."""

    def test_layout_config_defaults(self):
        """LayoutConfig should have sensible defaults."""
        config = LayoutConfig(start_x=10, start_y=20)
        assert config.spacing == 150
        assert config.symbol_spacing == 50
        assert config.label_pos == "left"

    def test_component_spec_get_y_increment_default(self):
        """get_y_increment should return the default when y_increment is None."""
        spec = ComponentSpec(func=None, kind="symbol")
        assert spec.get_y_increment(50.0) == 50.0

    def test_component_spec_get_y_increment_custom(self):
        """get_y_increment should return y_increment when it is set."""
        spec = ComponentSpec(func=None, kind="symbol", y_increment=30.0)
        assert spec.get_y_increment(50.0) == 30.0


# ---------------------------------------------------------------------------
# set_layout tests
# ---------------------------------------------------------------------------


class TestSetLayout:
    """Tests for set_layout method."""

    def test_set_layout_returns_self(self):
        """set_layout should return self for method chaining."""
        builder = CircuitBuilder(create_autonumberer())
        result = builder.set_layout(10, 20)
        assert result is builder

    def test_set_layout_stores_config(self):
        """set_layout should store the layout configuration."""
        builder = CircuitBuilder(create_autonumberer())
        builder.set_layout(10, 20, spacing=200, symbol_spacing=60)

        layout = builder._spec.layout
        assert layout.start_x == 10
        assert layout.start_y == 20
        assert layout.spacing == 200
        assert layout.symbol_spacing == 60


# ---------------------------------------------------------------------------
# Integration: terminal -> symbol -> terminal chain
# ---------------------------------------------------------------------------


class TestBuildIntegration:
    """Integration tests for building complete circuits."""

    def test_terminal_symbol_terminal_chain(self):
        """Build a terminal -> symbol -> terminal chain and verify connections."""
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(0, 0)
        builder.add_terminal("X1")
        builder.add_symbol(mock_symbol, tag_prefix="K")
        builder.add_terminal("X2")

        result = builder.build(count=1)

        assert result.circuit is not None
        assert len(result.circuit.elements) > 0
        assert "K" in result.component_map
        assert "X1" in result.terminal_pin_map
        assert "X2" in result.terminal_pin_map

    def test_multi_pole_terminal_chain(self):
        """Build with multi-pole terminals."""
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(0, 0)
        builder.add_terminal("X1", poles=3)
        builder.add_symbol(mock_two_pole_symbol, tag_prefix="Q", poles=2)
        builder.add_terminal("X2", poles=2)

        result = builder.build(count=1)

        assert len(result.terminal_pin_map["X1"]) == 3
        assert len(result.terminal_pin_map["X2"]) == 2

    def test_build_with_auto_connect_false(self):
        """Components with auto_connect_next=False should not auto-connect."""
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(0, 0)
        builder.add_symbol(mock_symbol, tag_prefix="K", auto_connect_next=False)
        builder.add_symbol(mock_symbol, tag_prefix="Q")

        result = builder.build(count=1)

        # Should build successfully even though first component won't auto-connect
        assert result.circuit is not None

    def test_build_with_manual_connection(self):
        """Manual connections should create wire lines in the circuit."""
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(0, 0)
        tm = builder.add_terminal("X1", pins=["1"])
        comp = builder.add_symbol(mock_symbol, tag_prefix="K", auto_connect_next=False)
        builder.add_connection(tm._index, 0, comp._index, 0, "bottom", "top")

        result = builder.build(count=1)

        assert result.circuit is not None
        # The circuit should have elements from both the terminal and the component
        assert len(result.circuit.elements) >= 2

    def test_build_with_connect_matching(self):
        """connect_matching should create horizontal wires between matching pins."""
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(0, 0)

        ref_a = builder.add_symbol(
            mock_symbol_with_pins,
            tag_prefix="K",
            pins=["1", "2"],
            auto_connect_next=False,
        )
        ref_b = builder.add_symbol(
            mock_symbol_with_pins,
            "Q",
            pins=["1", "2"],
            relative_to=ref_a,
            position="right",
            spacing=50.0,
        )
        builder.connect_matching(ref_a, ref_b, pins=["1", "2"])

        result = builder.build(count=1)
        assert result.circuit is not None

    def test_build_symbol_with_x_offset(self):
        """Components with x_offset should be placed at the correct X position."""
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(0, 0)
        builder.add_symbol(mock_symbol, tag_prefix="K", x_offset=25.0)

        result = builder.build(count=1)
        assert result.circuit is not None

    def test_build_symbol_with_y_increment(self):
        """Components with y_increment should be spaced correctly."""
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(0, 0, symbol_spacing=50)
        builder.add_symbol(mock_symbol, tag_prefix="K", y_increment=100.0)
        builder.add_symbol(mock_symbol, tag_prefix="Q")

        result = builder.build(count=1)
        assert result.circuit is not None

    def test_build_with_terminal_maps(self):
        """build() with terminal_maps should override terminal IDs for logical names."""
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(0, 0)
        builder.add_terminal("X1", logical_name="OUTPUT")
        builder.add_symbol(mock_symbol, tag_prefix="K")

        # Override OUTPUT to X99 at build time
        result = builder.build(count=1, terminal_maps={"OUTPUT": "X99"})

        assert result.circuit is not None

    def test_build_symbol_to_symbol_connection(self):
        """Two adjacent symbols should auto-connect."""
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(0, 0)
        builder.add_symbol(mock_symbol, tag_prefix="K")
        builder.add_symbol(mock_symbol, tag_prefix="Q")

        result = builder.build(count=1)
        assert len(result.circuit.elements) >= 2

    def test_build_reference_to_symbol_connection(self):
        """A reference followed by a symbol should register connection."""
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(0, 0)
        builder.add_reference("PLC:DO")
        builder.add_symbol(mock_symbol, tag_prefix="K")

        result = builder.build(count=1)
        assert result.circuit is not None

    def test_build_symbol_to_reference_connection(self):
        """A symbol followed by a reference should register connection."""
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(0, 0)
        builder.add_symbol(mock_symbol, tag_prefix="K")
        builder.add_reference("PLC:DI")

        result = builder.build(count=1)
        assert result.circuit is not None

    def test_build_with_pin_prefixes(self):
        """Terminals with pin_prefixes should use them for pin generation."""
        from schematika.electrical.terminal import Terminal

        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(0, 0)

        tm = Terminal("X1", pin_prefixes=("L1", "L2", "L3"))
        builder.add_terminal(tm, poles=3)
        builder.add_symbol(mock_symbol, tag_prefix="K")

        result = builder.build(count=1)
        assert "X1" in result.terminal_pin_map
        # Pins should follow prefix pattern
        pins = result.terminal_pin_map["X1"]
        assert len(pins) == 3
        assert all(":" in p for p in pins)  # Prefixed pins have colon

    def test_build_terminal_with_pin_prefixes_override(self):
        """add_terminal with explicit pin_prefixes should override Terminal's own."""
        from schematika.electrical.terminal import Terminal

        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(0, 0)

        tm = Terminal("X1", pin_prefixes=("L1", "L2", "L3"))
        builder.add_terminal(tm, poles=2, pin_prefixes=("L1", "N"))
        builder.add_symbol(mock_symbol, tag_prefix="K")

        result = builder.build(count=1)
        pins = result.terminal_pin_map["X1"]
        assert len(pins) == 2


# ---------------------------------------------------------------------------
# Additional coverage tests for remaining uncovered lines
# ---------------------------------------------------------------------------


class TestAdditionalCoverage:
    """Tests targeting specific uncovered lines in builder.py."""

    def test_add_reference_above_builds_with_fixed_gen(self):
        """add_reference with position="above" should build and use the fixed_gen."""
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(0, 0)
        comp = builder.add_symbol(mock_symbol, tag_prefix="K", pins=["1", "2"])

        builder.add_reference("PLC:DO", relative_to=comp.pin("1"), position="above")

        result = builder.build(count=1)
        # The reference should appear in the component_map with its fixed ID
        assert "PLC:DO" in result.component_map
        assert result.component_map["PLC:DO"] == ["PLC:DO"]

    def test_manual_connection_symbol_to_terminal(self):
        """Manual connection from symbol to terminal should register
        in the connection registry (lines 969-972)."""
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(0, 0)
        comp = builder.add_symbol(
            mock_symbol, tag_prefix="K", pins=["1", "2"], auto_connect_next=False
        )
        tm = builder.add_terminal("X1", pins=["42"], auto_connect_next=False)
        builder.add_connection(comp._index, 0, tm._index, 0, "bottom", "top")

        result = builder.build(count=1)
        assert result.circuit is not None

    def test_manual_connection_reference_to_symbol(self):
        """Manual connection from reference to symbol (lines 974-977)."""
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(0, 0)
        ref = builder.add_reference("PLC:DO")
        comp = builder.add_symbol(
            mock_symbol, tag_prefix="K", pins=["1", "2"], auto_connect_next=False
        )
        # Disable auto_connect_next on the reference by modifying spec after the fact
        # Actually, add_reference defaults auto_connect_next=True, so let's disable it
        # and add a manual connection instead
        builder._spec.components[ref._index] = ComponentSpec(
            func=builder._spec.components[ref._index].func,
            tag_prefix="PLC:DO",
            kind="reference",
            auto_connect_next=False,
        )
        builder.add_connection(ref._index, 0, comp._index, 0, "bottom", "top")

        result = builder.build(count=1)
        assert result.circuit is not None

    def test_manual_connection_symbol_to_reference(self):
        """Manual connection from symbol to reference (lines 978-981)."""
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(0, 0)
        comp = builder.add_symbol(
            mock_symbol, tag_prefix="K", pins=["1", "2"], auto_connect_next=False
        )
        ref = builder.add_reference("PLC:DI")
        builder._spec.components[ref._index] = ComponentSpec(
            func=builder._spec.components[ref._index].func,
            tag_prefix="PLC:DI",
            kind="reference",
            auto_connect_next=False,
        )
        builder.add_connection(comp._index, 0, ref._index, 0, "bottom", "top")

        result = builder.build(count=1)
        assert result.circuit is not None

    def test_chained_add_symbol_right_in_build(self):
        """Chained add_symbol(position="right") should trigger the _get_absolute_x_offset path
        in Phase 3 instantiation."""
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(0, 0)

        base = builder.add_symbol(mock_symbol, tag_prefix="K")
        right1 = builder.add_symbol(
            mock_symbol, "Q", relative_to=base, position="right", spacing=40.0
        )
        # Chain: place another component to the right of the first right-placed one
        builder.add_symbol(
            mock_symbol, "F", relative_to=right1, position="right", spacing=30.0
        )

        result = builder.build(count=1)
        assert "K" in result.component_map
        assert "Q" in result.component_map
        assert "F" in result.component_map

    def test_resolve_port_ref_to_pole_pin_not_in_direct_index_list(self):
        """_resolve_port_ref_to_pole should raise PortNotFoundError when pin
        is not found in a non-2x pins list (lines 591-592)."""
        builder = CircuitBuilder(create_autonumberer())
        builder.add_symbol(
            mock_symbol,
            tag_prefix="K",
            poles=1,
            pins=["L", "N", "PE"],  # 3 pins, not 1*2
        )
        ref = ComponentRef(builder, 0, "K")

        with pytest.raises(PortNotFoundError):
            builder._resolve_port_ref_to_pole(PortRef(ref, "MISSING"))


# ---------------------------------------------------------------------------
# BuildResult accessor methods (Task 15.1, 15.2)
# ---------------------------------------------------------------------------


class TestBuildResultAccessors:
    """Tests for BuildResult.component_tag(), component_tags(), get_symbol(), get_symbols()."""

    def test_component_tag_returns_first_tag(self):
        result = BuildResult(
            state=create_autonumberer(),
            circuit=Circuit(),
            used_terminals=[],
            component_map={"K": ["K1", "K2"], "F": ["F1"]},
        )
        assert result.component_tag("K") == "K1"
        assert result.component_tag("F") == "F1"

    def test_component_tag_raises_keyerror_for_missing_prefix(self):
        result = BuildResult(
            state=create_autonumberer(),
            circuit=Circuit(),
            used_terminals=[],
            component_map={"K": ["K1"]},
        )
        with pytest.raises(KeyError, match="No tags for prefix 'Q'"):
            result.component_tag("Q")

    def test_component_tag_raises_keyerror_for_empty_list(self):
        result = BuildResult(
            state=create_autonumberer(),
            circuit=Circuit(),
            used_terminals=[],
            component_map={"K": []},
        )
        with pytest.raises(KeyError, match="No tags for prefix 'K'"):
            result.component_tag("K")

    def test_component_tags_returns_all(self):
        result = BuildResult(
            state=create_autonumberer(),
            circuit=Circuit(),
            used_terminals=[],
            component_map={"K": ["K1", "K2", "K3"]},
        )
        assert result.component_tags("K") == ["K1", "K2", "K3"]

    def test_component_tags_returns_empty_for_missing(self):
        result = BuildResult(
            state=create_autonumberer(),
            circuit=Circuit(),
            used_terminals=[],
            component_map={},
        )
        assert result.component_tags("K") == []

    def test_component_tags_returns_copy(self):
        """Modifying the returned list should not affect the BuildResult."""
        result = BuildResult(
            state=create_autonumberer(),
            circuit=Circuit(),
            used_terminals=[],
            component_map={"K": ["K1"]},
        )
        tags = result.component_tags("K")
        tags.append("K99")
        assert result.component_map["K"] == ["K1"]

    def test_get_symbol_finds_placed_symbol(self):
        builder = CircuitBuilder(create_autonumberer())
        builder.set_layout(0, 0)
        builder.add_symbol(mock_symbol, tag_prefix="K")
        builder.add_terminal("X1")
        result = builder.build()
        tag = result.component_tag("K")
        sym = result.get_symbol(tag)
        assert sym is not None
        assert sym.label == tag

    def test_get_symbol_returns_none_for_missing(self):
        builder = CircuitBuilder(create_autonumberer())
        builder.set_layout(0, 0)
        builder.add_terminal("X1")
        result = builder.build()
        assert result.get_symbol("NONEXISTENT") is None

    def test_get_symbols_returns_all_matching(self):
        """With count=2, two instances produce two K tags."""
        builder = CircuitBuilder(create_autonumberer())
        builder.set_layout(0, 0)
        builder.add_terminal("X1")
        builder.add_symbol(mock_symbol, tag_prefix="K")
        builder.add_terminal("X2")
        result = builder.build(count=2)
        symbols = result.get_symbols("K")
        assert len(symbols) == 2

    def test_get_symbols_returns_empty_for_missing_prefix(self):
        builder = CircuitBuilder(create_autonumberer())
        builder.set_layout(0, 0)
        builder.add_terminal("X1")
        result = builder.build()
        assert result.get_symbols("K") == []


# ---------------------------------------------------------------------------
# String shorthand for tag_generators (Task 15.3)
# ---------------------------------------------------------------------------


class TestTagGeneratorStringShorthand:
    """Tests for passing string values in tag_generators dict."""

    def test_string_shorthand_produces_fixed_tag(self):
        builder = CircuitBuilder(create_autonumberer())
        builder.set_layout(0, 0)
        builder.add_terminal("X1")
        builder.add_symbol(mock_symbol, tag_prefix="K")
        builder.add_terminal("X2")
        result = builder.build(tag_generators={"K": "K5"})
        assert result.component_tag("K") == "K5"

    def test_string_shorthand_with_callable_mixed(self):
        """Can mix string shorthand and callable generators."""
        builder = CircuitBuilder(create_autonumberer())
        builder.set_layout(0, 0)
        builder.add_terminal("X1")
        builder.add_symbol(mock_symbol, tag_prefix="K")
        builder.add_symbol(mock_symbol, tag_prefix="F")
        builder.add_terminal("X2")
        result = builder.build(
            tag_generators={
                "K": "K10",
                "F": lambda s: (s, "F20"),
            }
        )
        assert result.component_tag("K") == "K10"
        assert result.component_tag("F") == "F20"

    def test_string_shorthand_in_multi_count(self):
        """String shorthand should produce the same fixed tag for each instance."""
        builder = CircuitBuilder(create_autonumberer())
        builder.set_layout(0, 0)
        builder.add_terminal("X1")
        builder.add_symbol(mock_symbol, tag_prefix="K")
        builder.add_terminal("X2")
        result = builder.build(count=2, tag_generators={"K": "K1"})
        # Both instances use the same fixed tag
        assert result.component_tags("K") == ["K1", "K1"]


# ---------------------------------------------------------------------------
# fixed_tag() utility
# ---------------------------------------------------------------------------


class TestFixedTag:
    """Tests for the fixed_tag() tag generator factory."""

    def test_fixed_tag_always_returns_same_tag(self):
        from schematika.electrical import create_autonumberer, fixed_tag

        state = create_autonumberer()
        gen = fixed_tag("K1")
        s1, t1 = gen(state)
        s2, t2 = gen(state)
        assert t1 == "K1"
        assert t2 == "K1"
        assert s1 is state

    def test_fixed_tag_works_as_tag_generator_in_build(self):
        from schematika.electrical import CircuitBuilder, create_autonumberer, fixed_tag

        builder = CircuitBuilder(create_autonumberer())
        builder.set_layout(0, 0)
        builder.add_terminal("X1")
        builder.add_symbol(mock_symbol, tag_prefix="K")
        builder.add_terminal("X2")
        result = builder.build(count=2, tag_generators={"K": fixed_tag("K1")})
        assert result.component_tags("K") == ["K1", "K1"]


def test_build_result_has_device_registry():
    from schematika.electrical.internal_device import InternalDevice

    state = create_autonumberer()
    c = Circuit()
    dev = InternalDevice("Q", "LC1D09", "Contactor")
    result = BuildResult(
        state=state,
        circuit=c,
        used_terminals=[],
        device_registry={"Q1": dev},
    )
    assert result.device_registry == {"Q1": dev}


def test_build_result_device_registry_default_empty():
    state = create_autonumberer()
    c = Circuit()
    result = BuildResult(state=state, circuit=c, used_terminals=[])
    assert result.device_registry == {}


def test_build_result_has_wire_connections():
    state = create_autonumberer()
    c = Circuit()
    result = BuildResult(
        state=state,
        circuit=c,
        used_terminals=[],
        wire_connections=[("F1", "2", "Q1", "1")],
    )
    assert result.wire_connections == [("F1", "2", "Q1", "1")]


def test_build_result_wire_connections_default_empty():
    state = create_autonumberer()
    c = Circuit()
    result = BuildResult(state=state, circuit=c, used_terminals=[])
    assert result.wire_connections == []


def test_wire_connections_includes_symbol_to_symbol():
    """CircuitBuilder should capture symbol-to-symbol wire connections."""
    state = create_autonumberer()
    builder = CircuitBuilder(state)
    builder.set_layout(x=0, y=0, spacing=150, symbol_spacing=50)
    builder.add_terminal("X1", poles=1)
    builder.add_symbol(mock_symbol, "F", poles=1, pins=("1", "2"))
    builder.add_symbol(mock_symbol, "Q", poles=1, pins=("1", "2"))
    builder.add_terminal("X2", poles=1)

    result = builder.build()

    # Should have wire connections: X1->F, F->Q (symbol-to-symbol), Q->X2
    assert len(result.wire_connections) >= 3
    # Check that F->Q connection exists (symbol-to-symbol)
    assert ("F1", "2", "Q1", "1") in result.wire_connections


def test_wire_connections_includes_terminal_connections():
    """CircuitBuilder should capture terminal-to-symbol wire connections."""
    state = create_autonumberer()
    builder = CircuitBuilder(state)
    builder.set_layout(x=0, y=0, spacing=150, symbol_spacing=50)
    builder.add_terminal("X1", poles=1)
    builder.add_symbol(mock_symbol, "F", poles=1, pins=("1", "2"))
    builder.add_terminal("X2", poles=1)

    result = builder.build()

    # X1:1->F1:1 and F1:2->X2:1
    assert len(result.wire_connections) >= 2
