"""PLC module definitions and reference resolver.

Tag form: `PLC:{type}` (generic) vs `PLC:{type}{n}` (specific).
Pin labels: `{suffix}{channel}` — RTD `+R/RL/-R`, 4-20mA `Sig/GND`, DI/DO no suffix.
"""

from __future__ import annotations

import re
import warnings
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from schematika.electrical.utils.utils import natural_sort_key

if TYPE_CHECKING:
    from schematika.electrical.field_devices import ConnectionRow
    from schematika.electrical.model.state import GenerationState


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlcModuleType:
    """Hardware definition for one PLC I/O module type.

    Used to build a :data:`PlcRack` for :func:`resolve_plc_references` and
    :func:`extract_plc_connections_from_registry`.

    Attributes:
        mpn: Manufacturer part number, e.g. ``"6ES7 321-1BL00-0AA0"``.
        signal_type: Signal category, e.g. ``"DI"``, ``"DO"``, ``"AI"``,
            ``"RTD"``.
        channels: Number of I/O channels on this module.
        pins_per_channel: Suffix(es) per channel, e.g. ``("",)`` for DI/DO,
            ``("+R", "RL", "-R")`` for RTD.
        label_format: Python format string for pin labels; default
            ``"{suffix}{channel}"``.

    Examples:
        >>> from schematika.electrical import PlcModuleType
        >>> mod = PlcModuleType(
        ...     mpn="DI16", signal_type="DI", channels=16,
        ...     pins_per_channel=("",))
        >>> mod.channels
        16
        >>> mod.signal_type
        'DI'
    """

    mpn: str
    signal_type: str
    channels: int
    pins_per_channel: tuple[str, ...]
    label_format: str = "{suffix}{channel}"


PlcRack = list[tuple[str, PlcModuleType]]
"""A physical PLC rack: ordered list of (designation, module_type) pairs."""


@dataclass(frozen=True)
class PlcDesignation:
    """Parsed PLC tag; `instance=None` for generic refs like `PLC:DO`/`PLC:RTD:+R`."""

    type: str
    instance: int | None
    signal: str | None

    @classmethod
    def parse(cls, tag: str) -> PlcDesignation | None:
        """Returns None if *tag* does not start with `PLC:`."""
        if not tag.startswith("PLC:"):
            return None
        rest = tag[4:]  # strip "PLC:"
        parts = rest.split(":", 1)
        type_and_num = parts[0]
        signal = parts[1] if len(parts) > 1 else None

        # Split trailing digits from the type string
        m = re.match(r"^([A-Za-z\-]+)(\d+)?$", type_and_num)
        if m:
            plc_type = m.group(1)
            instance = int(m.group(2)) if m.group(2) else None
        else:
            plc_type = type_and_num
            instance = None

        return cls(type=plc_type, instance=instance, signal=signal)

    def __str__(self) -> str:
        """Canonical tag string."""
        return f"PLC:{self.type}{'' if self.instance is None else self.instance}"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_plc_tag(terminal_tag: str) -> tuple[str, str]:
    """Returns (base_type, pin_suffix); e.g. `"PLC:RTD:+R"` -> `("RTD", "+R")`."""
    parts = terminal_tag[4:].split(":")
    return parts[0], parts[1] if len(parts) > 1 else ""


def _find_modules_for_type(
    plc_type: str,
    rack: PlcRack,
) -> list[tuple[str, PlcModuleType]]:
    """Designation prefix match first (`"DI"` -> `DI1`); else `signal_type` match."""
    modules = [(des, mod) for des, mod in rack if des.rstrip("0123456789") == plc_type]
    if modules:
        return modules
    return [(des, mod) for des, mod in rack if mod.signal_type == plc_type]


def _get_used_channels(connections: list[ConnectionRow]) -> set[tuple[str, int]]:
    """Returns {(designation, channel)} for specific PLC designations only."""
    used: set[tuple[str, int]] = set()
    for row in connections:
        comp_to = row[4]
        if not comp_to or not comp_to.startswith("PLC:"):
            continue
        designation = comp_to[4:]
        # Only count specific designations (with digits), not reference tags
        if not any(c.isdigit() for c in designation):
            continue
        pin_label = row[5]
        channel = "".join(c for c in pin_label if c.isdigit())
        if channel:
            used.add((designation, int(channel)))
    return used


def _assign_connections_to_modules(
    conns: list[Any],
    modules: list[tuple[str, PlcModuleType]],
    used_channels: set[tuple[str, int]] | None = None,
) -> list[ConnectionRow]:
    """Single-pin auto-assign sorted by component tag, skipping `used_channels`."""
    used_channels = used_channels or set()
    conns.sort(key=lambda c: natural_sort_key(c.component_tag))

    free_slots: list[tuple[str, PlcModuleType, int]] = [
        (des, mod, ch)
        for des, mod in modules
        for ch in range(1, mod.channels + 1)
        if (des, ch) not in used_channels
    ]

    rows: list[ConnectionRow] = []
    for conn, (des, mod, ch) in zip(conns, free_slots, strict=False):
        pin_label = mod.label_format.format(suffix=mod.pins_per_channel[0], channel=ch)
        rows.append(
            (conn.component_tag, conn.component_pin, "", "", f"PLC:{des}", pin_label)
        )

    if len(conns) > len(free_slots):
        overflow = len(conns) - len(free_slots)
        plc_type = modules[0][0].rstrip("0123456789")
        warnings.warn(
            f"WARNING: {overflow} {plc_type} connection(s) could not be assigned "
            f"— not enough free PLC channels.",
            stacklevel=2,
        )

    return rows


def _assign_multi_pin_connections(
    conn_pairs: list[tuple[Any, str]],
    modules: list[tuple[str, PlcModuleType]],
    used_channels: set[tuple[str, int]] | None = None,
) -> list[ConnectionRow]:
    """Groups by component tag so all pins of one device share a channel."""
    used_channels = used_channels or set()

    # Filter to modules whose pins match the required suffixes
    required_suffixes = {suffix for _, suffix in conn_pairs if suffix}
    compatible_modules = [
        (des, mod)
        for des, mod in modules
        if required_suffixes.issubset(set(mod.pins_per_channel))
    ]

    # Group by component tag — each component gets one channel
    by_component: dict[str, list[tuple[Any, str]]] = defaultdict(list)
    for conn, suffix in conn_pairs:
        by_component[conn.component_tag].append((conn, suffix))

    sorted_components = sorted(by_component.keys(), key=natural_sort_key)

    free_slots: list[tuple[str, PlcModuleType, int]] = [
        (des, mod, ch)
        for des, mod in compatible_modules
        for ch in range(1, mod.channels + 1)
        if (des, ch) not in used_channels
    ]

    rows: list[ConnectionRow] = []
    slot_idx = 0
    for comp_tag in sorted_components:
        if slot_idx >= len(free_slots):
            break
        des, mod, ch = free_slots[slot_idx]
        slot_idx += 1

        for conn, suffix in by_component[comp_tag]:
            pin_label = mod.label_format.format(suffix=suffix, channel=ch)
            rows.append(
                (
                    conn.component_tag,
                    conn.component_pin,
                    "",
                    "",
                    f"PLC:{des}",
                    pin_label,
                )
            )

    overflow = len(sorted_components) - slot_idx
    if overflow > 0:
        plc_type = modules[0][0].rstrip("0123456789") if modules else "?"
        warnings.warn(
            f"WARNING: {overflow} {plc_type} connection(s) could not be assigned "
            f"— not enough free PLC channels.",
            stacklevel=2,
        )

    return rows


def _resolve_single_pin_external(
    entries: list[tuple[ConnectionRow, str]],
    modules: list[tuple[str, PlcModuleType]],
) -> list[ConnectionRow]:
    """Sorts by terminal position so PLC channel order matches terminal strip order."""
    entries.sort(
        key=lambda e: (natural_sort_key(str(e[0][2])), natural_sort_key(e[0][3]))
    )

    free_slots: list[tuple[str, PlcModuleType, int]] = [
        (des, mod, ch) for des, mod in modules for ch in range(1, mod.channels + 1)
    ]

    rows: list[ConnectionRow] = []
    for (row, _), (des, mod, ch) in zip(entries, free_slots, strict=False):
        pin_label = mod.label_format.format(suffix=mod.pins_per_channel[0], channel=ch)
        rows.append((row[0], row[1], row[2], row[3], f"PLC:{des}", pin_label))

    if len(entries) > len(free_slots):
        overflow = len(entries) - len(free_slots)
        plc_type = modules[0][0].rstrip("0123456789")
        warnings.warn(
            f"WARNING: {overflow} {plc_type} external connection(s) could not be "
            f"assigned — not enough free PLC channels.",
            stacklevel=2,
        )

    return rows


def _resolve_multi_pin_external(
    entries: list[tuple[ConnectionRow, str]],
    modules: list[tuple[str, PlcModuleType]],
) -> list[ConnectionRow]:
    """Groups sorted by lowest terminal pin so channel order follows the strip."""
    required_suffixes = {suffix for _, suffix in entries if suffix}
    compatible_modules = [
        (des, mod)
        for des, mod in modules
        if required_suffixes.issubset(set(mod.pins_per_channel))
    ]

    by_component: dict[str, list[tuple[ConnectionRow, str]]] = defaultdict(list)
    for row, suffix in entries:
        by_component[row[0]].append((row, suffix))

    sorted_components = sorted(
        by_component.keys(),
        key=lambda tag: min(
            (natural_sort_key(str(row[2])), natural_sort_key(row[3]))
            for row, _ in by_component[tag]
        ),
    )

    free_slots: list[tuple[str, PlcModuleType, int]] = [
        (des, mod, ch)
        for des, mod in compatible_modules
        for ch in range(1, mod.channels + 1)
    ]

    rows: list[ConnectionRow] = []
    slot_idx = 0
    for comp_tag in sorted_components:
        if slot_idx >= len(free_slots):
            break
        des, mod, ch = free_slots[slot_idx]
        slot_idx += 1

        for row, suffix in by_component[comp_tag]:
            pin_label = mod.label_format.format(suffix=suffix, channel=ch)
            rows.append((row[0], row[1], row[2], row[3], f"PLC:{des}", pin_label))

    overflow = len(sorted_components) - slot_idx
    if overflow > 0:
        plc_type = modules[0][0].rstrip("0123456789") if modules else "?"
        warnings.warn(
            f"WARNING: {overflow} {plc_type} external connection(s) could not be "
            f"assigned — not enough free PLC channels.",
            stacklevel=2,
        )

    return rows


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_plc_references(
    connections: list[ConnectionRow],
    rack: PlcRack,
) -> list[ConnectionRow]:
    """Replace generic PLC reference tags with specific channel designations.

    Generic tags (e.g. ``"PLC:DI"``) are assigned to free channels on the
    matching rack module. Specific tags (e.g. ``"PLC:DI1"``) pass through
    unchanged. Rows without a ``"PLC:"`` prefix are also passed through.

    Args:
        connections: Connection rows, typically from
            :func:`generate_field_connections`.
        rack: Ordered list of ``(designation, PlcModuleType)`` pairs defining
            the physical PLC rack layout.

    Returns:
        New connection list with generic PLC tags replaced by specific
        designations and channel pin labels.

    Examples:
        >>> from schematika.electrical import PlcModuleType, resolve_plc_references
        >>> mod = PlcModuleType(
        ...     mpn="DI8", signal_type="DI", channels=2, pins_per_channel=("",))
        >>> rack = [("DI1", mod)]
        >>> rows = [("TT-101", "1", None, "", "PLC:DI", "")]
        >>> resolved = resolve_plc_references(rows, rack)
        >>> resolved[0][4]
        'PLC:DI1'
    """
    resolved: list[ConnectionRow] = []
    unresolved_by_type: dict[str, list[tuple[ConnectionRow, str]]] = defaultdict(list)

    for row in connections:
        comp_to = row[4]
        if not comp_to or not comp_to.startswith("PLC:"):
            resolved.append(row)
            continue

        base_type, pin_suffix = _parse_plc_tag(comp_to)

        # Already a specific designation (has digits like "AI1", "DI2")
        if any(c.isdigit() for c in base_type):
            resolved.append(row)
            continue

        unresolved_by_type[base_type].append((row, pin_suffix))

    for plc_type, entries in unresolved_by_type.items():
        modules = _find_modules_for_type(plc_type, rack)

        if not modules:
            for row, _ in entries:
                resolved.append(row)
            continue

        has_suffixes = any(suffix for _, suffix in entries)
        has_unsuffixed = any(not suffix for _, suffix in entries)

        if has_suffixes and has_unsuffixed:
            # Mixed tag types for the same PLC type — cannot route correctly
            warnings.warn(
                f"PLC type '{plc_type}' has a mix of suffixed (multi-pin) and "
                f"unsuffixed (single-pin) reference tags. These connections cannot "
                f"be routed and will be dropped.",
                stacklevel=2,
            )
            continue  # skip this type entirely — don't silently drop

        if has_suffixes:
            resolved.extend(_resolve_multi_pin_external(entries, modules))
        else:
            resolved.extend(_resolve_single_pin_external(entries, modules))

    return resolved


def extract_plc_connections_from_registry(
    state: GenerationState,
    rack: PlcRack,
    existing_connections: list[ConnectionRow] | None = None,
) -> list[ConnectionRow]:
    """Extract PLC connections logged via :func:`~schematika.electrical.log_connection`.

    Reads all connections with a ``"PLC:"`` terminal tag from the state's
    terminal registry and assigns them to free rack channels. Channels already
    present in ``existing_connections`` are skipped so explicit mappings take
    precedence.

    Args:
        state: Generation state containing the terminal registry.
        rack: Ordered ``(designation, PlcModuleType)`` pairs for the rack.
        existing_connections: Already-resolved connections to treat as occupied;
            ``None`` is equivalent to an empty list.

    Returns:
        List of :data:`ConnectionRow` tuples with specific PLC channel labels.

    Examples:
        >>> from schematika.electrical import (
        ...     create_initial_state, PlcModuleType,
        ...     extract_plc_connections_from_registry)
        >>> state = create_initial_state()
        >>> mod = PlcModuleType(
        ...     mpn="DI8", signal_type="DI", channels=8, pins_per_channel=("",))
        >>> rack = [("DI1", mod)]
        >>> rows = extract_plc_connections_from_registry(state, rack)
        >>> rows  # empty — no PLC connections logged
        []
    """
    from schematika.electrical.system.connection_registry import get_registry

    registry = get_registry(state)
    used_channels = _get_used_channels(existing_connections or [])

    # Group by base PLC type, preserving pin suffix for multi-pin modules
    plc_by_type: dict[str, list[tuple[Any, str]]] = defaultdict(list)
    for conn in registry.connections:
        if conn.terminal_tag.startswith("PLC:"):
            base_type, pin_suffix = _parse_plc_tag(conn.terminal_tag)
            plc_by_type[base_type].append((conn, pin_suffix))

    rows: list[ConnectionRow] = []

    for plc_type, conn_pairs in plc_by_type.items():
        modules = _find_modules_for_type(plc_type, rack)

        if not modules:
            continue

        has_suffixes = any(suffix for _, suffix in conn_pairs)

        if has_suffixes:
            rows.extend(
                _assign_multi_pin_connections(conn_pairs, modules, used_channels)
            )
        else:
            conns = [c for c, _ in conn_pairs]
            rows.extend(_assign_connections_to_modules(conns, modules, used_channels))

    return rows


def generate_plc_report_rows(
    connections: list[ConnectionRow],
    rack: PlcRack,
) -> list[tuple[str, str, str, str, str, str]]:
    """Build a full PLC I/O report table with one row per channel pin.

    Iterates the rack in order, emitting one row per ``(module, channel, pin)``
    combination. Connected channels show the field device and terminal
    information; unconnected channels emit blank fields so the full module
    capacity is always visible.

    Args:
        connections: Fully resolved connection rows (specific PLC designations).
        rack: Ordered ``(designation, PlcModuleType)`` pairs defining the rack.

    Returns:
        List of ``(designation, mpn, pin_label, component_tag, component_pin,
        terminal_str)`` tuples — one per channel pin, connected or not.

    Examples:
        >>> from schematika.electrical import PlcModuleType, generate_plc_report_rows
        >>> mod = PlcModuleType(
        ...     mpn="DI8", signal_type="DI", channels=2, pins_per_channel=("",))
        >>> rack = [("DI1", mod)]
        >>> rows = generate_plc_report_rows([], rack)
        >>> len(rows)
        2
        >>> rows[0][0]
        'DI1'
    """
    plc_conns: dict[tuple[str, str], ConnectionRow] = {}
    for row in connections:
        _from_comp, _from_pin, _terminal, _terminal_pin, to, to_pin = row
        if to.startswith("PLC:"):
            designation = to[4:]
            plc_conns[(designation, to_pin)] = row

    rows: list[tuple[str, str, str, str, str, str]] = []

    for designation, module_type in rack:
        for ch in range(1, module_type.channels + 1):
            for pin_suffix in module_type.pins_per_channel:
                pin_label = module_type.label_format.format(
                    suffix=pin_suffix, channel=ch
                )
                conn = plc_conns.get((designation, pin_label))

                if conn:
                    from_comp, from_pin, terminal, terminal_pin, _, _ = conn
                    terminal_str = f"{terminal}:{terminal_pin}" if terminal else ""
                    rows.append(
                        (
                            designation,
                            module_type.mpn,
                            pin_label,
                            from_comp,
                            from_pin,
                            terminal_str,
                        )
                    )
                else:
                    rows.append(
                        (
                            designation,
                            module_type.mpn,
                            pin_label,
                            "",
                            "",
                            "",
                        )
                    )

    return rows
