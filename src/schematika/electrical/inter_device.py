"""Sentinel device template for cable-only field devices.

Provides ``EMPTY_TEMPLATE``, a module-level ``DeviceTemplate`` sentinel for
field devices that participate only in cable connections and have no terminal
wiring.

``FieldDevice`` requires a ``DeviceTemplate`` argument.  For devices that have
no terminal wiring (``generate_field_connections()`` is never called on them),
the template is irrelevant.  Rather than making ``template`` optional on
``FieldDevice`` (which would require a sentinel default and a ``__post_init__``
guard - invasive), we provide ``EMPTY_TEMPLATE``::

    EMPTY_TEMPLATE = DeviceTemplate(mpn="_empty_", pins=())

Users declare such devices as ``FieldDevice(tag="BACKPLANE-J34",
template=EMPTY_TEMPLATE)`` and register them via ``project.field_devices([...])``.
"""

from schematika.electrical.field_devices import DeviceTemplate

# ---------------------------------------------------------------------------
# Sentinel template for cable-only devices
# ---------------------------------------------------------------------------

EMPTY_TEMPLATE = DeviceTemplate(mpn="_empty_", pins=())
"""
Sentinel ``DeviceTemplate`` for field devices that participate only in
cable connections and have no terminal wiring.

Usage::

    from schematika.electrical import FieldDevice, EMPTY_TEMPLATE
    backplane = FieldDevice(tag="BACKPLANE-J34", template=EMPTY_TEMPLATE)
"""
