"""TerminalRegistry accessors + CSV export."""

import csv
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

# Connection and TerminalRegistry now live in core/; re-exported here for
# backward compatibility so that all existing imports from this module work.
from schematika.core.connection_registry import (
    Connection,
    TerminalRegistry,
)

if TYPE_CHECKING:
    from schematika.electrical.model.state import GenerationState

__all__ = [
    "Connection",
    "TerminalRegistry",
    "export_registry_to_csv",
    "get_registry",
    "log_connection",
    "register_3phase_connections",
    "register_3phase_input",
    "register_3phase_output",
    "update_registry",
]


def get_registry(state: "GenerationState") -> TerminalRegistry:
    """Retrieves the TerminalRegistry from the state."""
    return state.terminal_registry


def update_registry(
    state: "GenerationState", registry: TerminalRegistry
) -> "GenerationState":
    """Updates the state with the new registry."""
    return replace(state, terminal_registry=registry)


def log_connection(
    state: "GenerationState",
    terminal_tag: str,
    terminal_pin: str,
    component_tag: str,
    component_pin: str,
    side: str = "bottom",
) -> "GenerationState":
    """Functional helper to register a connection in the state."""
    reg = get_registry(state)
    new_reg = reg.add_connection(
        terminal_tag, terminal_pin, component_tag, component_pin, side
    )
    return update_registry(state, new_reg)


def register_3phase_connections(
    state: "GenerationState",
    terminal_tag: str,
    terminal_pins: tuple[str, ...],
    component_tag: str,
    component_pins: tuple[str, ...],
    side: str = "bottom",
) -> "GenerationState":
    """Logs L1/L2/L3 in one call (3 connections)."""
    for i in range(min(3, len(terminal_pins), len(component_pins))):
        state = log_connection(
            state,
            terminal_tag,
            terminal_pins[i],
            component_tag,
            component_pins[i],
            side,
        )
    return state


def register_3phase_input(
    state: "GenerationState",
    terminal_tag: str,
    terminal_pins: tuple[str, ...],
    component_tag: str,
    component_pins: tuple[str, ...] = ("1", "3", "5"),
) -> "GenerationState":
    """Default input pins 1/3/5 (L1/L2/L3); bottom side."""
    return register_3phase_connections(
        state, terminal_tag, terminal_pins, component_tag, component_pins, side="bottom"
    )


def register_3phase_output(
    state: "GenerationState",
    terminal_tag: str,
    terminal_pins: tuple[str, ...],
    component_tag: str,
    component_pins: tuple[str, ...] = ("2", "4", "6"),
) -> "GenerationState":
    """Default output pins 2/4/6 (T1/T2/T3); top side."""
    return register_3phase_connections(
        state, terminal_tag, terminal_pins, component_tag, component_pins, side="top"
    )


def _build_all_pin_keys(
    grouped: dict,
    state: "GenerationState | None",
) -> list[tuple[str, str]]:
    """Includes empty pin slots up to the highest allocated, per terminal."""
    if state is None:
        return sorted(grouped.keys(), key=_pin_sort_key)

    # Only fill gaps for terminals that have at least one registered connection.
    # This avoids generating empty rows for filtered-out terminals (e.g. PLC).
    registry_tags: set[str] = {tag for tag, _ in grouped}
    prefix_counters: dict[str, dict[str, int]] = state.terminal_prefix_counters
    seq_counters: dict[str, int] = state.terminal_counters

    all_keys: set[tuple[str, str]] = set(grouped.keys())

    for tag in registry_tags:
        if prefix_counters.get(tag):
            # Prefixed terminal -- enumerate prefix:1 .. prefix:max for each prefix
            for prefix, max_num in prefix_counters[tag].items():
                for n in range(1, max_num + 1):
                    all_keys.add((tag, f"{prefix}:{n}"))
        elif tag in seq_counters:
            # Sequential terminal -- enumerate 1 .. max
            for n in range(1, seq_counters[tag] + 1):
                all_keys.add((tag, str(n)))

    return sorted(all_keys, key=_pin_sort_key)


def _pin_sort_key(k: tuple[str, str]) -> tuple:
    """Sort key for (terminal_tag, pin) pairs."""
    t, p = k
    p_str = str(p)
    # Handle "prefix:number" format (e.g. "L1:3")
    if ":" in p_str:
        prefix, num_str = p_str.rsplit(":", 1)
        try:
            return (t, 0, prefix, int(num_str))
        except ValueError:
            pass
    try:
        return (t, 1, "", int(p_str))  # Numeric pins sort first
    except (ValueError, TypeError):
        return (t, 2, "", 0, p_str)  # Non-numeric pins sort last


def export_registry_to_csv(
    registry: TerminalRegistry,
    filepath: str,
    state: "GenerationState | None" = None,
) -> None:
    """When *state* is given, includes placeholder rows for unconnected pins."""
    # Group by (Tag, Pin)
    # Result: Map[(Tag, Pin), {'top': [], 'bottom': []}]  # noqa: ERA001
    from collections import defaultdict

    grouped = defaultdict(lambda: {"top": [], "bottom": []})

    for conn in registry.connections:
        key = (conn.terminal_tag, conn.terminal_pin)
        grouped[key][conn.side].append(conn)

    sorted_keys = _build_all_pin_keys(grouped, state)

    with Path(filepath).open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Component From",
                "Pin From",
                "Terminal Tag",
                "Terminal Pin",
                "Component To",
                "Pin To",
            ]
        )

        for t_tag, t_pin in sorted_keys:
            data = grouped.get((t_tag, t_pin))

            if data:
                # Format Top side (usually "From")
                # Usually 'top' connections go to components inside the panel
                top_conns = data["top"]
                from_comp = " / ".join(c.component_tag for c in top_conns)
                from_pin = " / ".join(c.component_pin for c in top_conns)

                # Format Bottom side (usually "To")
                # Usually 'bottom' connections go to field
                bot_conns = data["bottom"]
                to_comp = " / ".join(c.component_tag for c in bot_conns)
                to_pin = " / ".join(c.component_pin for c in bot_conns)

                writer.writerow([from_comp, from_pin, t_tag, t_pin, to_comp, to_pin])
            else:
                # Empty slot -- pin was allocated but has no connections
                writer.writerow(["", "", t_tag, t_pin, "", ""])
