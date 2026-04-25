"""Internal device definition for BOM tracking."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InternalDevice:
    """Metadata for an internal cabinet component used in BOM generation.

    Associates a tag prefix with its MPN and description so the builder can
    accumulate a Bill of Materials while generating circuits.

    Attributes:
        prefix: Tag prefix for autonumbering, e.g. ``"Q"``, ``"K"``, ``"F"``.
        mpn: Manufacturer part number, e.g. ``"LC1D09"``.
        description: Human-readable description, e.g. ``"Contactor 9A"``.

    Examples:
        >>> from schematika.electrical import InternalDevice
        >>> dev = InternalDevice(prefix="K", mpn="LC1D09", description="Contactor 9A")
        >>> dev.prefix
        'K'
        >>> dev.mpn
        'LC1D09'
    """

    prefix: str
    mpn: str
    description: str
