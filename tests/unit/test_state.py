"""Unit tests for GenerationState."""

from schematika.electrical.model.state import GenerationState, create_initial_state
from schematika.electrical.system.connection_registry import TerminalRegistry


def test_create_initial_state():
    """Initial state should be a GenerationState with default values."""
    state = create_initial_state()
    assert isinstance(state, GenerationState)
    assert state.tags == {}
    assert state.terminal_counters == {}
    assert state.contact_channels == {}
    assert isinstance(state.terminal_registry, TerminalRegistry)
    assert state.pin_counter == 0


def test_generation_state_is_frozen():
    """GenerationState should be immutable (frozen dataclass)."""
    gs = GenerationState()
    try:
        gs.tags = {"K": 1}  # type: ignore[invalid-assignment]
        msg = "Should have raised FrozenInstanceError"
        raise AssertionError(msg)
    except AttributeError:
        pass  # Expected for frozen dataclass
