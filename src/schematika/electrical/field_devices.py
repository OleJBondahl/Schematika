"""Field device templates and connection generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from schematika.catalog.cables import CableData as CableData  # noqa: TC001
from schematika.catalog.cables import ConnectorData as ConnectorData  # noqa: TC001
from schematika.core.exceptions import CircuitValidationError

if TYPE_CHECKING:
    from schematika.electrical.builder import BuildResult
    from schematika.electrical.terminal import Terminal

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

DeviceEntry = tuple[str, "DeviceTemplate"] | tuple[str, "DeviceTemplate", "Terminal"]
"""(tag, template) or (tag, template, override). Override fills PinDef gaps."""


# ---------------------------------------------------------------------------
# Core data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DeviceCable:
    """One cable+connector pair on a multi-cable device.

    Groups a subset of device pins into a single cable with its own
    physical properties and optional connector.

    Examples:
        >>> from schematika.electrical import CableData, DeviceCable
        >>> cable = CableData(wire_gauge=0.75)
        >>> dc = DeviceCable(pins=("1", "2"), cable=cable)
        >>> dc.pins
        ('1', '2')
    """

    pins: tuple[str, ...]
    """Which device pins use this cable."""
    cable: CableData
    """Wire gauge, colors, category, etc."""
    connector: ConnectorData | None = None
    """Physical connector (cable gland, ferrule, etc.)."""


@dataclass(frozen=True, kw_only=True)
class AnalogScaling:
    """Raw-to-engineering scaling for one analog instrument.

    Declared on the :class:`FieldDevice` instance (a physical property of the
    specific instrument), consumed by the WAGO XML export to emit the
    ``<Operator>``/``<ScalingPoint>`` block and ``Unit`` attribute.

    Examples:
        >>> from schematika.electrical import AnalogScaling
        >>> s = AnalogScaling(
        ...     unit="bar", raw_min=0, raw_max=31987, eng_min=0, eng_max=3.6)
        >>> s.unit
        'bar'
    """

    unit: str
    """Engineering unit, e.g. ``"bar"`` or ``"°C"``."""
    raw_min: float
    """Raw value at the low scaling point, e.g. ``0``."""
    raw_max: float
    """Raw value at the high scaling point, e.g. ``32767``."""
    eng_min: float
    """Engineering value at the low scaling point."""
    eng_max: float
    """Engineering value at the high scaling point."""


@dataclass(frozen=True)
class FieldDevice:
    """A field device: connection template plus optional cable/connector data.

    Examples:
        >>> from schematika.electrical import (
        ...     FieldDevice, DeviceTemplate, PinDef)
        >>> pin = PinDef(device_pin="1")
        >>> tmpl = DeviceTemplate(mpn="TT-101", pins=(pin,))
        >>> dev = FieldDevice(tag="TT-101", template=tmpl)
        >>> dev.tag
        'TT-101'
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
    scaling: AnalogScaling | None = None
    """Analog raw-to-engineering scaling + unit (WAGO XML export)."""


@dataclass(frozen=True)
class PinDef:
    """Pin definition with three terminal numbering modes.

    The three modes are determined by the combination of ``pin_prefix`` and
    ``terminal_pin`` fields:

    * **Sequential** (both empty): auto-increments per terminal.
    * **Prefixed** (``pin_prefix`` set): group-based, e.g. ``"L1:1"``.
    * **Fixed** (``terminal_pin`` set): literal string used as-is.

    ``function_suffix`` optionally names the pin's PLC signal function (e.g.
    ``"StartFb"``); the WAGO XML export names the channel
    ``{device-tag}_{function_suffix}`` with hyphens replaced by underscores
    (e.g. tag ``PU-01-CX`` → ``PU_01_CX_StartFb``).

    Examples:
        >>> from schematika.electrical import PinDef
        >>> pin = PinDef(device_pin="OUT", terminal_pin="PE")
        >>> pin.terminal_pin
        'PE'
    """

    device_pin: str
    terminal: Terminal | None = None
    plc: Terminal | None = None
    terminal_pin: str = ""
    pin_prefix: str = ""
    function_suffix: str = ""


@dataclass(frozen=True)
class SequentialPin(PinDef):
    """Auto-numbered slot; `pin_prefix` and `terminal_pin` must both be empty."""

    def __post_init__(self) -> None:
        """Reject pin_prefix or terminal_pin."""
        if self.pin_prefix:
            msg = (
                f"SequentialPin '{self.device_pin}': pin_prefix must be empty "
                f"(use PrefixedPin for prefix-numbered pins)"
            )
            raise CircuitValidationError(msg)
        if self.terminal_pin:
            msg = (
                f"SequentialPin '{self.device_pin}': terminal_pin must be empty "
                f"(use FixedPin for literal pin names)"
            )
            raise CircuitValidationError(msg)


@dataclass(frozen=True)
class PrefixedPin(PinDef):
    """Formatted `"{pin_prefix}:{group_index}"`; requires `pin_prefix`."""

    def __post_init__(self) -> None:
        """Require pin_prefix; reject terminal_pin."""
        if not self.pin_prefix:
            msg = f"PrefixedPin '{self.device_pin}': pin_prefix is required"
            raise CircuitValidationError(msg)
        if self.terminal_pin:
            msg = (
                f"PrefixedPin '{self.device_pin}': terminal_pin must be empty "
                f"(use FixedPin for literal pin names)"
            )
            raise CircuitValidationError(msg)


@dataclass(frozen=True)
class FixedPin(PinDef):
    """Literal pin name; requires `terminal_pin`, rejects `pin_prefix`."""

    def __post_init__(self) -> None:
        """Require terminal_pin; reject pin_prefix."""
        if not self.terminal_pin:
            msg = f"FixedPin '{self.device_pin}': terminal_pin is required"
            raise CircuitValidationError(msg)
        if self.pin_prefix:
            msg = (
                f"FixedPin '{self.device_pin}': pin_prefix must be empty "
                f"(use PrefixedPin for prefix-numbered pins)"
            )
            raise CircuitValidationError(msg)


@dataclass(frozen=True)
class DeviceTemplate:
    """Reusable connection pattern for a field device type.

    Examples:
        >>> from schematika.electrical import DeviceTemplate, PinDef
        >>> pin = PinDef(device_pin="1")
        >>> tmpl = DeviceTemplate(mpn="GE-100", pins=(pin,))
        >>> tmpl.mpn
        'GE-100'
        >>> len(tmpl.pins)
        1
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
    """Implements the three numbering modes documented on `PinDef`."""
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
    """Accepts `list[str]` (consumed in order) or a `BuildResult.terminal_pin_map`."""
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
    """Iterators are shared by `(terminal, id(source))` for duplicate sources."""
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
) -> list[tuple[str, str, Any, str, str, str]]:
    """Generate a flat connection table from a list of field devices.

    Each :class:`FieldDevice` is expanded into one connection tuple per
    pin.  Pin IDs are allocated from ``reuse_terminals``, ``template_reuse``,
    or auto-incremented sequentially.  ``template_reuse`` reserves specific
    pin ranges so non-matching devices skip those slots.

    Args:
        devices: Ordered list of :class:`FieldDevice` objects to process.
        reuse_terminals: Maps terminal ID to a pre-allocated pin list or a
            :class:`~schematika.electrical.BuildResult` whose
            ``terminal_pin_map`` is consumed in order.
        template_reuse: Maps :class:`DeviceTemplate` to a terminal->pins dict
            for template-scoped pin reservation.

    Returns:
        List of ``(component_from, pin_from, terminal, terminal_pin,
        component_to, pin_to)`` tuples, one per device pin.

    Examples:
        >>> from schematika.electrical import (
        ...     FieldDevice, DeviceTemplate, PinDef, Terminal,
        ...     generate_field_connections)
        >>> t = Terminal("X001")
        >>> pin = PinDef(device_pin="1", terminal=t)
        >>> tmpl = DeviceTemplate(mpn="SENSOR", pins=(pin,))
        >>> dev = FieldDevice(tag="TT-101", template=tmpl)
        >>> rows = generate_field_connections([dev])
        >>> rows[0][0], rows[0][1]
        ('TT-101', '1')
    """
    sequential_counters: dict[str, int] = {}
    prefix_counters: dict[str, dict[str, int]] = {}
    global_reuse_iters = _build_reuse_iters(reuse_terminals)
    template_iters, reserved_pins = _build_template_reuse(template_reuse)

    connections: list[tuple[str, str, Any, str, str, str]] = []

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
                msg = (
                    f"Device '{tag}' pin '{pin_def.device_pin}': "
                    f"no terminal in template and no terminal override "
                    f"provided"
                )
                raise CircuitValidationError(msg)

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
