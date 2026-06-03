"""PartSpec — the canonical part record and its category literal."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from schematika.catalog.identifiers import PartId

PartCategory = Literal["connector", "cable", "device", "terminal"]
# __doc__ assigned post-definition: a Literal alias has no inline docstring slot,
# and the api-docs-audit gate requires public symbols to be documented.
PartCategory.__doc__ = (
    "Valid category strings for a :class:`PartSpec`.\n\n"
    'One of ``"connector"``, ``"cable"``, ``"device"``, ``"terminal"``.\n\n'
    "Examples:\n"
    '    ``"connector"`` identifies a multi-pin connector part;\n'
    '    ``"cable"`` a cable assembly; ``"device"`` a generic instrument\n'
    '    or equipment item; ``"terminal"`` a ferrule or terminal block entry.\n'
    "    >>> 'connector' in ('connector', 'cable', 'device', 'terminal')\n"
    "    True\n"
)


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
