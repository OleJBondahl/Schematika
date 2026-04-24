"""Field device templates and connection generation.

Provides reusable data types for describing how field devices (sensors,
valves, motors, power feeds) connect to cabinet terminals and PLC modules.
Each device is described by a ``DeviceTemplate`` containing an ordered
tuple of ``PinDef`` entries.  The ``generate_field_connections()`` function
expands a list of device declarations into ``ConnectionRow`` tuples with
auto-numbered terminal pins and PLC reference tags.

Usage example::

    from schematika.electrical import Terminal
    from schematika.electrical.field_devices import (
        PinDef, DeviceTemplate, generate_field_connections,
    )

    # Define terminals
    SIGNAL = Terminal("X100", "Signal terminal")
    PLC_AI = Terminal("PLC:AI", reference=True)

    # Define a device template
    SENSOR_4_20 = DeviceTemplate(
        mpn="4-20mA Transmitter",
        pins=(
            PinDef("Sig+", SIGNAL, PLC_AI),
            PinDef("GND", SIGNAL),
        ),
    )

    # Expand into connection rows
    rows = generate_field_connections([
        ("PT-01", SENSOR_4_20),
        ("PT-02", SENSOR_4_20),
    ])
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Union

from schematika.core.exceptions import CircuitValidationError

if TYPE_CHECKING:
    from schematika.electrical.builder import BuildResult
    from schematika.electrical.terminal import Terminal

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

ConnectionRow = tuple[str, str, Any, str, str, str]
"""
A single connection row in the field wiring report.

Fields: (component_from, pin_from, terminal, terminal_pin, component_to, pin_to)

- component_from: Device tag (e.g., "PT-01").
- pin_from: Device pin name (e.g., "Sig+").
- terminal: Terminal object or tag string for the terminal block.
- terminal_pin: Resolved pin number on the terminal block.
- component_to: PLC reference tag or empty string.
- pin_to: Currently unused (empty string), reserved for PLC pin.
"""

DeviceEntry = Union[
    tuple[str, "DeviceTemplate"],
    tuple[str, "DeviceTemplate", "Terminal"],
]
"""
A device declaration for ``generate_field_connections()``.

Either ``(tag, template)`` — terminal comes from each PinDef — or
``(tag, template, terminal_override)`` — the override terminal is used
for any pin that has no terminal in its PinDef.
"""


# ---------------------------------------------------------------------------
# Core data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConnectorData:
    """Physical connector properties for one connector on a field device."""

    pins: tuple[str, ...]
    """Device pins this connector covers."""
    type: str | None = None
    """WireViz type (e.g. "Crimp ferrule", "M12")."""
    subtype: str | None = None
    """WireViz subtype (e.g. "female", "0.75mm²")."""
    style: str | None = None
    """WireViz style (e.g. "simple" for ferrules)."""
    notes: str | None = None
    """Free text shown on diagram."""
    loops: tuple[tuple[int | str, int | str], ...] | None = None
    """Pin pairs to show as internal jumpers (WireViz ``loops``)."""


@dataclass(frozen=True)
class CableData:
    """Physical cable properties for a field device connection."""

    wire_gauge: float
    """Wire cross-section in mm²."""
    wire_colour: str | None = None
    """Wire colour code, e.g. "BK", "RD"."""
    wire_colors: tuple[str, ...] | None = None
    """Per-wire color codes in order, e.g. ("BN", "BU", "GNYE")."""
    cable_length: float | None = None
    """Cable length in mm."""
    cable_note: str | None = None
    """Free-text note, e.g. "3P+PE", "Shielded"."""
    category: str = "cable"
    """WireViz category: "cable" or "bundle"."""


@dataclass(frozen=True)
class DeviceCable:
    """One cable+connector pair on a multi-cable device.

    Groups a subset of device pins into a single cable with its own
    physical properties and optional connector.
    """

    pins: tuple[str, ...]
    """Which device pins use this cable."""
    cable: CableData
    """Wire gauge, colors, category, etc."""
    connector: ConnectorData | None = None
    """Physical connector (cable gland, ferrule, etc.)."""


@dataclass(frozen=True)
class FieldDevice:
    """A specific field device instance with its connection template and optional cable
    data.
    """

    tag: str
    """Device tag, e.g. "PU-01-CX"."""
    template: DeviceTemplate
    """Connection pattern defining pins and terminal assignments."""
    terminal: Terminal | None = None
    """Device-level terminal override (used when PinDef has no terminal)."""
    cable: CableData | None = None
    """Physical cable properties (single-cable devices)."""
    connectors: tuple[ConnectorData, ...] | None = None
    """Physical connector properties (single-cable devices)."""
    cables: tuple[DeviceCable, ...] | None = None
    """Multiple cable+connector pairs (multi-cable devices like valves)."""


@dataclass(frozen=True)
class PinDef:
    """Defines one pin on a field device template.

    Pin numbering modes (mutually exclusive):

    - **Sequential** (default): auto-numbered ``"1"``, ``"2"``, ``"3"``...
      per terminal block.
    - **Prefixed** (``pin_prefix="L1"``): formatted ``"{prefix}:{index}"``.
      All prefixed pins on the same device share one group index per
      terminal.
    - **Fixed** (``terminal_pin="L1"``): literal pin name, no auto-numbering.

    Attributes:
        device_pin: Pin name on the physical device (e.g., ``"R+"``,
            ``"U1"``, ``"1"``).
        terminal: Physical terminal block.  ``None`` means use the
            device-level terminal override.
        plc: PLC reference terminal for auto-assignment.  ``None``
            means no PLC connection.
        terminal_pin: Fixed terminal pin name (skips auto-numbering).
        pin_prefix: Formatted prefix for auto-indexed pins.
    """

    device_pin: str
    terminal: Terminal | None = None
    plc: Terminal | None = None
    terminal_pin: str = ""
    pin_prefix: str = ""


@dataclass(frozen=True)
class SequentialPin(PinDef):
    """Auto-numbered terminal slot.

    Cannot have pin_prefix or terminal_pin — both must be empty.
    Terminal pin is assigned automatically as "1", "2", "3"...
    """

    def __post_init__(self) -> None:
        if self.pin_prefix:
            raise CircuitValidationError(
                f"SequentialPin '{self.device_pin}': pin_prefix must be empty "
                f"(use PrefixedPin for prefix-numbered pins)"
            )
        if self.terminal_pin:
            raise CircuitValidationError(
                f"SequentialPin '{self.device_pin}': terminal_pin must be empty "
                f"(use FixedPin for literal pin names)"
            )


@dataclass(frozen=True)
class PrefixedPin(PinDef):
    """Prefix-numbered terminal slot (e.g. 'L1:1', 'L2:1').

    Requires pin_prefix; cannot have terminal_pin.
    Terminal pin is formatted as "{pin_prefix}:{group_index}".
    """

    def __post_init__(self) -> None:
        if not self.pin_prefix:
            raise CircuitValidationError(
                f"PrefixedPin '{self.device_pin}': pin_prefix is required"
            )
        if self.terminal_pin:
            raise CircuitValidationError(
                f"PrefixedPin '{self.device_pin}': terminal_pin must be empty "
                f"(use FixedPin for literal pin names)"
            )


@dataclass(frozen=True)
class FixedPin(PinDef):
    """Fixed terminal pin name (e.g. 'L1', 'PE').

    Requires terminal_pin; cannot have pin_prefix.
    Terminal pin is used literally without any auto-numbering.
    """

    def __post_init__(self) -> None:
        if not self.terminal_pin:
            raise CircuitValidationError(
                f"FixedPin '{self.device_pin}': terminal_pin is required"
            )
        if self.pin_prefix:
            raise CircuitValidationError(
                f"FixedPin '{self.device_pin}': pin_prefix must be empty "
                f"(use PrefixedPin for prefix-numbered pins)"
            )


@dataclass(frozen=True)
class DeviceTemplate:
    """Reusable connection pattern for a field device type.

    Attributes:
        mpn: Manufacturer part number or type description.
        pins: Ordered pin definitions for this device.
    """

    mpn: str
    pins: tuple[PinDef, ...]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_terminal_pin(
    pin_def: PinDef,
    terminal_key: str,
    device_prefix_indices: dict[str, int],
    device_prefixes_used: dict[str, set[str]],
    prefix_counters: dict[str, dict[str, int]],
    sequential_counters: dict[str, int],
    reuse_iters: dict[str, Any],
    reserved_pins: dict[str, set[str]] | None = None,
) -> str:
    """Resolve the terminal pin string for a single pin definition.

    This implements the three mutually-exclusive numbering modes
    described in :class:`PinDef`.
    """
    # Mode 1: Fixed pin — use as-is.
    if pin_def.terminal_pin:
        return pin_def.terminal_pin

    # Mode 2: Prefixed pin — group-based numbering.
    if pin_def.pin_prefix:
        if terminal_key not in device_prefix_indices:
            # Compute group number from per-prefix counters for only the
            # prefixes this device uses on this terminal.  A device that
            # uses only N will not advance the L counter.
            tag_counters = prefix_counters.get(terminal_key, {})
            prefixes = device_prefixes_used.get(terminal_key, set())
            max_existing = max(
                (tag_counters.get(p, 0) for p in prefixes),
                default=0,
            )
            new_group = max_existing + 1
            device_prefix_indices[terminal_key] = new_group
            # Update per-prefix counters for the prefixes this device uses
            if terminal_key not in prefix_counters:
                prefix_counters[terminal_key] = {}
            for p in prefixes:
                prefix_counters[terminal_key][p] = new_group

        return f"{pin_def.pin_prefix}:{device_prefix_indices[terminal_key]}"

    # Mode 3: Sequential — consume from reuse iterator or auto-increment.
    if terminal_key in reuse_iters:
        return next(reuse_iters[terminal_key])

    seq = sequential_counters.get(terminal_key, 0) + 1
    if reserved_pins:
        skip = reserved_pins.get(terminal_key, set())
        while str(seq) in skip:
            seq += 1
    sequential_counters[terminal_key] = seq
    return str(seq)


def _build_reuse_iters(
    reuse_terminals: dict[str, list[str] | BuildResult] | None,
) -> dict[str, Any]:
    """Build reuse iterators from a ``reuse_terminals`` mapping.

    Accepted value types per key:

    - ``list[str]``: plain list of pin strings, consumed in order.
    - ``BuildResult``: pins are read from
      ``source.terminal_pin_map[key]``.
    """
    reuse_iters: dict[str, Any] = {}
    if not reuse_terminals:
        return reuse_iters
    for key, source in reuse_terminals.items():
        str_key = str(key)
        if isinstance(source, list):
            reuse_iters[str_key] = iter(source)
        else:
            # Assume BuildResult-like object with terminal_pin_map
            reuse_iters[str_key] = iter(source.terminal_pin_map.get(str_key, []))
    return reuse_iters


def _build_template_reuse(
    template_reuse: dict[DeviceTemplate, dict[str, list[str] | BuildResult]] | None,
) -> tuple[dict[DeviceTemplate, dict[str, Any]], dict[str, set[str]]]:
    """Build template-scoped reuse iterators and reserved pin sets.

    Returns:
        A tuple ``(template_iters, reserved_pins)`` where:

        - *template_iters* maps each ``DeviceTemplate`` to a dict of
          ``{terminal_key: iterator}`` — used when the current device's
          template matches.
        - *reserved_pins* maps ``{terminal_key: set_of_pin_strings}`` —
          the sequential counter skips these to avoid collisions with
          template-reused pins.
    """
    template_iters: dict[DeviceTemplate, dict[str, Any]] = {}
    reserved_pins: dict[str, set[str]] = {}
    if not template_reuse:
        return template_iters, reserved_pins

    # Share one iterator when multiple templates reference the same
    # source object for the same terminal (e.g. FAN_1P, TURN_SWITCH_FAN,
    # and GAS_SENSOR_FAN all mapping to the same fan_controll BuildResult).
    shared_iters: dict[tuple[str, int], Any] = {}

    for template, terminal_map in template_reuse.items():
        template_iters[template] = {}
        for terminal_key, source in terminal_map.items():
            str_key = str(terminal_key)
            cache_key = (str_key, id(source))

            if cache_key not in shared_iters:
                if isinstance(source, list):
                    pins = source
                else:
                    pins = source.terminal_pin_map.get(str_key, [])
                shared_iters[cache_key] = iter(pins)
                reserved_pins.setdefault(str_key, set()).update(str(p) for p in pins)

            template_iters[template][str_key] = shared_iters[cache_key]

    return template_iters, reserved_pins


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_field_connections(
    devices: list[FieldDevice],
    reuse_terminals: dict[str, list[str] | BuildResult] | None = None,
    template_reuse: (
        dict[DeviceTemplate, dict[str, list[str] | BuildResult]] | None
    ) = None,
) -> list[ConnectionRow]:
    """Expand device declarations into connection row tuples.

    Terminal pins are auto-numbered sequentially per terminal block.
    PLC connections use reference tags (resolved later by
    ``PlcMapper`` or project-specific PLC modules).

    Args:
        devices: List of :class:`FieldDevice` instances.
        reuse_terminals: Optional dict mapping terminal key to a list of
            pin strings or a ``BuildResult``.  When a terminal key
            matches, pins are consumed from the reuse source instead of
            being auto-numbered.
        template_reuse: Optional dict mapping ``DeviceTemplate`` to a
            dict of ``{terminal_key: BuildResult | list[str]}``.  Only
            devices whose template matches will reuse those terminal
            pins; other devices auto-number normally but skip the
            reserved (reused) pin values to avoid collisions.

    Returns:
        List of :data:`ConnectionRow` tuples with auto-numbered terminal
        pins and PLC reference tags in the *component_to* field.

    Raises:
        ValueError: If a pin has no terminal and no terminal override
            was provided for its device.
    """
    sequential_counters: dict[str, int] = {}
    prefix_counters: dict[str, dict[str, int]] = {}
    global_reuse_iters = _build_reuse_iters(reuse_terminals)
    template_iters, reserved_pins = _build_template_reuse(template_reuse)

    connections: list[ConnectionRow] = []

    for device in devices:
        tag = device.tag
        template = device.template
        terminal_override = device.terminal

        # Build effective reuse_iters for this device: start with global,
        # then overlay template-scoped iterators if the template matches.
        effective_reuse = dict(global_reuse_iters)
        if template in template_iters:
            effective_reuse.update(template_iters[template])

        device_prefix_indices: dict[str, int] = {}

        # Pre-compute which prefixes this device uses per terminal so
        # _resolve_terminal_pin can compute group numbers correctly.
        device_prefixes_used: dict[str, set[str]] = {}
        for pin_def in template.pins:
            if pin_def.pin_prefix:
                t = pin_def.terminal or terminal_override
                if t is not None:
                    device_prefixes_used.setdefault(str(t), set()).add(
                        pin_def.pin_prefix
                    )

        for pin_def in template.pins:
            terminal = pin_def.terminal or terminal_override

            if terminal is None:
                raise CircuitValidationError(
                    f"Device '{tag}' pin '{pin_def.device_pin}': "
                    f"no terminal in template and no terminal override "
                    f"provided"
                )

            terminal_pin = _resolve_terminal_pin(
                pin_def,
                str(terminal),
                device_prefix_indices,
                device_prefixes_used,
                prefix_counters,
                sequential_counters,
                effective_reuse,
                reserved_pins if reserved_pins else None,
            )
            plc_tag = str(pin_def.plc) if pin_def.plc else ""

            connections.append(
                (tag, pin_def.device_pin, terminal, terminal_pin, plc_tag, "")
            )

    return connections
