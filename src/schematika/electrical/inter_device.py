"""
Device-to-device cable connection API.

This module provides ``InterDeviceConnection``, a declarative description of a
cable running directly between two field devices (i.e. FieldDevice → FieldDevice,
without a cabinet terminal in between).  It is a parallel code path to the
existing FieldDevice → Terminal → PLC pipeline: ``Project.inter_device_cables()``
accumulates these connections, and ``Project.cable_pages()`` appends their
drawings after the existing device-to-terminal cable drawings.

Template handling decision
--------------------------
``FieldDevice`` requires a ``DeviceTemplate`` argument.  For devices that
participate **only** in inter-device connections and have no terminal wiring,
the template is irrelevant (``generate_field_connections()`` is never called
on them).  Rather than making ``template`` optional on ``FieldDevice`` (which
would require a sentinel default and a ``__post_init__`` guard — invasive), we
provide a module-level ``EMPTY_TEMPLATE`` sentinel:

    EMPTY_TEMPLATE = DeviceTemplate(mpn="_empty_", pins=())

Users declare such devices as ``FieldDevice(tag="BACKPLANE-J34",
template=EMPTY_TEMPLATE)`` and register them via ``project.field_devices([...])``.
``EMPTY_TEMPLATE`` is also re-exported from ``schematika.electrical`` and
``schematika`` for import convenience.

ConnectorData handling
----------------------
``InterDeviceConnection`` carries optional ``from_connector_data`` and
``to_connector_data`` fields.  Resolution at drawing time:

- Both set → used as-is; their ``pins`` tuples must have equal length (validated
  in ``_build_inter_device_drawing``).
- Only ``from_connector_data`` set → same data applied to both sides.
- Only ``to_connector_data`` set → same data applied to both sides.
- Neither set → a 1-pin ``ConnectorData`` is synthesised from the cable wire
  count, giving pins ("1", "2", ..., N).
"""

from __future__ import annotations

from dataclasses import dataclass

from schematika.electrical.field_devices import CableData, ConnectorData, DeviceTemplate

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
# InterDeviceConnection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InterDeviceConnection:
    """A cable that runs directly between two field devices.

    Attributes:
        from_device: Tag of the source device (e.g. "BACKPLANE-J34").
        from_connector: Connector designator on the source device (e.g. "J34").
        to_device: Tag of the destination device (e.g. "PUMP-M01").
        to_connector: Connector designator on the destination device.
        cable: Physical cable properties (gauge, colors, length, etc.).
        from_connector_data: Optional connector metadata for the source side.
            If only one side is set, it is mirrored to the other side.
            If neither is set, a default connector is synthesised from the
            cable wire count.
        to_connector_data: Optional connector metadata for the destination side.
    """

    from_device: str
    from_connector: str
    to_device: str
    to_connector: str
    cable: CableData
    from_connector_data: ConnectorData | None = None
    to_connector_data: ConnectorData | None = None
