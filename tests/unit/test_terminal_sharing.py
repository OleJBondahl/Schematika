"""Tests for terminal pin sharing (reuse_terminals)."""

import pytest

from schematika.electrical import (
    CircuitBuilder,
    Terminal,
    create_autonumberer,
)
from schematika.electrical.exceptions import TerminalReuseError

TM_A = Terminal("XA", "Terminal A")
TM_B = Terminal("XB", "Terminal B")


def _simple_builder(state, terminal):
    """Build a simple terminal-only circuit for testing."""
    builder = CircuitBuilder(state)
    builder.set_layout(x=0, y=0, spacing=100)
    builder.add_terminal(terminal, poles=1)
    return builder


class TestTerminalPinMap:
    """Tests that terminal_pin_map is populated correctly."""

    def test_single_instance_single_pole(self):
        state = create_autonumberer()
        builder = _simple_builder(state, TM_A)
        res = builder.build(count=1)

        assert str(TM_A) in res.terminal_pin_map
        assert res.terminal_pin_map[str(TM_A)] == ["1"]

    def test_multiple_instances(self):
        state = create_autonumberer()
        builder = _simple_builder(state, TM_A)
        res = builder.build(count=3)

        assert res.terminal_pin_map[str(TM_A)] == ["1", "2", "3"]

    def test_two_terminals_tracked_separately(self):
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(x=0, y=0, spacing=100)
        builder.add_terminal(TM_A, poles=1, connect_to_next=False)
        builder.add_terminal(TM_B, poles=1, connect_to_next=False)
        res = builder.build(count=2)

        assert str(TM_A) in res.terminal_pin_map
        assert str(TM_B) in res.terminal_pin_map
        # Each terminal gets 2 pins (one per instance)
        assert len(res.terminal_pin_map[str(TM_A)]) == 2
        assert len(res.terminal_pin_map[str(TM_B)]) == 2

    def test_explicit_pins_not_tracked(self):
        """Terminals with explicit pins are still tracked in the map."""
        state = create_autonumberer()
        builder = CircuitBuilder(state)
        builder.set_layout(x=0, y=0, spacing=100)
        builder.add_terminal(TM_A, poles=1, pins=("L1",))
        res = builder.build(count=1)

        assert res.terminal_pin_map[str(TM_A)] == ["L1"]


class TestReuseTerminals:
    """Tests that reuse_terminals replays pins from a source result."""

    def test_same_pins_reused(self):
        state = create_autonumberer()

        # Build source: auto-assigns pins 1, 2, 3
        builder_a = _simple_builder(state, TM_A)
        res_a = builder_a.build(count=3)

        # Build consumer: reuses pins from source
        builder_b = _simple_builder(res_a.state, TM_A)
        res_b = builder_b.build(count=3, reuse_terminals={TM_A: res_a})

        assert res_b.terminal_pin_map[str(TM_A)] == ["1", "2", "3"]

    def test_reuse_does_not_advance_counter(self):
        state = create_autonumberer()

        builder_a = _simple_builder(state, TM_A)
        res_a = builder_a.build(count=3)
        # Counter is now at 3

        # Reuse should NOT advance the counter
        builder_b = _simple_builder(res_a.state, TM_A)
        res_b = builder_b.build(count=3, reuse_terminals={TM_A: res_a})

        # Build another without reuse — should continue from 3
        builder_c = _simple_builder(res_b.state, TM_A)
        res_c = builder_c.build(count=1)

        assert res_c.terminal_pin_map[str(TM_A)] == ["4"]

    def test_reuse_exhausted_raises(self):
        state = create_autonumberer()

        builder_a = _simple_builder(state, TM_A)
        res_a = builder_a.build(count=2)

        # Try to reuse 2 pins for 3 instances
        builder_b = _simple_builder(res_a.state, TM_A)
        with pytest.raises(TerminalReuseError):
            builder_b.build(count=3, reuse_terminals={TM_A: res_a})

    def test_mixed_reuse_and_auto(self):
        """Only the specified terminal reuses; others auto-number."""
        state = create_autonumberer()

        # Source only has TM_A pins
        builder_a = _simple_builder(state, TM_A)
        res_a = builder_a.build(count=2)

        # Consumer has both TM_A (reused) and TM_B (auto)
        builder_b = CircuitBuilder(res_a.state)
        builder_b.set_layout(x=0, y=0, spacing=100)
        builder_b.add_terminal(TM_A, poles=1, connect_to_next=False)
        builder_b.add_terminal(TM_B, poles=1, connect_to_next=False)
        res_b = builder_b.build(count=2, reuse_terminals={TM_A: res_a})

        # TM_A reused from source
        assert res_b.terminal_pin_map[str(TM_A)] == ["1", "2"]
        # TM_B auto-numbered independently
        assert res_b.terminal_pin_map[str(TM_B)] == ["1", "2"]


class TestBuildResultIter:
    """Tests that BuildResult backward-compatible iteration still works."""

    def test_tuple_unpacking(self):
        state = create_autonumberer()
        builder = _simple_builder(state, TM_A)
        state, circuit, terminals = builder.build(count=1)

        assert state is not None
        assert circuit is not None
        assert isinstance(terminals, list)
