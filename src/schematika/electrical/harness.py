"""Harness — a Layer-2 builder that resolves multi-point routes into Wires.

Collects ``route()`` declarations (concrete pins plus unallocated ``Plc``
channel requests), batch-allocates PLC channels against a rack, and decomposes
each route into 2-point ``Wire``s via the Layer-1 ``route_to_wires`` primitive.
Built alongside the legacy ``ConnectionRow``/``resolve_plc_references`` pipeline;
the legacy path is untouched.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from schematika.catalog.identifiers import NetId
    from schematika.catalog.refs import PinRef
    from schematika.catalog.wires import Wire


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
