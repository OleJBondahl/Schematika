"""PartSpec — the canonical part record and its category literal."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from schematika.catalog.identifiers import PartId

PartCategory = Literal["connector", "cable", "device", "terminal"]


@dataclass(frozen=True, slots=True, kw_only=True)
class PartSpec:
    """Canonical part specification; ``mpn`` is the manufacturer part number.

    Attributes:
        part: Catalog primary key.
        mpn: Manufacturer part number.
        category: One of ``"connector"``, ``"cable"``, ``"device"``,
            ``"terminal"``.
        description: Human-readable description.
        manufacturer: Manufacturer name; ``None`` if unspecified.
        notes: Free-form note; ``None`` if unspecified.

    Examples:
        >>> from schematika.catalog.identifiers import PartId
        >>> from schematika.catalog.parts import PartSpec
        >>> PartSpec(part=PartId("ferrule_1.5"), mpn="3200536",
        ...          category="terminal", description="1.5mm ferrule").category
        'terminal'
    """

    part: PartId
    mpn: str
    category: PartCategory
    description: str
    manufacturer: str | None = None
    notes: str | None = None
