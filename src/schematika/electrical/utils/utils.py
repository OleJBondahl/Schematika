"""Tag counter and terminal helpers."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from schematika.core.utils import natural_sort_key as natural_sort_key

if TYPE_CHECKING:
    from collections.abc import Callable

    from schematika.electrical.model.state import GenerationState


def set_tag_counter(state: GenerationState, prefix: str, value: int) -> GenerationState:
    """Next `next_tag(prefix)` will return `value + 1`."""
    new_tags = {**state.tags, prefix: value}
    return replace(state, tags=new_tags)


def set_terminal_counter(
    state: GenerationState, terminal_tag: str, value: int
) -> GenerationState:
    """Sets shared + per-prefix counters; next allocation starts at `value + 1`."""
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
    """Current pin counter (0 if unused)."""
    return state.terminal_counters.get(str(terminal_tag), 0)


def apply_start_indices(
    state: GenerationState,
    start_indices: dict[str, int] | None = None,
) -> GenerationState:
    """Apply `{prefix: start_value}` to tag counters."""
    if not start_indices:
        return state
    for prefix, value in start_indices.items():
        state = set_tag_counter(state, prefix, value)
    return state


def merge_terminals(target: list, source: list) -> list:
    """Concatenate two terminal lists into a new list."""
    return target + source


def fixed_tag(tag: str) -> Callable[[GenerationState], tuple[GenerationState, str]]:
    """Tag generator that always emits *tag* (for fixed designations)."""

    def _gen(state: GenerationState) -> tuple[GenerationState, str]:
        return state, tag

    return _gen
