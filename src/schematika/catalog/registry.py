"""Device catalog registry for looking up equipment by tag or category.

Provides ``DeviceCatalog``, which stores and retrieves ``CatalogDevice``
entries imported from ``catalog/device.py``.
"""

from __future__ import annotations

from schematika.catalog.device import CatalogDevice
from schematika.catalog.errors import CatalogError


class DeviceCatalog:
    """Registry of devices shared between P&ID and electrical drawings.

    Mutable builder (same pattern as Project, Circuit, PIDBuilder).
    """

    def __init__(self) -> None:
        """Build an empty device catalog."""
        self._devices: dict[str, CatalogDevice] = {}

    def register(self, device: CatalogDevice) -> None:
        """Register a device. Raises ValueError if tag already exists."""
        if device.tag in self._devices:
            raise CatalogError(f"Device '{device.tag}' already registered")
        self._devices[device.tag] = device

    def get(self, tag: str) -> CatalogDevice:
        """Look up device by tag. Raises KeyError if not found."""
        if tag not in self._devices:
            raise KeyError(f"Device '{tag}' not found in catalog")
        return self._devices[tag]

    def __contains__(self, tag: str) -> bool:
        return tag in self._devices

    def __len__(self) -> int:
        return len(self._devices)

    def __iter__(self):
        return iter(self._devices.values())

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
