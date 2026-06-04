"""Cable specifications for cross-domain connection tracking.

Provides a single source of truth for cable connections that appear on
block diagrams, electrical schematics, and cable schedules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from schematika.catalog.registry import Catalog

if TYPE_CHECKING:
    from collections.abc import Iterator

    from schematika.catalog.identifiers import PartId

__all__ = [
    "CableInstance",
    "CableInstanceRegistry",
    "CableProductSpec",
    "CableRegistry",
    "CableSpec",
]


@dataclass(frozen=True)
class CableInstance:
    """A per-project cable connection between two devices or subsystems.

    Renamed from ``CableSpec`` in Phase 0: this is a project-level cable
    *instance*, distinct from the cable *product* spec (``CableProductSpec``).
    ``CableSpec`` remains as a deprecated alias.

    Attributes:
        tag: Cable designation (e.g. "W0001").
        spec: Cable specification string (e.g. "4x2.5", "2x2x0.5", "CAT7").
        cable_type: Type for style mapping: "power_ac", "power_dc", "signal",
            "ethernet", or "control".
        from_device: Tag of the source device or subsystem.
        to_device: Tag of the destination device or subsystem.
        description: Optional human-readable description.

    Examples:
        >>> cable = CableInstance(
        ...     tag="W0001", spec="4x2.5", cable_type="power_ac",
        ...     from_device="M1", to_device="X1",
        ... )
        >>> cable.label
        '4x2.5 (W0001)'
    """

    tag: str
    spec: str
    cable_type: str
    from_device: str
    to_device: str
    description: str = ""

    @property
    def label(self) -> str:
        """Display label for the cable, e.g. '4x2.5 (W0001)'."""
        return f"{self.spec} ({self.tag})"


@dataclass(frozen=True, slots=True, kw_only=True)
class CableProductSpec:
    """Canonical cable product specification (e.g. 'Lapp OELFLEX 110 4x0.75').

    Distinct from ``CableInstance`` (a per-project cable connection).

    Attributes:
        part: Catalog primary key.
        conductor_count: Number of conductors.
        default_length_mm: Catalog default length in mm; ``None`` if unset.
        gauge_mm2: Conductor cross-section in mm²; ``None`` if unspecified.
        category: Cosmetic cable category (e.g. ``"control"``); ``None`` if unset.
        type: Cosmetic; ``None`` if unspecified.
        subtype: Cosmetic; ``None`` if unspecified.
        notes: Cosmetic; ``None`` if unspecified.

    Examples:
        >>> from schematika.catalog.identifiers import PartId
        >>> CableProductSpec(part=PartId("oelflex_110_4x075"),
        ...                  conductor_count=4).conductor_count
        4
    """

    part: PartId
    conductor_count: int
    default_length_mm: float | None = None
    gauge_mm2: float | None = None
    category: str | None = None
    type: str | None = None
    subtype: str | None = None
    notes: str | None = None


class CableInstanceRegistry(Catalog):
    """Deprecated cable-only face of ``Catalog``.

    Deprecated: use ``Catalog`` with ``add_cable_instance`` /
    ``get_cable_instance``. Kept for one release cycle (Phase 0 merge).
    Re-exposes the legacy ``register`` / ``get`` names and cable-scoped
    dunders. Device methods are inherited from ``Catalog`` and remain
    callable, but are out of scope for this deprecated face.

    Examples:
        >>> reg = CableInstanceRegistry()
        >>> cable = CableInstance(
        ...     tag="W0001", spec="4x2.5", cable_type="power_ac",
        ...     from_device="M1", to_device="X1",
        ... )
        >>> reg.register(cable)
        >>> reg.get("W0001").tag
        'W0001'
    """

    def register(self, cable: CableInstance) -> None:
        """Deprecated alias for ``Catalog.add_cable_instance``."""
        self.add_cable_instance(cable)

    def get(self, tag: str) -> CableInstance:
        """Deprecated alias for ``Catalog.get_cable_instance``."""
        return self.get_cable_instance(tag)

    def __contains__(self, tag: str) -> bool:
        """Return True if *tag* is a registered cable instance."""
        return tag in self._cables

    def __len__(self) -> int:
        """Return the number of registered cable instances."""
        return len(self._cables)

    def __iter__(self) -> Iterator[CableInstance]:
        """Iterate over all ``CableInstance`` entries."""
        return iter(self._cables.values())


# Deprecated Phase 0 aliases — remove in a later phase.
CableSpec = CableInstance
CableRegistry = CableInstanceRegistry
