"""Unit tests for system/connection_registry.py.

Covers:
- TerminalRegistry.add_connection / add_connections
- log_connection (functional helper)
- register_3phase_connections / register_3phase_input / register_3phase_output
- _build_all_pin_keys (gap-filling for sequential and prefixed terminals)
- _pin_sort_key (sort key with prefix:number handling)
- export_registry_to_csv (CSV export including empty-slot branch)
- get_registry / update_registry
"""

import csv
from dataclasses import replace
from pathlib import Path

from schematika.electrical.system.connection_registry import (
    Connection,
    TerminalRegistry,
    _build_all_pin_keys,
    _pin_sort_key,
    export_registry_to_csv,
    get_registry,
    log_connection,
    register_3phase_connections,
    register_3phase_input,
    register_3phase_output,
    update_registry,
)
from schematika.electrical.utils.autonumbering import create_autonumberer

# ---------------------------------------------------------------------------
# TerminalRegistry dataclass
# ---------------------------------------------------------------------------


class TestTerminalRegistry:
    """Tests for the TerminalRegistry frozen dataclass."""

    def test_empty_registry(self):
        reg = TerminalRegistry()
        assert reg.connections == ()

    def test_add_connection_returns_new_registry(self):
        reg = TerminalRegistry()
        new_reg = reg.add_connection("X1", "1", "F1", "1", "bottom")
        # Original is unchanged (frozen)  # noqa: ERA001
        assert reg.connections == ()
        assert len(new_reg.connections) == 1

    def test_add_connection_data(self):
        reg = TerminalRegistry()
        new_reg = reg.add_connection("X1", "1", "F1", "1", "bottom")
        conn = new_reg.connections[0]
        assert conn.terminal_tag == "X1"
        assert conn.terminal_pin == "1"
        assert conn.component_tag == "F1"
        assert conn.component_pin == "1"
        assert conn.side == "bottom"

    def test_add_connection_accumulates(self):
        reg = TerminalRegistry()
        reg = reg.add_connection("X1", "1", "F1", "1", "bottom")
        reg = reg.add_connection("X1", "2", "F1", "3", "bottom")
        assert len(reg.connections) == 2

    def test_add_connections_batch(self):
        """TerminalRegistry.add_connections adds multiple connections at once."""
        reg = TerminalRegistry()
        conns = [
            Connection("X1", "1", "F1", "1", "bottom"),
            Connection("X1", "2", "F1", "3", "bottom"),
            Connection("X1", "3", "F1", "5", "bottom"),
        ]
        new_reg = reg.add_connections(conns)
        assert len(new_reg.connections) == 3
        assert reg.connections == ()  # original unchanged

    def test_add_connections_appends_to_existing(self):
        """add_connections appends to any pre-existing connections."""
        reg = TerminalRegistry()
        reg = reg.add_connection("X0", "1", "K0", "A1", "top")
        conns = [
            Connection("X1", "1", "F1", "1", "bottom"),
            Connection("X1", "2", "F1", "3", "bottom"),
        ]
        new_reg = reg.add_connections(conns)
        assert len(new_reg.connections) == 3
        assert new_reg.connections[0].component_tag == "K0"
        assert new_reg.connections[1].component_tag == "F1"

    def test_add_connections_empty_list(self):
        """add_connections with an empty list returns equivalent registry."""
        reg = TerminalRegistry()
        reg = reg.add_connection("X1", "1", "F1", "1", "bottom")
        new_reg = reg.add_connections([])
        assert new_reg.connections == reg.connections

    def test_registry_is_frozen(self):
        """TerminalRegistry is a frozen dataclass."""
        reg = TerminalRegistry()
        try:
            reg.connections = ()  # ty: ignore[invalid-assignment]
            msg = "Should have raised FrozenInstanceError"
            raise AssertionError(msg)
        except AttributeError:
            pass  # Expected

    def test_connection_is_frozen(self):
        """Connection is a frozen dataclass."""
        conn = Connection("X1", "1", "F1", "1", "bottom")
        try:
            conn.terminal_tag = "X2"  # ty: ignore[invalid-assignment]
            msg = "Should have raised FrozenInstanceError"
            raise AssertionError(msg)
        except AttributeError:
            pass  # Expected


# ---------------------------------------------------------------------------
# get_registry / update_registry
# ---------------------------------------------------------------------------


class TestGetUpdateRegistry:
    def test_get_registry_returns_default(self):
        state = create_autonumberer()
        reg = get_registry(state)
        assert isinstance(reg, TerminalRegistry)
        assert reg.connections == ()

    def test_update_registry_replaces(self):
        state = create_autonumberer()
        reg = TerminalRegistry().add_connection("X1", "1", "F1", "1", "bottom")
        new_state = update_registry(state, reg)
        assert get_registry(new_state) is reg
        assert len(get_registry(new_state).connections) == 1
        # Original state unchanged
        assert len(get_registry(state).connections) == 0


# ---------------------------------------------------------------------------
# log_connection (functional helper)
# ---------------------------------------------------------------------------


class TestRegisterConnection:
    def test_single_registration(self):
        state = create_autonumberer()
        state = log_connection(state, "X1", "1", "F1", "1", "bottom")
        reg = get_registry(state)
        assert len(reg.connections) == 1
        conn = reg.connections[0]
        assert conn.terminal_tag == "X1"
        assert conn.terminal_pin == "1"
        assert conn.component_tag == "F1"
        assert conn.component_pin == "1"
        assert conn.side == "bottom"

    def test_default_side_is_bottom(self):
        state = create_autonumberer()
        state = log_connection(state, "X1", "1", "F1", "1")
        conn = get_registry(state).connections[0]
        assert conn.side == "bottom"

    def test_top_side(self):
        state = create_autonumberer()
        state = log_connection(state, "X1", "1", "F1", "1", "top")
        conn = get_registry(state).connections[0]
        assert conn.side == "top"

    def test_multiple_registrations_accumulate(self):
        state = create_autonumberer()
        state = log_connection(state, "X1", "1", "F1", "1")
        state = log_connection(state, "X1", "2", "F1", "3")
        state = log_connection(state, "X1", "3", "F1", "5")
        reg = get_registry(state)
        assert len(reg.connections) == 3

    def test_different_terminals(self):
        state = create_autonumberer()
        state = log_connection(state, "X1", "1", "F1", "1")
        state = log_connection(state, "X2", "1", "Q1", "2")
        reg = get_registry(state)
        assert reg.connections[0].terminal_tag == "X1"
        assert reg.connections[1].terminal_tag == "X2"


# ---------------------------------------------------------------------------
# register_3phase_connections
# ---------------------------------------------------------------------------


class TestRegister3PhaseConnections:
    def test_three_phase_registers_3_connections(self):
        state = create_autonumberer()
        state = register_3phase_connections(
            state, "X001", ("1", "2", "3"), "F1", ("1", "3", "5"), side="bottom"
        )
        reg = get_registry(state)
        assert len(reg.connections) == 3

    def test_three_phase_correct_mapping(self):
        state = create_autonumberer()
        state = register_3phase_connections(
            state, "X001", ("1", "2", "3"), "F1", ("1", "3", "5"), side="bottom"
        )
        conns = get_registry(state).connections
        # Phase 1
        assert conns[0].terminal_tag == "X001"
        assert conns[0].terminal_pin == "1"
        assert conns[0].component_tag == "F1"
        assert conns[0].component_pin == "1"
        assert conns[0].side == "bottom"
        # Phase 2
        assert conns[1].terminal_pin == "2"
        assert conns[1].component_pin == "3"
        # Phase 3
        assert conns[2].terminal_pin == "3"
        assert conns[2].component_pin == "5"

    def test_default_side_is_bottom(self):
        state = create_autonumberer()
        state = register_3phase_connections(
            state, "X001", ("1", "2", "3"), "F1", ("1", "3", "5")
        )
        for conn in get_registry(state).connections:
            assert conn.side == "bottom"

    def test_top_side(self):
        state = create_autonumberer()
        state = register_3phase_connections(
            state, "X201", ("4", "5", "6"), "Q1", ("2", "4", "6"), side="top"
        )
        for conn in get_registry(state).connections:
            assert conn.side == "top"

    def test_fewer_than_3_pins(self):
        """When fewer than 3 pins are supplied, only those are registered."""
        state = create_autonumberer()
        state = register_3phase_connections(
            state, "X1", ("1", "2"), "F1", ("1", "3", "5"), side="bottom"
        )
        reg = get_registry(state)
        assert len(reg.connections) == 2

    def test_more_than_3_pins_caps_at_3(self):
        """register_3phase_connections caps at 3 regardless of input length."""
        state = create_autonumberer()
        state = register_3phase_connections(
            state,
            "X1",
            ("1", "2", "3", "4"),
            "F1",
            ("1", "3", "5", "7"),
            side="bottom",
        )
        reg = get_registry(state)
        assert len(reg.connections) == 3


# ---------------------------------------------------------------------------
# register_3phase_input / register_3phase_output
# ---------------------------------------------------------------------------


class TestRegister3PhaseInputOutput:
    def test_input_uses_default_pins_1_3_5(self):
        state = create_autonumberer()
        state = register_3phase_input(state, "X001", ("1", "2", "3"), "F1")
        conns = get_registry(state).connections
        assert len(conns) == 3
        assert conns[0].component_pin == "1"
        assert conns[1].component_pin == "3"
        assert conns[2].component_pin == "5"
        for conn in conns:
            assert conn.side == "bottom"

    def test_input_custom_component_pins(self):
        state = create_autonumberer()
        state = register_3phase_input(
            state, "X001", ("1", "2", "3"), "F1", ("A", "B", "C")
        )
        conns = get_registry(state).connections
        assert conns[0].component_pin == "A"
        assert conns[1].component_pin == "B"
        assert conns[2].component_pin == "C"

    def test_output_uses_default_pins_2_4_6(self):
        state = create_autonumberer()
        state = register_3phase_output(state, "X201", ("4", "5", "6"), "Q1")
        conns = get_registry(state).connections
        assert len(conns) == 3
        assert conns[0].component_pin == "2"
        assert conns[1].component_pin == "4"
        assert conns[2].component_pin == "6"
        for conn in conns:
            assert conn.side == "top"

    def test_output_custom_component_pins(self):
        state = create_autonumberer()
        state = register_3phase_output(
            state, "X201", ("4", "5", "6"), "Q1", ("U", "V", "W")
        )
        conns = get_registry(state).connections
        assert conns[0].component_pin == "U"
        assert conns[1].component_pin == "V"
        assert conns[2].component_pin == "W"

    def test_input_then_output_accumulates(self):
        """Registering input and output on same state accumulates all 6 connections."""
        state = create_autonumberer()
        state = register_3phase_input(state, "X001", ("1", "2", "3"), "F1")
        state = register_3phase_output(state, "X201", ("4", "5", "6"), "Q1")
        reg = get_registry(state)
        assert len(reg.connections) == 6


# ---------------------------------------------------------------------------
# _pin_sort_key
# ---------------------------------------------------------------------------


class TestPinSortKey:
    def test_numeric_pins_sort_numerically(self):
        """Plain numeric pins should sort numerically, not lexicographically."""
        keys = [("X1", "10"), ("X1", "2"), ("X1", "1")]
        result = sorted(keys, key=_pin_sort_key)
        assert result == [("X1", "1"), ("X1", "2"), ("X1", "10")]

    def test_prefixed_pins_sort_by_prefix_then_number(self):
        """Prefixed pins (e.g., 'L1:3') sort by prefix, then number."""
        keys = [("X1", "L2:3"), ("X1", "L1:1"), ("X1", "L1:2")]
        result = sorted(keys, key=_pin_sort_key)
        assert result == [("X1", "L1:1"), ("X1", "L1:2"), ("X1", "L2:3")]

    def test_prefixed_pins_before_numeric(self):
        """Prefixed pins sort before plain numeric pins (group 0 vs 1)."""
        keys = [("X1", "1"), ("X1", "L1:1")]
        result = sorted(keys, key=_pin_sort_key)
        assert result == [("X1", "L1:1"), ("X1", "1")]

    def test_different_terminal_tags_sort_first(self):
        """Terminal tag is the primary sort key."""
        keys = [("X2", "1"), ("X1", "1")]
        result = sorted(keys, key=_pin_sort_key)
        assert result == [("X1", "1"), ("X2", "1")]

    def test_non_numeric_pins_sort_last(self):
        """Non-numeric, non-prefixed pins sort after numeric pins."""
        keys = [("X1", "PE"), ("X1", "1"), ("X1", "L1:1")]
        result = sorted(keys, key=_pin_sort_key)
        assert result == [("X1", "L1:1"), ("X1", "1"), ("X1", "PE")]

    def test_multiple_prefixed_groups(self):
        """Multiple prefixed groups interleave correctly."""
        keys = [
            ("X1", "L3:2"),
            ("X1", "L1:1"),
            ("X1", "L2:1"),
            ("X1", "L3:1"),
            ("X1", "L1:2"),
            ("X1", "L2:2"),
        ]
        result = sorted(keys, key=_pin_sort_key)
        assert result == [
            ("X1", "L1:1"),
            ("X1", "L1:2"),
            ("X1", "L2:1"),
            ("X1", "L2:2"),
            ("X1", "L3:1"),
            ("X1", "L3:2"),
        ]


# ---------------------------------------------------------------------------
# _build_all_pin_keys
# ---------------------------------------------------------------------------


class TestBuildAllPinKeys:
    def test_no_state_returns_sorted_existing_keys(self):
        """Without state, returns just the existing keys, sorted."""
        grouped = {
            ("X1", "3"): {"top": [], "bottom": []},
            ("X1", "1"): {"top": [], "bottom": []},
        }
        result = _build_all_pin_keys(grouped, state=None)
        assert result == [("X1", "1"), ("X1", "3")]

    def test_sequential_gap_filling(self):
        """With sequential counters, fills gaps between 1 and max."""
        state = create_autonumberer()
        # Simulate terminal_counters having allocated up to pin 4 for X1
        state = replace(state, terminal_counters={"X1": 4})
        # Only pins 1 and 3 have connections registered
        grouped = {
            ("X1", "1"): {"top": [], "bottom": []},
            ("X1", "3"): {"top": [], "bottom": []},
        }
        result = _build_all_pin_keys(grouped, state)
        # Should include 1, 2, 3, 4
        assert ("X1", "1") in result
        assert ("X1", "2") in result
        assert ("X1", "3") in result
        assert ("X1", "4") in result
        assert len([k for k in result if k[0] == "X1"]) == 4

    def test_prefixed_gap_filling(self):
        """With prefix counters, fills gaps for each prefix."""
        state = create_autonumberer()
        # Simulate prefix counters: L1 up to 2, L2 up to 2 for X1
        state = replace(
            state,
            terminal_prefix_counters={"X1": {"L1": 2, "L2": 2}},
        )
        # Only one connection registered
        grouped = {
            ("X1", "L1:1"): {"top": [], "bottom": []},
        }
        result = _build_all_pin_keys(grouped, state)
        expected_keys = {
            ("X1", "L1:1"),
            ("X1", "L1:2"),
            ("X1", "L2:1"),
            ("X1", "L2:2"),
        }
        assert set(result) == expected_keys

    def test_mixed_terminals(self):
        """Sequential and prefixed terminals in the same call."""
        state = create_autonumberer()
        state = replace(
            state,
            terminal_counters={"X2": 2},
            terminal_prefix_counters={"X1": {"L1": 1}},
        )
        grouped = {
            ("X1", "L1:1"): {"top": [], "bottom": []},
            ("X2", "1"): {"top": [], "bottom": []},
        }
        result = _build_all_pin_keys(grouped, state)
        assert ("X1", "L1:1") in result
        assert ("X2", "1") in result
        assert ("X2", "2") in result

    def test_no_gap_when_counter_matches(self):
        """When all pins are present, no extra keys are added."""
        state = create_autonumberer()
        state = replace(state, terminal_counters={"X1": 2})
        grouped = {
            ("X1", "1"): {"top": [], "bottom": []},
            ("X1", "2"): {"top": [], "bottom": []},
        }
        result = _build_all_pin_keys(grouped, state)
        assert len([k for k in result if k[0] == "X1"]) == 2

    def test_terminal_not_in_grouped_is_ignored(self):
        """Counters for terminals not in grouped dict are not expanded."""
        state = create_autonumberer()
        state = replace(state, terminal_counters={"X1": 3, "X2": 5})
        grouped = {
            ("X1", "1"): {"top": [], "bottom": []},
        }
        result = _build_all_pin_keys(grouped, state)
        # X1 should be expanded, X2 should NOT (no registered connections)
        x1_keys = [k for k in result if k[0] == "X1"]
        x2_keys = [k for k in result if k[0] == "X2"]
        assert len(x1_keys) == 3
        assert len(x2_keys) == 0


# ---------------------------------------------------------------------------
# export_registry_to_csv
# ---------------------------------------------------------------------------


class TestExportRegistryToCsv:
    def test_basic_export(self, tmp_path):
        """Export a simple registry to CSV and verify content."""
        state = create_autonumberer()
        state = log_connection(state, "X1", "1", "F1", "1", "bottom")
        state = log_connection(state, "X1", "1", "K1", "A1", "top")

        filepath = str(tmp_path / "connections.csv")
        export_registry_to_csv(get_registry(state), filepath)

        with Path(filepath).open(encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # Header + 1 data row
        assert len(rows) == 2
        assert rows[0] == [
            "Component From",
            "Pin From",
            "Terminal Tag",
            "Terminal Pin",
            "Component To",
            "Pin To",
        ]
        # Top side = from, bottom side = to
        assert rows[1] == ["K1", "A1", "X1", "1", "F1", "1"]

    def test_multiple_rows(self, tmp_path):
        """Multiple terminal pins create multiple rows."""
        state = create_autonumberer()
        state = log_connection(state, "X1", "1", "F1", "1", "bottom")
        state = log_connection(state, "X1", "2", "F1", "3", "bottom")
        state = log_connection(state, "X1", "3", "F1", "5", "bottom")

        filepath = str(tmp_path / "connections.csv")
        export_registry_to_csv(get_registry(state), filepath)

        with Path(filepath).open(encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        assert len(rows) == 4  # header + 3 data rows

    def test_empty_registry(self, tmp_path):
        """Exporting an empty registry produces only a header."""
        filepath = str(tmp_path / "empty.csv")
        export_registry_to_csv(TerminalRegistry(), filepath)

        with Path(filepath).open(encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        assert len(rows) == 1  # header only

    def test_empty_slots_with_state(self, tmp_path):
        """When state has counters beyond registered connections, empty slots appear."""
        state = create_autonumberer()
        # Register connection for pin 1 only
        state = log_connection(state, "X1", "1", "F1", "1", "bottom")
        # But the counter says 3 pins were allocated
        state = replace(state, terminal_counters={"X1": 3})

        filepath = str(tmp_path / "with_gaps.csv")
        export_registry_to_csv(get_registry(state), filepath, state=state)

        with Path(filepath).open(encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # header + 3 data rows (pin 1 has data, pins 2 and 3 are empty)
        assert len(rows) == 4
        # Pin 1 has data
        assert rows[1][2] == "X1"
        assert rows[1][3] == "1"
        assert rows[1][4] == "F1"  # Component To
        # Pins 2, 3 are empty slots
        assert rows[2] == ["", "", "X1", "2", "", ""]
        assert rows[3] == ["", "", "X1", "3", "", ""]

    def test_export_with_both_sides(self, tmp_path):
        """A pin with both top and bottom connections shows both."""
        state = create_autonumberer()
        state = log_connection(state, "X1", "1", "F1", "1", "bottom")
        state = log_connection(state, "X1", "1", "K1", "A1", "top")

        filepath = str(tmp_path / "both_sides.csv")
        export_registry_to_csv(get_registry(state), filepath)

        with Path(filepath).open(encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        assert len(rows) == 2  # header + 1 row
        data = rows[1]
        assert data[0] == "K1"  # Component From (top)
        assert data[1] == "A1"  # Pin From (top)
        assert data[2] == "X1"  # Terminal Tag
        assert data[3] == "1"  # Terminal Pin
        assert data[4] == "F1"  # Component To (bottom)
        assert data[5] == "1"  # Pin To (bottom)

    def test_export_multiple_components_same_pin(self, tmp_path):
        """Multiple components on the same side of a pin are joined with ' / '."""
        state = create_autonumberer()
        state = log_connection(state, "X1", "1", "F1", "1", "bottom")
        state = log_connection(state, "X1", "1", "F2", "3", "bottom")

        filepath = str(tmp_path / "multi.csv")
        export_registry_to_csv(get_registry(state), filepath)

        with Path(filepath).open(encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        data = rows[1]
        assert data[4] == "F1 / F2"  # Component To
        assert data[5] == "1 / 3"  # Pin To

    def test_export_without_state(self, tmp_path):
        """Without state, no gap-filling occurs."""
        reg = TerminalRegistry()
        reg = reg.add_connection("X1", "1", "F1", "1", "bottom")
        reg = reg.add_connection("X1", "3", "F1", "5", "bottom")

        filepath = str(tmp_path / "no_state.csv")
        export_registry_to_csv(reg, filepath, state=None)

        with Path(filepath).open(encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # header + 2 data rows (no gap-filling for pin 2)
        assert len(rows) == 3

    def test_export_prefixed_pins_with_gaps(self, tmp_path):
        """Prefixed pins with state gap-fill correctly."""
        state = create_autonumberer()
        state = log_connection(state, "X1", "L1:1", "F1", "1", "bottom")
        # Set prefix counters: L1 up to 2, L2 up to 1
        state = replace(
            state,
            terminal_prefix_counters={"X1": {"L1": 2, "L2": 1}},
        )

        filepath = str(tmp_path / "prefixed.csv")
        export_registry_to_csv(get_registry(state), filepath, state=state)

        with Path(filepath).open(encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # Expected pins: L1:1 (has data), L1:2 (empty), L2:1 (empty) = 3 data rows
        assert len(rows) == 4  # header + 3
        # Verify the filled row
        pins = [row[3] for row in rows[1:]]
        assert "L1:1" in pins
        assert "L1:2" in pins
        assert "L2:1" in pins

    def test_export_sorted_output(self, tmp_path):
        """Output rows are sorted by terminal tag, then pin."""
        state = create_autonumberer()
        state = log_connection(state, "X2", "1", "Q1", "2", "top")
        state = log_connection(state, "X1", "2", "F1", "3", "bottom")
        state = log_connection(state, "X1", "1", "F1", "1", "bottom")

        filepath = str(tmp_path / "sorted.csv")
        export_registry_to_csv(get_registry(state), filepath)

        with Path(filepath).open(encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        data_rows = rows[1:]
        tags_pins = [(r[2], r[3]) for r in data_rows]
        assert tags_pins == [("X1", "1"), ("X1", "2"), ("X2", "1")]


# ---------------------------------------------------------------------------
# Integration: 3-phase registration + CSV export
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_full_3phase_input_output_export(self, tmp_path):
        """Register input + output for a 3-phase component, then export."""
        state = create_autonumberer()
        state = register_3phase_input(state, "X001", ("1", "2", "3"), "F1")
        state = register_3phase_output(state, "X201", ("4", "5", "6"), "Q1")

        filepath = str(tmp_path / "full.csv")
        export_registry_to_csv(get_registry(state), filepath)

        with Path(filepath).open(encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # 6 connections total
        assert len(rows) == 7  # header + 6

    def test_multiple_components_on_same_terminal(self, tmp_path):
        """Multiple 3-phase components sharing the same terminal."""
        state = create_autonumberer()
        state = register_3phase_input(state, "X001", ("1", "2", "3"), "F1")
        state = register_3phase_input(state, "X001", ("4", "5", "6"), "F2")

        reg = get_registry(state)
        assert len(reg.connections) == 6
        # All on X001
        for conn in reg.connections:
            assert conn.terminal_tag == "X001"
