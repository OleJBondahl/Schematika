"""Data classes representing catalog device entries.

Provides ``CatalogDevice`` and its component specs (``InstrumentSpec``,
``ProcessSpec``, ``ElectricalSpec``) used by ``Catalog`` in
``catalog/registry.py`` (and the deprecated ``DeviceCatalog`` subclass).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InstrumentSpec:
    """ISA 5.1 instrument identification for a field instrument.

    Attributes:
        letters: ISA function letters, e.g. ``"TT"`` (temperature transmitter),
            ``"FIC"`` (flow indicating controller).
        number: Loop number, e.g. ``"101"`` or ``"201A"``.
        location: Physical or graphical location; one of ``"field"``,
            ``"panel"``, or ``"dcs"``.

    Examples:
        >>> from schematika.catalog import InstrumentSpec
        >>> spec = InstrumentSpec(letters="TT", number="101")
        >>> spec.tag
        'TT-101'
        >>> spec.first_letter
        'T'
        >>> spec.location
        'field'
    """

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
    """How a device appears on P&ID drawings.

    Attributes:
        instrument: ISA identification for the instrument.
        service: Human-readable service description, e.g.
            ``"Cooling water supply temperature"``.
        range: Measurement range with units, e.g. ``"0-100 degC"``.
        output: Signal output specification, e.g. ``"4-20mA"``.

    Examples:
        >>> from schematika.catalog import InstrumentSpec, ProcessSpec
        >>> inst = InstrumentSpec(letters="TT", number="101")
        >>> spec = ProcessSpec(instrument=inst, service="CW supply temp",
        ...                    range="0-100 degC", output="4-20mA")
        >>> spec.instrument.tag
        'TT-101'
        >>> spec.service
        'CW supply temp'
    """

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

    Single source of truth for device identity. Both ``PIDBuilder`` and
    ``CircuitBuilder``/field-devices reference ``CatalogDevice`` entries by tag.

    Attributes:
        tag: Unique device identifier, e.g. ``"TT-101"``.
        description: Human-readable description of the device.
        manufacturer: Manufacturer name (optional).
        model: Model or part number (optional).
        process: P&ID appearance data; ``None`` if not shown on P&ID.
        electrical: Electrical drawing data; ``None`` if not shown on
            electrical drawings.

    Examples:
        >>> from schematika.catalog import (
        ...     CatalogDevice, InstrumentSpec, ProcessSpec)
        >>> inst = InstrumentSpec(letters="TT", number="101")
        >>> proc = ProcessSpec(instrument=inst, service="CW supply temp")
        >>> device = CatalogDevice(
        ...     tag="TT-101",
        ...     description="Cooling water temperature transmitter",
        ...     process=proc,
        ... )
        >>> device.tag
        'TT-101'
        >>> device.process.instrument.tag
        'TT-101'
    """

    tag: str  # "TT-101" (unique identifier)
    description: str  # "Cooling water temperature transmitter"
    manufacturer: str = ""
    model: str = ""
    process: ProcessSpec | None = None
    electrical: ElectricalSpec | None = None
