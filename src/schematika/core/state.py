"""Typed state for circuit generation.

Provides type-safe state management for the CircuitBuilder and
related generation functions.
"""

from dataclasses import dataclass, field

import deal

from schematika.core.connection_registry import TerminalRegistry


@dataclass(frozen=True)
class GenerationState:
    """Immutable state container threaded through all circuit generation calls.

    Passed into :class:`~schematika.electrical.CircuitBuilder` and returned
    in :class:`~schematika.electrical.BuildResult`.  All fields default to
    empty so a fresh state is just ``GenerationState()`` or
    :func:`create_initial_state`.

    Attributes:
        tags: Per-prefix tag counter, e.g. ``{"K": 3}`` means next K tag is K4.
        terminal_counters: Sequential pin counter per terminal block ID.
        terminal_prefix_counters: Per-prefix group counters for prefixed terminals,
            e.g. ``{"X001": {"L1": 3}}`` means next L1 group on X001 is 4.
        contact_channels: Counter for contact channel assignment.
        terminal_registry: Registry of all logged terminal connections.
        pin_counter: Global pin counter (legacy field; prefer terminal_counters).

    Examples:
        >>> from schematika.electrical import GenerationState, create_initial_state
        >>> state = create_initial_state()
        >>> state.tags
        {}
        >>> state.pin_counter
        0
    """

    tags: dict[str, int] = field(default_factory=dict)
    terminal_counters: dict[str, int] = field(default_factory=dict)
    terminal_prefix_counters: dict[str, dict[str, int]] = field(default_factory=dict)
    contact_channels: dict[str, int] = field(default_factory=dict)
    terminal_registry: TerminalRegistry = field(default_factory=TerminalRegistry)
    pin_counter: int = 0


@deal.pure
def create_initial_state() -> "GenerationState":
    """Create a fresh :class:`GenerationState` with all counters at zero.

    Returns:
        :class:`GenerationState` with all fields at their defaults.

    Examples:
        >>> from schematika.electrical import create_initial_state
        >>> state = create_initial_state()
        >>> state.tags, state.terminal_counters
        ({}, {})
    """
    return GenerationState()
