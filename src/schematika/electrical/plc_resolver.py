"""PLC Module Definitions and Connection Resolver.

Defines PLC module types (hardware), rack configuration, and functions for
resolving generic PLC reference tags to specific module designations.

Tag convention: ``"PLC:{type}"`` (generic) vs ``"PLC:{type}{n}"`` (specific)
Pin label convention: ``{pin_suffix}{channel_number}``
    RTD:    "+R1", "RL1", "-R1" (suffix "+R", "RL", "-R")
    4-20mA: "Sig1", "GND1"     (suffix "Sig", "GND")
    DI/DO:  "1", "2", "3"      (suffix "")
"""

from __future__ import annotations

import re
import warnings
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from schematika.electrical.field_devices import ConnectionRow
from schematika.electrical.utils.utils import natural_sort_key

if TYPE_CHECKING:
    from schematika.electrical.model.state import GenerationState


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlcModuleType:
    """Hardware definition for a PLC I/O module.

    Attributes:
        mpn: Manufacturer part number (e.g. "750-461").
        signal_type: Signal category ("RTD", "4-20mA", "DO", "DI").
        channels: Number of I/O channels per module.
        pins_per_channel: Pin suffix strings for each channel's wires.
    """

    mpn: str
    signal_type: str
    channels: int
    pins_per_channel: tuple[str, ...]
    label_format: str = "{suffix}{channel}"


PlcRack = list[tuple[str, PlcModuleType]]
"""
A physical PLC rack: ordered list of (designation, module_type) pairs.

Example::

    rack = PlcRack([
        ("RTD1", RTD_MODULE),
        ("RTD2", RTD_MODULE),
        ("AI1",  MA_MODULE),
        ("DI1",  DI_MODULE),
        ("DO1",  DO_MODULE),
    ])
"""


@dataclass(frozen=True)
class PlcDesignation:
    """Parsed representation of a PLC tag string.

    Parses tags of the form ``"PLC:DO"``, ``"PLC:RTD:+R"``, ``"PLC:DO1"``.

    Attributes:
        type: Signal type string, e.g. ``"DO"``, ``"RTD"``, ``"AI"``.
        instance: Module instance number (1-based), or ``None`` for generic
            reference tags without a number (e.g. ``"PLC:DO"``).
        signal: Pin suffix string for multi-pin types, e.g. ``"+R"``,
            ``"Sig"``, or ``None`` for single-pin types.
    """

    type: str
    instance: int | None
    signal: str | None

    @classmethod
    def parse(cls, tag: str) -> PlcDesignation | None:
        """Parse a PLC tag string into a ``PlcDesignation``.

        Returns ``None`` if the tag does not start with ``"PLC:"``.

        Args:
            tag: A PLC tag string like ``"PLC:DO"``, ``"PLC:RTD:+R"``,
                ``"PLC:DO1"``, or ``"PLC:RTD1"``.

        Returns:
            A :class:`PlcDesignation` instance, or ``None`` if the tag is
            not a PLC tag.

        Examples::

            PlcDesignation.parse("PLC:DO")    # type="DO", instance=None, signal=None
            PlcDesignation.parse("PLC:DO1")   # type="DO", instance=1, signal=None
            PlcDesignation.parse("PLC:RTD:+R") # type="RTD", instance=None, signal="+R"
        """
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
        """Return the canonical tag string for this designation."""
        return f"PLC:{self.type}{'' if self.instance is None else self.instance}"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_plc_tag(terminal_tag: str) -> tuple[str, str]:
    """Parse a PLC terminal tag into (base_type, pin_suffix).

    Examples:
        "PLC:DO"      → ("DO", "")
        "PLC:AI:Sig"  → ("AI", "Sig")
        "PLC:RTD:+R"  → ("RTD", "+R")
    """
    parts = terminal_tag[4:].split(":")
    return parts[0], parts[1] if len(parts) > 1 else ""


def _find_modules_for_type(
    plc_type: str,
    rack: PlcRack,
) -> list[tuple[str, PlcModuleType]]:
    """Find PLC rack modules matching a PLC type string.

    First tries designation prefix match (e.g., "DI" → DI1, DI2).
    Falls back to signal_type match (e.g., "RTD" → modules with signal_type "RTD").

    Args:
        plc_type: The PLC type string to look up (e.g. "DI", "RTD", "4-20mA").
        rack: The rack to search.

    Returns:
        List of (designation, module_type) pairs from the rack that match.
    """
    modules = [(des, mod) for des, mod in rack if des.rstrip("0123456789") == plc_type]
    if modules:
        return modules
    return [(des, mod) for des, mod in rack if mod.signal_type == plc_type]


def _get_used_channels(connections: list[ConnectionRow]) -> set[tuple[str, int]]:
    """Extract PLC module channels already occupied by external connections.

    Scans the "Component To" field for "PLC:..." entries with specific
    module designations and returns a set of (designation, channel_number)
    tuples (e.g. {("DI1", 1), ("AI1", 2)}).

    Args:
        connections: List of ConnectionRow tuples to scan.

    Returns:
        Set of (designation, channel) tuples already in use.
    """
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
    """Auto-assign registry connections to free module channels.

    Sorts connections by component tag (natural order), then maps each
    to the next free channel across the provided modules, skipping
    channels already occupied by external connections.

    Args:
        conns: Registry connection objects with component_tag and component_pin.
        modules: List of (designation, module_type) pairs to fill.
        used_channels: Set of (designation, channel) tuples already occupied.

    Returns:
        List of ConnectionRow tuples mapping components to PLC pins.
    """
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
    """Auto-assign multi-pin connections (e.g. 4-20mA Sig+GND) to channels.

    Groups connections by component_tag so that all pins from the same
    component land on the same channel. Each group consumes one channel
    and each connection gets its specific pin suffix.

    Args:
        conn_pairs: List of (connection, pin_suffix) tuples.
        modules: List of (designation, module_type) pairs to fill.
        used_channels: Set of (designation, channel) tuples already occupied.

    Returns:
        List of ConnectionRow tuples mapping components to PLC pins.
    """
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
    """Resolve single-pin external PLC references (DI, DO) to specific channels.

    Sorts by terminal position so PLC channel order matches terminal strip order.

    Args:
        entries: List of (ConnectionRow, pin_suffix) tuples.
        modules: List of (designation, module_type) pairs to fill.

    Returns:
        List of ConnectionRow tuples with resolved PLC designations.
    """
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
    """Resolve multi-pin external PLC references (RTD, 4-20mA) to specific channels.

    Groups by component tag so all pins of the same device share one channel.
    Sorts groups by their lowest terminal pin so PLC channel order matches
    terminal strip order. Filters modules to those with compatible pin suffixes.

    Args:
        entries: List of (ConnectionRow, pin_suffix) tuples.
        modules: List of (designation, module_type) pairs to fill.

    Returns:
        List of ConnectionRow tuples with resolved PLC designations.
    """
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
    """Resolve PLC reference tags in a list of connections to specific module slots.

    Connections with reference-style PLC tags (e.g., ``"PLC:RTD:+R"``,
    ``"PLC:DI"``) are auto-assigned to free module channels. Non-PLC and
    already-resolved connections pass through unchanged.

    Physical terminal info (terminal tag + terminal pin) is preserved.

    Connections are sorted by terminal position so PLC channel order matches
    terminal strip order.

    Args:
        connections: Connection rows, some with generic PLC reference tags.
        rack: The PLC rack describing available modules.

    Returns:
        List of ConnectionRow tuples with all PLC references resolved
        to specific module designations and pin labels.
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
    """Extract PLC references from the circuit registry and convert to ConnectionRow format.

    Registry connections with terminal_tag like ``"PLC:DO"`` are auto-assigned to
    matching module instances (e.g., DO1, DO2), skipping channels already
    occupied by external connections to avoid conflicts.

    For multi-pin modules (e.g. 4-20mA with Sig+GND), connections are grouped
    by component tag so both pins of the same device share one channel.

    Args:
        state: Autonumbering state containing the terminal registry.
        rack: The PLC rack describing available modules.
        existing_connections: External connections already defining PLC mappings.

    Returns:
        List of ConnectionRow tuples for PLC connections found in the registry.
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
    """Generate PLC connection table by matching connections to module pins.

    Iterates the rack and fills each channel's pins with matched connections.
    Pins with a matching connection are filled in; unconnected pins are left
    empty (showing available capacity).

    Args:
        connections: All PLC connections (external + registry), with resolved
            designations (e.g. ``"PLC:DO1"``).
        rack: The PLC rack to generate the report for.

    Returns:
        List of ``(Module, MPN, PLC Pin, Component, Pin, Terminal)`` tuples.
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
