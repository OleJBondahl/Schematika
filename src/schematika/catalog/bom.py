# src/schematika/catalog/bom.py
"""BOMRow — one row of the consolidated bill of materials."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from schematika.catalog.identifiers import PartId


@dataclass(frozen=True, slots=True, kw_only=True)
class BOMRow:
    """One consolidated BOM row.

    ``used_by`` carries stringified handles (e.g. ``"K1"``, ``"W12"``) to keep
    the type simple.

    Attributes:
        part: Catalog primary key.
        count: Aggregate quantity.
        used_by: Stringified consumer handles.

    Examples:
        >>> from schematika.catalog.identifiers import PartId
        >>> from schematika.catalog.bom import BOMRow
        >>> BOMRow(part=PartId("phoenix_3pos"), count=2, used_by=("J1", "J3")).count
        2
    """

    part: PartId
    count: int
    used_by: tuple[str, ...]
