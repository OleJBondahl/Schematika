"""Typed state for circuit generation.

Provides type-safe state management for the CircuitBuilder and
related generation functions.
"""

from dataclasses import dataclass, field

import deal

from schematika.core.connection_registry import TerminalRegistry


@dataclass(frozen=True)
class GenerationState:
    """Immutable state container for circuit generation.

    Attributes:
        tags: Counter for component tags (e.g., {"K": 3} means next K is K4)
        terminal_counters: Counter for terminal numbering per terminal block
        terminal_prefix_counters: Per-prefix counters for prefixed terminals
            (e.g., {"X001": {"L1": 3, "N": 2}} means next L1 on X001 is group 4)
        contact_channels: Counter for contact channel assignment
        terminal_registry: Registry of terminal connections
        pin_counter: Global pin counter (legacy)
    """

    tags: dict[str, int] = field(default_factory=dict)
    terminal_counters: dict[str, int] = field(default_factory=dict)
    terminal_prefix_counters: dict[str, dict[str, int]] = field(default_factory=dict)
    contact_channels: dict[str, int] = field(default_factory=dict)
    terminal_registry: TerminalRegistry = field(default_factory=TerminalRegistry)
    pin_counter: int = 0


@deal.pure
def create_initial_state() -> "GenerationState":
    """Create a new initial state.

    Returns:
        GenerationState: A fresh state with all fields initialized to defaults.
    """
    return GenerationState()
