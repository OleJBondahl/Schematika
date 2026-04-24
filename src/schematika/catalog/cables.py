"""Cable specifications for cross-domain connection tracking.

Provides a single source of truth for cable connections that appear on
block diagrams, electrical schematics, and cable schedules.
"""

from __future__ import annotations

from dataclasses import dataclass

from schematika.catalog.errors import CatalogError

__all__ = ["CableRegistry", "CableSpec"]


@dataclass(frozen=True)
class CableSpec:
    """A cable connection between two devices or subsystems.

    Attributes:
        tag: Cable designation (e.g. "W0001").
        spec: Cable specification string (e.g. "4x2.5", "2x2x0.5", "CAT7").
        cable_type: Type for style mapping: "power_ac", "power_dc", "signal",
            "ethernet", or "control".
        from_device: Tag of the source device or subsystem.
        to_device: Tag of the destination device or subsystem.
        description: Optional human-readable description.
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


class CableRegistry:
    """Project-level registry of cable connections.

    Cables are registered once and referenced by tag across all drawing
    modules (electrical, P&ID, block diagram, cable schedule).
    """

    def __init__(self) -> None:
        self._cables: dict[str, CableSpec] = {}

    def register(self, cable: CableSpec) -> None:
        """Register a cable. Raises ValueError if tag already exists."""
        if cable.tag in self._cables:
            raise CatalogError(f"Cable '{cable.tag}' already registered")
        self._cables[cable.tag] = cable

    def get(self, tag: str) -> CableSpec:
        """Look up a cable by tag. Raises KeyError if not found."""
        if tag not in self._cables:
            raise KeyError(f"Cable '{tag}' not found in registry")
        return self._cables[tag]

    def __contains__(self, tag: str) -> bool:
        return tag in self._cables

    def __len__(self) -> int:
        return len(self._cables)

    def __iter__(self):
        return iter(self._cables.values())

    def by_device(self, device_tag: str) -> list[CableSpec]:
        """Return all cables connected to a device (as source or destination)."""
        return [
            c
            for c in self._cables.values()
            if c.from_device == device_tag or c.to_device == device_tag
        ]

    @property
    def cables(self) -> list[CableSpec]:
        """All registered cables."""
        return list(self._cables.values())
