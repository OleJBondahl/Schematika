"""Device-to-device cable connection API.

This module provides ``InterDeviceConnection``, a declarative description of a
cable running directly between two field devices (i.e. FieldDevice -> FieldDevice,
without a cabinet terminal in between).  It is a parallel code path to the
existing FieldDevice -> Terminal -> PLC pipeline: ``Project.inter_device_cables()``
accumulates these connections, and ``Project.cable_pages()`` appends their
drawings after the existing device-to-terminal cable drawings.

Template handling decision
--------------------------
``FieldDevice`` requires a ``DeviceTemplate`` argument.  For devices that
participate **only** in inter-device connections and have no terminal wiring,
the template is irrelevant (``generate_field_connections()`` is never called
on them).  Rather than making ``template`` optional on ``FieldDevice`` (which
would require a sentinel default and a ``__post_init__`` guard - invasive), we
provide a module-level ``EMPTY_TEMPLATE`` sentinel:

    EMPTY_TEMPLATE = DeviceTemplate(mpn="_empty_", pins=())

Users declare such devices as ``FieldDevice(tag="BACKPLANE-J34",
template=EMPTY_TEMPLATE)`` and register them via ``project.field_devices([...])``.
``EMPTY_TEMPLATE`` is also re-exported from ``schematika.electrical`` and
``schematika`` for import convenience.

Fan-out support
---------------
``InterDeviceConnection`` supports one-to-many wiring via ``to_endpoints`` (a
tuple of ``CableTargetEndpoint``) and ``wires`` (explicit per-wire routing).

When ``wires`` is ``None`` the connection behaves as a simple 1-to-1 cable
against ``to_endpoints[0]``: pin synthesis follows the same rules as before
(connector_data.pins -> wire_colors count -> error).

When ``wires`` is provided each ``WireSpec`` names the source pin, the target
endpoint (by index into ``to_endpoints``), and the target pin.  This is the
fan-out path.  A single CableDrawing is produced; all target connectors appear
as additional connectors on the right side of the harness, which WireViz
renders correctly in one SVG.

ConnectorData handling (wires=None path)
----------------------------------------
- Both from_connector_data and to_endpoints[0].connector_data set -> used
  as-is; their ``pins`` tuples must have equal length.
- Only ``from_connector_data`` set -> mirrored to target side.
- Only ``to_endpoints[0].connector_data`` set -> mirrored to source side.
- Neither set -> synthesised from cable wire_colors count.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from schematika.electrical.field_devices import DeviceTemplate

if TYPE_CHECKING:
    from schematika.catalog.cables import CableData, ConnectorData

# ---------------------------------------------------------------------------
# Sentinel template for inter-device-only devices
# ---------------------------------------------------------------------------

EMPTY_TEMPLATE = DeviceTemplate(mpn="_empty_", pins=())
"""
Sentinel ``DeviceTemplate`` for field devices that participate only in
inter-device connections and have no terminal wiring.

Usage::

    from schematika.electrical import FieldDevice, EMPTY_TEMPLATE
    backplane = FieldDevice(tag="BACKPLANE-J34", template=EMPTY_TEMPLATE)
"""


# ---------------------------------------------------------------------------
# Fan-out data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CableTargetEndpoint:
    """One target end of an inter-device cable.

    Attributes:
        device: Tag of the target device (e.g. "BMU1").
        connector: Connector designator on the target device (e.g. "J1").
        connector_data: Optional connector metadata for this endpoint.
    """

    device: str
    connector: str
    connector_data: ConnectorData | None = None


@dataclass(frozen=True)
class WireSpec:
    """Explicit routing for one wire in a fan-out cable.

    Attributes:
        from_pin: Pin label on the source connector.
        to_endpoint: Index into ``InterDeviceConnection.to_endpoints``.
        to_pin: Pin label on the target endpoint connector.
        color: Optional wire color code (e.g. "BN").
        net_name: Optional net label rendered alongside the wire in the cable
            diagram (e.g. ``"V24"``, ``"CAN_H"``).  ``None`` means no label.
    """

    from_pin: str
    to_endpoint: int
    to_pin: str
    color: str | None = None
    net_name: str | None = None


# ---------------------------------------------------------------------------
# InterDeviceConnection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InterDeviceConnection:
    """A cable that runs directly between a source device and one or more targets.

    Attributes:
        from_device: Tag of the source device (e.g. "BACKPLANE-J34").
        from_connector: Connector designator on the source device (e.g. "J34").
        to_endpoints: One or more target endpoints.  For a simple 1-to-1 cable
            provide a single-element tuple; for fan-out provide multiple.
        cable: Physical cable properties (gauge, colors, length, etc.).
        from_connector_data: Optional connector metadata for the source side.
        wires: Explicit per-wire routing.  When ``None`` the connection falls
            back to sequential 1-to-1 wiring against ``to_endpoints[0]``,
            synthesising pins from ``wire_colors`` count or connector_data.
    """

    from_device: str
    from_connector: str
    to_endpoints: tuple[CableTargetEndpoint, ...]
    cable: CableData
    from_connector_data: ConnectorData | None = None
    wires: tuple[WireSpec, ...] | None = None
