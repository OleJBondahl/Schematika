"""Data classes representing catalog device entries.

Provides ``CatalogDevice`` and its component specs (``InstrumentSpec``,
``ProcessSpec``, ``ElectricalSpec``) used by ``DeviceCatalog`` in
``catalog/registry.py``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InstrumentSpec:
    """ISA 5.1 instrument identification."""

    letters: str  # "TT", "PT", "FIC", etc.
    number: str  # "101", "201A"
    location: str = "field"  # "field", "panel", "dcs"

    @property
    def tag(self) -> str:
        """Full ISA tag, e.g. 'TT-101'."""
        return f"{self.letters}-{self.number}"

    @property
    def first_letter(self) -> str:
        """Measured variable letter, e.g. 'T' for Temperature."""
        return self.letters[0]


@dataclass(frozen=True)
class ProcessSpec:
    """How a device appears on P&ID drawings."""

    instrument: InstrumentSpec
    service: str = ""  # "Cooling water supply temperature"
    range: str = ""  # "0-100°C"
    output: str = ""  # "4-20mA"


@dataclass(frozen=True)
class ElectricalSpec:
    """How a device appears on electrical drawings."""

    terminal: str  # Terminal block ID (e.g., "X100")
    pin_count: int = 2  # Number of pins
    cable: str | None = None  # Cable designation
    signal_type: str = "4-20mA"  # Signal type for documentation


@dataclass(frozen=True)
class CatalogDevice:
    """A device that appears on both P&ID and electrical drawings.

    Single source of truth for device identity. Both PIDBuilder and
    CircuitBuilder/field_devices reference CatalogDevices by tag.
    """

    tag: str  # "TT-101" (unique identifier)
    description: str  # "Cooling water temperature transmitter"
    manufacturer: str = ""
    model: str = ""
    process: ProcessSpec | None = None
    electrical: ElectricalSpec | None = None
