"""Tests for auto terminal pin allocation (Task 8A)."""

from schematika.core.options import TerminalConfig
from schematika.electrical import Terminal
from schematika.electrical.builder import CircuitBuilder
from schematika.electrical.symbols.coils import coil
from schematika.electrical.utils.autonumbering import (
    create_autonumberer,
    next_terminal_pins,
)
from schematika.electrical.utils.utils import set_terminal_counter


def test_auto_pin_sequential():
    """Adding terminals without explicit pins should auto-allocate sequential pins."""
    state = create_autonumberer()

    builder = CircuitBuilder(state)
    builder.set_layout(x=0, y=0, spacing=80)
    builder.add_terminal("X008")
    builder.add_symbol(coil, "K", pins=("A1", "A2"))
    builder.add_terminal("X008")

    result = builder.build(count=3)

    # The terminal counter for X008 should have advanced
    # 3 instances, each with 2 terminals using 1 pin each = 6 pins total
    # Pins: 1, 2, 3, 4, 5, 6 (sequential across instances)
    assert result.state.terminal_counters["X008"] == 6


def test_auto_pin_with_seeded_start():
    """Setting terminal counter should affect where auto pins start."""
    state = create_autonumberer()
    state = set_terminal_counter(state, "X008", 5)

    builder = CircuitBuilder(state)
    builder.set_layout(x=0, y=0, spacing=80)
    builder.add_terminal("X008")
    builder.add_symbol(coil, "K", pins=("A1", "A2"))
    builder.add_terminal("X008")

    result = builder.build(count=1)

    # Pins should start at 6 (counter was 5, next_terminal_pins adds 1)
    assert result.state.terminal_counters["X008"] == 7


def test_explicit_pins_override():
    """Explicit pins should be used instead of auto-allocation."""
    state = create_autonumberer()

    builder = CircuitBuilder(state)
    builder.set_layout(x=0, y=0, spacing=80)
    builder.add_terminal("X008", config=TerminalConfig(pins=("42",)))
    builder.add_symbol(coil, "K", pins=("A1", "A2"))
    builder.add_terminal("X008")

    result = builder.build(count=1)

    # First terminal used explicit pin "42", so counter should be at 1
    # (only the second terminal auto-allocated pin "1")
    assert result.state.terminal_counters["X008"] == 1


def test_auto_pin_across_builds():
    """Auto pins should continue across multiple builds using shared state."""
    state = create_autonumberer()

    # First build: allocates pins 1, 2 for X008
    builder1 = CircuitBuilder(state)
    builder1.set_layout(x=0, y=0, spacing=80)
    builder1.add_terminal("X008")
    builder1.add_symbol(coil, "K", pins=("A1", "A2"))
    builder1.add_terminal("X008")
    result1 = builder1.build(count=1)

    assert result1.state.terminal_counters["X008"] == 2

    # Second build with state from first: should continue from pin 3
    builder2 = CircuitBuilder(result1.state)
    builder2.set_layout(x=0, y=0, spacing=80)
    builder2.add_terminal("X008")
    builder2.add_symbol(coil, "K", pins=("A1", "A2"))
    builder2.add_terminal("X008")
    result2 = builder2.build(count=1)

    assert result2.state.terminal_counters["X008"] == 4


def test_mixed_auto_and_explicit():
    """Mix of auto and explicit pins should not conflict."""
    state = create_autonumberer()

    builder = CircuitBuilder(state)
    builder.set_layout(x=0, y=0, spacing=80)
    builder.add_terminal("X008")  # auto: pin 1
    builder.add_symbol(coil, "K", pins=("A1", "A2"))
    builder.add_terminal(
        "X008", config=TerminalConfig(pins=("99",))
    )  # explicit: pin 99

    result = builder.build(count=1)

    # Auto-allocated only 1 pin, explicit used "99"
    assert result.state.terminal_counters["X008"] == 1


def test_auto_pin_different_terminals():
    """Different terminal IDs should have independent pin counters."""
    state = create_autonumberer()

    builder = CircuitBuilder(state)
    builder.set_layout(x=0, y=0, spacing=80)
    builder.add_terminal("X003")
    builder.add_symbol(coil, "K", pins=("A1", "A2"))
    builder.add_terminal("X103")

    result = builder.build(count=3)

    # Each terminal gets 1 pin per instance, 3 instances
    assert result.state.terminal_counters["X003"] == 3
    assert result.state.terminal_counters["X103"] == 3


# ---------------------------------------------------------------------------
# Per-prefix counter tests
# ---------------------------------------------------------------------------


def test_prefixed_partial_allocation_does_not_advance_other_prefixes():
    """Allocating only L1 on a 4-prefix terminal should not advance L2/L3/N."""
    tm = Terminal("X001", "Test", pin_prefixes=("L1", "L2", "L3", "N"))
    state = create_autonumberer()

    # Allocate L1 only
    state, pins = next_terminal_pins(state, tm, poles=1, pin_prefixes=("L1",))
    assert pins == ("L1:1",)

    # L2/L3/N should still be at 0 (unadvanced)
    prefix_counters = state.terminal_prefix_counters["X001"]
    assert prefix_counters["L1"] == 1
    assert "L2" not in prefix_counters
    assert "L3" not in prefix_counters
    assert "N" not in prefix_counters


def test_prefixed_partial_then_full_allocation():
    """After partial L1 allocations, a full L1+L2+L3 should start L2/L3 from 2."""
    tm = Terminal("X001", "Test", pin_prefixes=("L1", "L2", "L3", "N"))
    state = create_autonumberer()

    # Step 1: Full allocation (like changeover) -- group 1
    state, pins = next_terminal_pins(state, tm, poles=4)
    assert pins == ("L1:1", "L2:1", "L3:1", "N:1")

    # Step 2: Partial L1 only (like K1 coil) -- L1 advances to 2
    state, pins = next_terminal_pins(state, tm, poles=1, pin_prefixes=("L1",))
    assert pins == ("L1:2",)

    # Step 3: Partial N only (like K1 coil bottom) -- N advances to 2
    state, pins = next_terminal_pins(state, tm, poles=1, pin_prefixes=("N",))
    assert pins == ("N:2",)

    # Step 4: Another L1 (like K2 coil) -- L1 advances to 3
    state, pins = next_terminal_pins(state, tm, poles=1, pin_prefixes=("L1",))
    assert pins == ("L1:3",)

    # Step 5: Another N -- N advances to 3
    state, pins = next_terminal_pins(state, tm, poles=1, pin_prefixes=("N",))
    assert pins == ("N:3",)

    # Step 6: Full L1+L2+L3 (like pump DOL) -- max(L1=3, L2=1, L3=1)+1 = 4
    state, pins = next_terminal_pins(state, tm, poles=3)
    assert pins == ("L1:4", "L2:4", "L3:4")

    # L2 went from 1 directly to 4 (gap of 2 instead of old gap of 4)
    prefix_counters = state.terminal_prefix_counters["X001"]
    assert prefix_counters["L1"] == 4
    assert prefix_counters["L2"] == 4
    assert prefix_counters["L3"] == 4
    assert prefix_counters["N"] == 3


def test_prefixed_full_allocation_consistent_groups():
    """Multiple full-prefix allocations should produce consistent sequential groups."""
    tm = Terminal("X001", "Test", pin_prefixes=("L1", "L2", "L3"))
    state = create_autonumberer()

    state, pins1 = next_terminal_pins(state, tm, poles=3)
    assert pins1 == ("L1:1", "L2:1", "L3:1")

    state, pins2 = next_terminal_pins(state, tm, poles=3)
    assert pins2 == ("L1:2", "L2:2", "L3:2")

    state, pins3 = next_terminal_pins(state, tm, poles=3)
    assert pins3 == ("L1:3", "L2:3", "L3:3")

    # All prefixes should be at 3
    prefix_counters = state.terminal_prefix_counters["X001"]
    assert prefix_counters == {"L1": 3, "L2": 3, "L3": 3}


def test_set_terminal_counter_respects_prefix_floor():
    """set_terminal_counter should update per-prefix counters too."""
    tm = Terminal("X001", "Test", pin_prefixes=("L1", "L2", "L3"))
    state = create_autonumberer()

    # Allocate a group first to populate prefix counters
    state, _ = next_terminal_pins(state, tm, poles=3)
    assert state.terminal_prefix_counters["X001"] == {"L1": 1, "L2": 1, "L3": 1}

    # Set counter to 5
    state = set_terminal_counter(state, "X001", 5)

    # Per-prefix counters should also be updated
    assert state.terminal_prefix_counters["X001"] == {"L1": 5, "L2": 5, "L3": 5}

    # Next allocation should start at 6
    state, pins = next_terminal_pins(state, tm, poles=3)
    assert pins == ("L1:6", "L2:6", "L3:6")


def test_prefixed_allocation_respects_shared_counter_floor():
    """Per-prefix allocation should respect the legacy shared counter as a floor."""
    tm = Terminal("X001", "Test", pin_prefixes=("L1", "L2", "L3"))
    state = create_autonumberer()

    # Set shared counter to 5 without any prefix allocations existing
    state = set_terminal_counter(state, "X001", 5)

    # Allocation should start at 6 (respecting the shared counter floor)
    state, pins = next_terminal_pins(state, tm, poles=3)
    assert pins == ("L1:6", "L2:6", "L3:6")
