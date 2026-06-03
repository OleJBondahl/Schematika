"""Unified catalog builder and the legacy device-catalog face.

``Catalog`` is the single mutable builder holding a device registry and a
cable-instance registry. ``DeviceCatalog`` is a deprecated subclass kept
for one release cycle (Phase 0 merge).
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from schematika.catalog.errors import CatalogError, CatalogValidationError
from schematika.catalog.refs import PartRef
from schematika.catalog.result import ResolvedCatalog

if TYPE_CHECKING:
    from collections.abc import Iterator

    from schematika.catalog.cables import CableInstance, CableProductSpec
    from schematika.catalog.connectors import ConnectorSpec
    from schematika.catalog.device import CatalogDevice
    from schematika.catalog.identifiers import PartId
    from schematika.catalog.parts import PartSpec


class Catalog:
    """Single source of truth for project devices and cable instances.

    Mutable builder (same pattern as ``Project``, ``CircuitBuilder``,
    ``PIDBuilder``). Devices and cable instances are each keyed by ``tag``
    in separate namespaces. Parts, connectors, and cable products are
    registered via ``add_part`` / ``add_connector`` / ``add_cable_product``
    and frozen into an immutable ``ResolvedCatalog`` snapshot via ``build()``.

    Examples:
        >>> from schematika.catalog import Catalog, CatalogDevice
        >>> from schematika.catalog import InstrumentSpec, ProcessSpec
        >>> cat = Catalog()
        >>> proc = ProcessSpec(instrument=InstrumentSpec(letters="TT", number="101"))
        >>> cat.add_device(CatalogDevice(tag="TT-101",
        ...                              description="Temperature transmitter",
        ...                              process=proc))
        >>> cat.get_device("TT-101").description
        'Temperature transmitter'
    """

    def __init__(self) -> None:
        """Build an empty catalog."""
        self._devices: dict[str, CatalogDevice] = {}
        self._cables: dict[str, CableInstance] = {}
        self._parts: dict[PartId, PartSpec] = {}
        self._connectors: dict[PartId, ConnectorSpec] = {}
        self._cable_products: dict[PartId, CableProductSpec] = {}

    # --- devices ---------------------------------------------------------

    def add_device(self, device: CatalogDevice) -> None:
        """Register a device. Raises CatalogError if tag already exists."""
        if device.tag in self._devices:
            msg = f"Device '{device.tag}' already registered"
            raise CatalogError(msg)
        self._devices[device.tag] = device

    def get_device(self, tag: str) -> CatalogDevice:
        """Look up a device by tag. Raises KeyError if not found."""
        if tag not in self._devices:
            msg = f"Device '{tag}' not found in catalog"
            raise KeyError(msg)
        return self._devices[tag]

    @property
    def devices(self) -> list[CatalogDevice]:
        """All registered devices."""
        return list(self._devices.values())

    def instruments(self) -> list[CatalogDevice]:
        """All devices with a ProcessSpec (appear on P&ID)."""
        return [d for d in self._devices.values() if d.process is not None]

    def electrical_devices(self) -> list[CatalogDevice]:
        """All devices with an ElectricalSpec (appear on electrical drawings)."""
        return [d for d in self._devices.values() if d.electrical is not None]

    def cross_referenced(self) -> list[CatalogDevice]:
        """Devices that appear on BOTH P&ID and electrical drawings."""
        return [
            d
            for d in self._devices.values()
            if d.process is not None and d.electrical is not None
        ]

    def generate_cross_reference_table(self) -> list[dict[str, str]]:
        """Generate a cross-reference table for documentation.

        Returns list of dicts with keys: tag, description, pid_letters,
        pid_location, electrical_terminal, signal_type
        """
        rows = []
        for device in self.cross_referenced():
            row: dict[str, str] = {
                "tag": device.tag,
                "description": device.description,
            }
            if device.process:
                row["pid_letters"] = device.process.instrument.letters
                row["pid_location"] = device.process.instrument.location
                row["service"] = device.process.service
            if device.electrical:
                row["electrical_terminal"] = device.electrical.terminal
                row["signal_type"] = device.electrical.signal_type
            rows.append(row)
        return rows

    # --- cable instances -------------------------------------------------

    def add_cable_instance(self, cable: CableInstance) -> None:
        """Register a cable instance. Raises CatalogError on duplicate tag."""
        if cable.tag in self._cables:
            msg = f"Cable '{cable.tag}' already registered"
            raise CatalogError(msg)
        self._cables[cable.tag] = cable

    def get_cable_instance(self, tag: str) -> CableInstance:
        """Look up a cable instance by tag. Raises KeyError if not found."""
        if tag not in self._cables:
            msg = f"Cable '{tag}' not found in registry"
            raise KeyError(msg)
        return self._cables[tag]

    @property
    def cables(self) -> list[CableInstance]:
        """All registered cable instances."""
        return list(self._cables.values())

    def by_device(self, device_tag: str) -> list[CableInstance]:
        """Return all cables connected to a device (as source or destination)."""
        return [
            c
            for c in self._cables.values()
            if device_tag in (c.from_device, c.to_device)
        ]

    # --- parts / connectors / cable products ---------------------------------

    def add_part(self, spec: PartSpec, /) -> PartRef:
        """Register a part spec. Returns its ``PartRef``.

        Args:
            spec: The part spec; ``spec.part`` is the key.

        Returns:
            A ``PartRef`` for the registered part.

        Raises:
            CatalogValidationError: if ``spec.part`` is already registered.
        """
        if spec.part in self._parts:
            msg = f"Part '{spec.part}' already registered"
            raise CatalogValidationError(msg)
        self._parts[spec.part] = spec
        return PartRef(part=spec.part)

    def add_connector(self, spec: ConnectorSpec, /) -> PartRef:
        """Register a connector spec. Returns its ``PartRef``.

        Args:
            spec: The connector spec; ``spec.part`` is the key.

        Returns:
            A ``PartRef`` for the registered connector.

        Raises:
            CatalogValidationError: if ``spec.part`` is already registered.
        """
        if spec.part in self._connectors:
            msg = f"Connector '{spec.part}' already registered"
            raise CatalogValidationError(msg)
        self._connectors[spec.part] = spec
        return PartRef(part=spec.part)

    def add_cable_product(self, spec: CableProductSpec, /) -> PartRef:
        """Register a cable-product spec. Returns its ``PartRef``.

        Args:
            spec: The cable-product spec; ``spec.part`` is the key.

        Returns:
            A ``PartRef`` for the registered cable product.

        Raises:
            CatalogValidationError: if ``spec.part`` is already registered.
        """
        if spec.part in self._cable_products:
            msg = f"Cable product '{spec.part}' already registered"
            raise CatalogValidationError(msg)
        self._cable_products[spec.part] = spec
        return PartRef(part=spec.part)

    def build(self) -> ResolvedCatalog:
        """Freeze the catalog into an immutable ``ResolvedCatalog`` snapshot.

        Returns:
            A ``ResolvedCatalog`` over read-only copies of the current state.

        Examples:
            >>> from schematika.catalog.identifiers import PartId
            >>> from schematika.catalog.parts import PartSpec
            >>> from schematika.catalog.registry import Catalog
            >>> cat = Catalog()
            >>> _ = cat.add_part(PartSpec(part=PartId("p1"), mpn="1",
            ...                  category="device", description="d"))
            >>> cat.build().lookup_part(PartId("p1")).mpn
            '1'
        """
        return ResolvedCatalog(
            parts=MappingProxyType(dict(self._parts)),
            connectors=MappingProxyType(dict(self._connectors)),
            cable_products=MappingProxyType(dict(self._cable_products)),
            devices=MappingProxyType(dict(self._devices)),
            cable_instances=MappingProxyType(dict(self._cables)),
        )


class DeviceCatalog(Catalog):
    """Deprecated device-only face of ``Catalog``.

    Deprecated: use ``Catalog`` with ``add_device`` / ``get_device``.
    Kept for one release cycle (Phase 0 merge). Re-exposes the legacy
    ``register`` / ``get`` names and device-scoped dunders.
    Cable methods (``add_cable_instance`` etc.) are inherited from
    ``Catalog`` and remain callable, but are out of scope for this
    deprecated face — migrate to ``Catalog`` directly.

    Examples:
        >>> from schematika.catalog import (
        ...     CatalogDevice, DeviceCatalog, InstrumentSpec, ProcessSpec)
        >>> cat = DeviceCatalog()
        >>> inst = InstrumentSpec(letters="TT", number="101")
        >>> proc = ProcessSpec(instrument=inst)
        >>> device = CatalogDevice(tag="TT-101",
        ...                        description="Temperature transmitter",
        ...                        process=proc)
        >>> cat.register(device)
        >>> "TT-101" in cat
        True
        >>> cat.get("TT-101").description
        'Temperature transmitter'
        >>> len(cat)
        1
    """

    def register(self, device: CatalogDevice) -> None:
        """Deprecated alias for ``Catalog.add_device``."""
        self.add_device(device)

    def get(self, tag: str) -> CatalogDevice:
        """Deprecated alias for ``Catalog.get_device``."""
        return self.get_device(tag)

    def __contains__(self, tag: str) -> bool:
        """Return True if *tag* is a registered device."""
        return tag in self._devices

    def __len__(self) -> int:
        """Return the number of registered devices."""
        return len(self._devices)

    def __iter__(self) -> Iterator[CatalogDevice]:
        """Iterate over all ``CatalogDevice`` entries."""
        return iter(self._devices.values())
