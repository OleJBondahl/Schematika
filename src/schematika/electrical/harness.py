"""Harness — a Layer-2 builder that resolves multi-point routes into Wires.

Collects ``route()`` declarations (concrete pins plus unallocated ``Plc``
channel requests), batch-allocates PLC channels against a rack, and decomposes
each route into 2-point ``Wire``s via the Layer-1 ``route_to_wires`` primitive.
Built alongside the legacy ``ConnectionRow``/``resolve_plc_references`` pipeline;
the legacy path is untouched.
"""

from __future__ import annotations

import warnings
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from schematika.catalog.refs import PinRef
from schematika.catalog.routes import Route, route_to_wires
from schematika.core.exceptions import CircuitValidationError
from schematika.electrical.plc_resolver import PLC_PREFIX
from schematika.electrical.utils.utils import natural_sort_key

if TYPE_CHECKING:
    from schematika.catalog.identifiers import DeviceTag, NetId
    from schematika.catalog.wires import Wire
    from schematika.electrical.builder import BuildResult
    from schematika.electrical.field_devices import DeviceTemplate, FieldDevice
    from schematika.electrical.plc_resolver import PlcModuleType, PlcRack

_MIN_WAYPOINTS = 2
_PLC_PREFIX = PLC_PREFIX


def _synth_net(source: PinRef) -> NetId:
    """Default net name from the signal source pin: ``{device}_{port}``."""
    from schematika.catalog.identifiers import NetId

    return NetId(f"{source.device}_{source.port_id}")


def _split_plc_ref(reference: str) -> tuple[str, str]:
    """Split a ``PLC:<type>[:<suffix>]`` reference into ``(signal_type, suffix)``.

    Mirrors ``plc_resolver._parse_plc_tag``: ``"PLC:DI"`` -> ``("DI", "")``;
    ``"PLC:RTD:+R"`` -> ``("RTD", "+R")``.
    """
    parts = reference[len(_PLC_PREFIX) :].split(":")
    return parts[0], parts[1] if len(parts) > 1 else ""


def _plc_device(designation: str) -> DeviceTag:
    """Device tag for a resolved PLC channel endpoint, e.g. ``"PLC:DI1"``.

    ``DeviceTag`` validates non-empty only, so the ``":"`` separator is
    accepted; the ``"PLC:"`` form keeps these endpoints visually grouped.
    """
    from schematika.catalog.identifiers import DeviceTag

    return DeviceTag(f"PLC:{designation}")


@dataclass(frozen=True, slots=True, kw_only=True)
class Plc:
    """An unallocated PLC channel request, resolved against the rack at build().

    Attributes:
        signal_type: Module signal category, e.g. ``"DI"``, ``"AI"``, ``"RTD"``.
        suffix: Per-channel pin suffix; ``""`` for single-pin (DI/DO),
            ``"+R"``/``"RL"``/``"-R"`` for a multi-pin channel (RTD).

    Examples:
        >>> from schematika.electrical.harness import Plc
        >>> Plc(signal_type="RTD", suffix="+R").signal_type
        'RTD'
    """

    signal_type: str
    suffix: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class PlcAssignment:
    """A resolved PLC channel — the row the PLC report needs.

    Attributes:
        module: Rack module designation, e.g. ``"DI1"``.
        mpn: The module's manufacturer part number.
        channel: 1-based channel index on the module.
        signal_type: The module's signal category.
        pin_label: Formatted channel pin label, e.g. ``"3"`` or ``"+R3"``.
        source: The device/terminal pin this channel serves.
        net: The net carried by the wire to this channel.

    Examples:
        >>> from schematika.catalog.identifiers import DeviceTag, NetId
        >>> from schematika.catalog.refs import PinRef
        >>> from schematika.electrical.harness import PlcAssignment
        >>> PlcAssignment(module="DI1", mpn="DI16", channel=1, signal_type="DI",
        ...     pin_label="1", source=PinRef(device=DeviceTag("TT-1"), port_id="1"),
        ...     net=NetId("TT-1_1")).module
        'DI1'
    """

    module: str
    mpn: str
    channel: int
    signal_type: str
    pin_label: str
    source: PinRef
    net: NetId


@dataclass(frozen=True, slots=True, kw_only=True)
class HarnessBuildResult:
    """The frozen output of ``Harness.build()``.

    Attributes:
        wires: Every 2-point wire the harness's routes decomposed into.
        plc_assignments: One record per resolved PLC channel (for the PLC report).

    Examples:
        >>> from schematika.electrical.harness import HarnessBuildResult
        >>> HarnessBuildResult(wires=(), plc_assignments=()).wires
        ()
    """

    wires: tuple[Wire, ...]
    plc_assignments: tuple[PlcAssignment, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class _PlcRequest:
    """One PLC channel to allocate (internal to build())."""

    signal_type: str
    suffix: str
    terminal_sort: tuple[str, str]  # (terminal device tag, terminal pin) for sort order
    source_device: str  # field-device tag, for multi-pin channel grouping
    key: object  # opaque caller key mapping back to the route/waypoint


@dataclass(frozen=True, slots=True, kw_only=True)
class _PlcResolved:
    """One allocated PLC channel (internal)."""

    key: object
    designation: str
    mpn: str
    channel: int
    signal_type: str
    pin_label: str


def _find_modules_for_type(
    signal_type: str, rack: PlcRack
) -> list[tuple[str, PlcModuleType]]:
    """Designation-prefix match first (``"DI"`` -> ``DI1``); else ``signal_type``."""
    by_prefix = [
        (des, mod) for des, mod in rack if des.rstrip("0123456789") == signal_type
    ]
    if by_prefix:
        return by_prefix
    return [(des, mod) for des, mod in rack if mod.signal_type == signal_type]


def _allocate_single_pin(
    reqs: list[_PlcRequest], modules: list[tuple[str, PlcModuleType]]
) -> list[_PlcResolved]:
    """One channel per request, channels assigned in terminal-strip order."""
    ordered = sorted(
        enumerate(reqs),
        key=lambda ir: (
            natural_sort_key(ir[1].terminal_sort[0]),
            natural_sort_key(ir[1].terminal_sort[1]),
        ),
    )
    free = [(des, mod, ch) for des, mod in modules for ch in range(1, mod.channels + 1)]
    by_input_idx: dict[int, _PlcResolved] = {}
    for (input_idx, req), (des, mod, ch) in zip(ordered, free, strict=False):
        label = mod.label_format.format(suffix=mod.pins_per_channel[0], channel=ch)
        by_input_idx[input_idx] = _PlcResolved(
            key=req.key,
            designation=des,
            mpn=mod.mpn,
            channel=ch,
            signal_type=mod.signal_type,
            pin_label=label,
        )
    if len(ordered) > len(free):
        overflow = len(ordered) - len(free)
        plc_type = modules[0][0].rstrip("0123456789")
        warnings.warn(
            f"WARNING: {overflow} {plc_type} connection(s) could not be assigned "
            f"— not enough free PLC channels.",
            stacklevel=2,
        )
    return [by_input_idx[i] for i in sorted(by_input_idx)]


def _allocate_multi_pin(
    reqs: list[_PlcRequest], modules: list[tuple[str, PlcModuleType]]
) -> list[_PlcResolved]:
    """One channel per source device; all that device's pins share it."""
    required = {r.suffix for r in reqs if r.suffix}
    compatible = [
        (des, mod)
        for des, mod in modules
        if required.issubset(set(mod.pins_per_channel))
    ]
    by_device: dict[str, list[_PlcRequest]] = defaultdict(list)
    for r in reqs:
        by_device[r.source_device].append(r)
    ordered_devices = sorted(
        by_device,
        key=lambda dev: min(
            (natural_sort_key(r.terminal_sort[0]), natural_sort_key(r.terminal_sort[1]))
            for r in by_device[dev]
        ),
    )
    free = [
        (des, mod, ch) for des, mod in compatible for ch in range(1, mod.channels + 1)
    ]
    out: list[_PlcResolved] = []
    for idx, dev in enumerate(ordered_devices):
        if idx >= len(free):
            break
        des, mod, ch = free[idx]
        for r in by_device[dev]:
            label = mod.label_format.format(suffix=r.suffix, channel=ch)
            out.append(
                _PlcResolved(
                    key=r.key,
                    designation=des,
                    mpn=mod.mpn,
                    channel=ch,
                    signal_type=mod.signal_type,
                    pin_label=label,
                )
            )
    overflow = len(ordered_devices) - min(len(ordered_devices), len(free))
    if overflow > 0:
        plc_type = modules[0][0].rstrip("0123456789") if modules else "?"
        warnings.warn(
            f"WARNING: {overflow} {plc_type} connection(s) could not be assigned "
            f"— not enough free PLC channels.",
            stacklevel=2,
        )
    return out


@dataclass(frozen=True, slots=True, kw_only=True)
class _RouteDecl:
    """A collected route declaration, resolved at build()."""

    waypoints: tuple[PinRef | Plc, ...]
    net: NetId | None


class Harness:
    """Mutable builder: collect multi-point routes, resolve PLC + emit wires.

    Mutable-builder exception (invariant 5): like ``Catalog`` and
    ``CableBuilder``, it accumulates ``route()`` declarations and freezes on
    ``build()``. It owns the PLC ``rack`` passed at construction.

    Routes may carry concrete terminal pins, or be generated from field devices
    via ``add_field_devices`` (which auto-assigns terminal pins). A ``Plc(...)``
    waypoint is an unallocated channel request resolved against the rack at
    ``build()``.

    Examples:
        >>> from schematika.catalog.identifiers import DeviceTag
        >>> from schematika.catalog.refs import PinRef
        >>> from schematika.electrical.harness import Harness
        >>> h = Harness(rack=[])
        >>> h.route(PinRef(device=DeviceTag("-M1"), port_id="U"),
        ...         PinRef(device=DeviceTag("X1"), port_id="1"))
        >>> len(h.build().wires)
        1
    """

    def __init__(self, *, rack: PlcRack) -> None:
        """Start a harness bound to a PLC *rack* (may be empty)."""
        self._rack = rack
        self._routes: list[_RouteDecl] = []

    def route(self, *waypoints: PinRef | Plc, net: NetId | None = None) -> None:
        """Declare a signal through ``>= 2`` waypoints (pins and/or Plc requests).

        Raises:
            CircuitValidationError: if fewer than two waypoints are given.
        """
        if len(waypoints) < _MIN_WAYPOINTS:
            msg = f"route needs >= {_MIN_WAYPOINTS} waypoints, got {len(waypoints)}"
            raise CircuitValidationError(msg)
        self._routes.append(_RouteDecl(waypoints=waypoints, net=net))

    def add_field_devices(
        self,
        devices: list[FieldDevice],
        *,
        reuse_terminals: dict[str, list[str] | BuildResult] | None = None,
        template_reuse: (
            dict[DeviceTemplate, dict[str, list[str] | BuildResult]] | None
        ) = None,
    ) -> None:
        """Expand field devices into routes, auto-assigning terminal pins.

        Delegates terminal-pin numbering to ``generate_field_connections`` (the
        canonical fixed/prefixed/sequential allocator) and turns each resulting
        connection into a route: the device pin to its terminal pin. A pin that
        references a PLC channel grows a trailing ``Plc`` waypoint (parsed from
        the ``"PLC:..."`` reference) resolved against the rack at ``build()``.
        """
        from schematika.catalog.identifiers import DeviceTag
        from schematika.electrical.field_devices import generate_field_connections

        rows = generate_field_connections(
            devices,
            reuse_terminals=reuse_terminals,
            template_reuse=template_reuse,
        )
        for (
            component_from,
            pin_from,
            terminal,
            terminal_pin,
            component_to,
            _pin_to,
        ) in rows:
            source = PinRef(device=DeviceTag(component_from), port_id=pin_from)
            term = PinRef(device=DeviceTag(str(terminal)), port_id=terminal_pin)
            if component_to.startswith(_PLC_PREFIX):
                signal_type, suffix = _split_plc_ref(component_to)
                self.route(source, term, Plc(signal_type=signal_type, suffix=suffix))
            else:
                self.route(source, term)

    def build(self) -> HarnessBuildResult:
        """Resolve all declared routes into wires + PLC assignments."""
        requests = self._collect_plc_requests()
        resolved = {r.key: r for r in _allocate_plc(requests, self._rack)}

        wires: list[Wire] = []
        assignments: list[PlcAssignment] = []
        for route_idx, decl in enumerate(self._routes):
            source = decl.waypoints[0]
            if not isinstance(source, PinRef):
                msg = "route source (first waypoint) must be a concrete pin"
                raise CircuitValidationError(msg)
            net = decl.net if decl.net is not None else _synth_net(source)

            waypoints: list[PinRef] = []
            for wp_idx, wp in enumerate(decl.waypoints):
                if isinstance(wp, PinRef):
                    waypoints.append(wp)
                    continue
                res = resolved.get((route_idx, wp_idx))
                if res is None:
                    continue  # overflow-dropped: skip this channel (parity w/ legacy)
                endpoint = PinRef(
                    device=_plc_device(res.designation), port_id=res.pin_label
                )
                waypoints.append(endpoint)
                assignments.append(
                    PlcAssignment(
                        module=res.designation,
                        mpn=res.mpn,
                        channel=res.channel,
                        signal_type=res.signal_type,
                        pin_label=res.pin_label,
                        source=source,
                        net=net,
                    )
                )

            if len(waypoints) >= _MIN_WAYPOINTS:
                wires.extend(route_to_wires(Route(net=net, waypoints=tuple(waypoints))))

        return HarnessBuildResult(
            wires=tuple(wires), plc_assignments=tuple(assignments)
        )

    def _collect_plc_requests(self) -> list[_PlcRequest]:
        """Build one _PlcRequest per Plc waypoint, keyed by (route_idx, wp_idx)."""
        requests: list[_PlcRequest] = []
        for route_idx, decl in enumerate(self._routes):
            source = decl.waypoints[0]
            src_dev = str(source.device) if isinstance(source, PinRef) else ""
            for wp_idx, wp in enumerate(decl.waypoints):
                if not isinstance(wp, Plc):
                    continue
                prev = decl.waypoints[wp_idx - 1] if wp_idx > 0 else None
                if isinstance(prev, PinRef):
                    term = (str(prev.device), prev.port_id)
                else:
                    term = ("", "")
                requests.append(
                    _PlcRequest(
                        signal_type=wp.signal_type,
                        suffix=wp.suffix,
                        terminal_sort=term,
                        source_device=src_dev,
                        key=(route_idx, wp_idx),
                    )
                )
        return requests


def _allocate_plc(reqs: list[_PlcRequest], rack: PlcRack) -> list[_PlcResolved]:
    """Bucket requests by signal type and allocate channels (legacy semantics)."""
    by_type: dict[str, list[_PlcRequest]] = defaultdict(list)
    for r in reqs:
        by_type[r.signal_type].append(r)

    out: list[_PlcResolved] = []
    for signal_type, entries in by_type.items():
        modules = _find_modules_for_type(signal_type, rack)
        if not modules:
            continue
        has_suffix = any(r.suffix for r in entries)
        has_plain = any(not r.suffix for r in entries)
        if has_suffix and has_plain:
            warnings.warn(
                f"PLC type '{signal_type}' has a mix of suffixed (multi-pin) and "
                f"unsuffixed (single-pin) requests. These cannot be routed and are "
                f"dropped.",
                stacklevel=2,
            )
            continue
        if has_suffix:
            out.extend(_allocate_multi_pin(entries, modules))
        else:
            out.extend(_allocate_single_pin(entries, modules))
    return out
