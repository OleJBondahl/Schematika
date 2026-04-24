"""Autonumbering utilities for component tags and terminal pins.

This module provides functional utilities for automatically numbering components
and terminals in electrical schematics. It uses a counter-based approach that
generates sequential numbers for tags with the same prefix letter.

Example:
    >>> state = create_autonumberer()
    >>> state, tag1 = next_tag(state, "F")
    >>> tag1
    'F1'
    >>> state, tag2 = next_tag(state, "F")
    >>> tag2
    'F2'
"""

from dataclasses import replace

from schematika.core.state import GenerationState, create_initial_state


def create_autonumberer() -> GenerationState:
    """Create a new autonumbering state.

    Returns:
        GenerationState: Fresh state with all counters initialized to defaults.
    """
    return create_initial_state()


def get_tag_number(state: GenerationState, prefix: str) -> int:
    """Get the current number for a tag prefix.

    Args:
        state: The autonumbering state.
        prefix: The tag prefix (e.g., "F", "Q", "X").

    Returns:
        int: The current number for this prefix (0 if not yet used).
    """
    return state.tags.get(prefix, 0)


def _increment_tag(state: GenerationState, prefix: str) -> GenerationState:
    """Increment the counter for a tag prefix and return new state.

    Args:
        state: The current autonumbering state.
        prefix: The tag prefix to increment.

    Returns:
        GenerationState: New state with incremented counter.
    """
    new_tags = {**state.tags, prefix: get_tag_number(state, prefix) + 1}
    return replace(state, tags=new_tags)


def _format_tag(prefix: str, number: int) -> str:
    """Format a tag with prefix and number.

    Args:
        prefix: The tag prefix (e.g., "F", "Q", "X").
        number: The tag number.

    Returns:
        str: Formatted tag (e.g., "F1", "Q2", "X3").
    """
    return f"{prefix}{number}"


def next_tag(state: GenerationState, prefix: str) -> tuple[GenerationState, str]:
    """Get the next tag for a prefix and return updated state.

    This is a convenience function that combines increment_tag and format_tag.

    Args:
        state: The current autonumbering state.
        prefix: The tag prefix.

    Returns:
        tuple[GenerationState, str]: Updated state and formatted tag.

    Example:
        >>> state = create_autonumberer()
        >>> state, tag1 = next_tag(state, "F")
        >>> print(tag1)  # "F1"
        >>> state, tag2 = next_tag(state, "F")
        >>> print(tag2)  # "F2"
    """
    new_state = _increment_tag(state, prefix)
    tag = _format_tag(prefix, get_tag_number(new_state, prefix))
    return new_state, tag


def next_terminal_pins(
    state: GenerationState,
    terminal_tag: str,
    poles: int = 3,
    pin_prefixes: tuple[str, ...] | None = None,
) -> tuple[GenerationState, tuple[str, ...]]:
    """Generate sequential terminal pins for a specific terminal strip.

    When ``pin_prefixes`` are available (either passed explicitly or read
    from a :class:`Terminal` object's ``pin_prefixes`` attribute), pins are
    formatted as ``"<prefix>:<group_number>"``.  Each prefix has its own
    counter so that using a subset of prefixes (e.g. only ``L1``) does not
    advance the counters for unused prefixes (e.g. ``L2``, ``L3``).
    The group number for a multi-prefix allocation is the maximum of all
    requested per-prefix counters (plus one), ensuring consistent group
    numbers within a single allocation.

    Without ``pin_prefixes``, plain sequential numbers are generated and the
    counter advances by *poles*.

    Args:
        state: The current autonumbering state.
        terminal_tag: The tag of the terminal strip (e.g. "X1", "X2").
            May be a :class:`Terminal` instance carrying ``pin_prefixes``.
        poles: Number of poles (default 3 for three-phase).
        pin_prefixes: Optional explicit prefixes that override the attribute
            on *terminal_tag*.

    Returns:
        Tuple containing updated state and pin number tuple.
    """
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


def resolve_terminal_pins(
    state: GenerationState,
    terminal_tag: str,
    poles: int,
    provided_pins: tuple[str, ...] | None,
    pin_accumulator: dict[str, list[str]],
) -> tuple[GenerationState, tuple[str, ...]]:
    """Resolve terminal pins: use provided pins or auto-generate them.

    Combines the common pattern of conditionally calling next_terminal_pins()
    and accumulating the result into a pin_accumulator dict.

    Args:
        state: The current autonumbering state.
        terminal_tag: The terminal strip tag (e.g. "X1").
        poles: Number of poles to generate.
        provided_pins: Explicit pins to use, or None to auto-generate.
        pin_accumulator: Dict to extend with the resolved pins.

    Returns:
        Tuple of (updated state, resolved pins).
    """
    if provided_pins is None:
        state, pins = next_terminal_pins(state, terminal_tag, poles)
    else:
        pins = provided_pins
    pin_accumulator.setdefault(str(terminal_tag), []).extend(pins)
    return state, pins
