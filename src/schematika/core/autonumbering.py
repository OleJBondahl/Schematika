"""Autonumbering for component tags (`F1`, `F2`, ...) and terminal pins."""

from dataclasses import replace

import deal

from schematika._purity import pure
from schematika.core.state import GenerationState, create_initial_state


@deal.pure
def create_autonumberer() -> GenerationState:
    """Fresh state with all counters at zero."""
    return create_initial_state()


@deal.pure
def get_tag_number(state: GenerationState, prefix: str) -> int:
    """Current number for *prefix* (0 if unused)."""
    return state.tags.get(prefix, 0)


@deal.pure
def _increment_tag(state: GenerationState, prefix: str) -> GenerationState:
    """Increment counter for *prefix*; returns new state."""
    new_tags = {**state.tags, prefix: get_tag_number(state, prefix) + 1}
    return replace(state, tags=new_tags)


@deal.pure
def _format_tag(prefix: str, number: int) -> str:
    """`f"{prefix}{number}"`."""
    return f"{prefix}{number}"


@deal.pure
def next_tag(state: GenerationState, prefix: str) -> tuple[GenerationState, str]:
    """Increment + format the next tag for *prefix*."""
    new_state = _increment_tag(state, prefix)
    tag = _format_tag(prefix, get_tag_number(new_state, prefix))
    return new_state, tag


@deal.pure
def next_terminal_pins(
    state: GenerationState,
    terminal_tag: str,
    poles: int = 3,
    pin_prefixes: tuple[str, ...] | None = None,
) -> tuple[GenerationState, tuple[str, ...]]:
    """With `pin_prefixes`, returns `"prefix:group"` per prefix; else sequential."""
    prefixes = pin_prefixes or getattr(terminal_tag, "pin_prefixes", None)

    counters = state.terminal_counters
    tag_key = str(terminal_tag)

    if prefixes and len(prefixes) >= poles:
        # Per-prefix group-based allocation.
        # Each prefix has its own counter.  The group number is
        # max(per-prefix counters for requested prefixes) + 1,
        # also respecting the legacy shared counter as a floor
        # (set only by set_terminal_counter, not auto-advanced here).
        prefix_counters = state.terminal_prefix_counters
        tag_prefixes = prefix_counters.get(tag_key, {})
        shared_floor = counters.get(tag_key, 0)

        requested = tuple(prefixes[i] for i in range(poles))
        max_existing = max(
            (tag_prefixes.get(p, 0) for p in requested),
            default=0,
        )
        new_group = max(max_existing, shared_floor) + 1
        pins = tuple(f"{p}:{new_group}" for p in requested)

        # Update per-prefix counters for only the requested prefixes
        new_tag_prefixes = tag_prefixes.copy()
        for p in requested:
            new_tag_prefixes[p] = new_group

        new_prefix_counters = {**prefix_counters, tag_key: new_tag_prefixes}
        # Legacy shared counter is NOT advanced here -- it serves only
        # as a floor set by set_terminal_counter().  Copy it unchanged.
        new_state = replace(
            state,
            terminal_prefix_counters=new_prefix_counters,
        )
    else:
        # Sequential: counter advances by number of poles
        current_pin = counters.get(tag_key, 0) + 1
        pins = tuple(str(current_pin + i) for i in range(poles))
        new_counter_val = current_pin + poles - 1

        new_counters = {**counters, tag_key: new_counter_val}
        new_state = replace(state, terminal_counters=new_counters)

    return new_state, pins


@pure
def resolve_terminal_pins(
    state: GenerationState,
    terminal_tag: str,
    poles: int,
    provided_pins: tuple[str, ...] | None,
    pin_accumulator: dict[str, list[str]],
) -> tuple[GenerationState, tuple[str, ...]]:
    """Use *provided_pins* or auto-generate; appends to *pin_accumulator*."""
    if provided_pins is None:
        state, pins = next_terminal_pins(state, terminal_tag, poles)
    else:
        pins = provided_pins
    pin_accumulator.setdefault(str(terminal_tag), []).extend(pins)
    return state, pins
