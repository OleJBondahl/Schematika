"""
Utility functions for circuit generation and state management.
Contains helpers for tag counters and terminal management.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from schematika.core.utils import natural_sort_key as natural_sort_key  # noqa: F401
from schematika.electrical.model.state import GenerationState


def set_tag_counter(state: GenerationState, prefix: str, value: int) -> GenerationState:
    """
    Sets the counter for a specific tag prefix to a given value.
    The next call to next_tag() will return value + 1.

    Args:
        state: The autonumbering state.
        prefix: The tag prefix to set (e.g. "Q").
        value: The value to set the counter to.

    Returns:
        Updated state.
    """
    new_tags = {**state.tags, prefix: value}
    return replace(state, tags=new_tags)


def set_terminal_counter(
    state: GenerationState, terminal_tag: str, value: int
) -> GenerationState:
    """
    Sets the pin counter for a specific terminal tag.
    The next call to next_terminal_pins() will start from value + 1.

    Also updates all per-prefix counters for this terminal to *value*
    so that prefixed allocations respect the new floor.
    """
    tag_key = str(terminal_tag)

    # Update legacy shared counter
    new_counters = {**state.terminal_counters, tag_key: value}

    # Update per-prefix counters to match
    prefix_counters = state.terminal_prefix_counters
    if tag_key in prefix_counters:
        new_tag_prefixes = prefix_counters[tag_key].copy()
        for p in new_tag_prefixes:
            new_tag_prefixes[p] = value
        new_prefix_counters = {**prefix_counters, tag_key: new_tag_prefixes}
    else:
        new_prefix_counters = prefix_counters

    return replace(
        state,
        terminal_counters=new_counters,
        terminal_prefix_counters=new_prefix_counters,
    )


def get_terminal_counter(state: GenerationState, terminal_tag: str) -> int:
    """
    Get the current pin counter for a terminal (0 if unused).

    Args:
        state: The autonumbering state.
        terminal_tag: The terminal tag to query.

    Returns:
        Current pin counter value for this terminal.
    """
    return state.terminal_counters.get(str(terminal_tag), 0)


def apply_start_indices(
    state: GenerationState,
    start_indices: dict[str, int] | None = None,
) -> GenerationState:
    """
    Apply start indices to tag counters.

    Args:
        state: Current autonumbering state
        start_indices: Dict of {prefix: start_value}

    Returns:
        Updated state
    """
    if not start_indices:
        return state
    for prefix, value in start_indices.items():
        state = set_tag_counter(state, prefix, value)
    return state


def merge_terminals(target: list, source: list) -> list:
    """
    Merge two terminal lists, returning a new combined list.

    Args:
        target: The first terminal list
        source: The second terminal list to append

    Returns:
        A new list containing all items from both lists.
    """
    return target + source


def fixed_tag(tag: str) -> Callable[[GenerationState], tuple[GenerationState, str]]:
    """Return a tag generator that always emits the given fixed tag.

    Useful for ``tag_generators`` when a relay or contactor tag must stay
    constant across multiple circuit instances.

    Args:
        tag: The tag string to always return (e.g. ``"K1"``).

    Returns:
        A callable ``(state) -> (state, tag)`` suitable for use as a
        ``tag_generators`` value in
        :meth:`~schematika.electrical.builder.CircuitBuilder.build`.

    Example::

        from schematika.electrical import fixed_tag, CircuitBuilder

        result = builder.build(count=3, tag_generators={"K": fixed_tag("K1")})
    """

    def _gen(state: GenerationState) -> tuple[GenerationState, str]:
        return state, tag

    return _gen
