"""Production BOM: designator grouping + natural sort, decoupled from supplier data."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from schematika.core.utils import natural_sort_key

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence
    from pathlib import Path

DEFAULT_HEADER = [
    "Designator(s)",
    "Footprint",
    "Quantity",
    "Designation",
    "Manufacturer",
    "Mfr Part Number",
    "Supplier",
    "Supplier Part Number",
    "Note",
]


@runtime_checkable
class PartLike(Protocol):
    """Structural type for a placed PCB part: ref/value/footprint.

    Examples:
        >>> class _P:
        ...     ref = "R1"
        ...     value = "10k"
        ...     footprint = "Resistor_SMD:R_0603"
        >>> isinstance(_P(), PartLike)
        True
    """

    ref: str
    value: str
    footprint: str


@dataclass(frozen=True, slots=True)
class SupplierInfo:
    """One footprint's sourcing data for the BOM.

    Examples:
        >>> SupplierInfo("Yageo", "RC0603", "Mouser", "603-RC0603", "").manufacturer
        'Yageo'
    """

    manufacturer: str
    mfr_part_number: str
    supplier: str
    supplier_part_number: str
    note: str = ""


@dataclass(frozen=True, slots=True)
class BomRow:
    """One consolidated, supplier-annotated BOM row.

    Examples:
        >>> BomRow(("R1", "R2"), "R_0603", 2, "10k", "Yageo", "RC0603",
        ...        "Mouser", "603-RC0603", "").quantity
        2
    """

    designators: tuple[str, ...]
    footprint: str
    quantity: int
    designation: str
    manufacturer: str
    mfr_part_number: str
    supplier: str
    supplier_part_number: str
    note: str


def group_parts(parts: Iterable[PartLike]) -> dict[tuple[str, str], list[str]]:
    """Group part references by their (footprint, value) pair.

    Examples:
        >>> class _P:
        ...     def __init__(self, ref, value, footprint):
        ...         self.ref, self.value, self.footprint = ref, value, footprint
        >>> sorted(group_parts([_P("R1", "10k", "R_0603")]).items())
        [(('R_0603', '10k'), ['R1'])]
    """
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for part in parts:
        groups[(part.footprint, part.value)].append(part.ref)
    return groups


def build_bom_rows(
    parts: Iterable[PartLike],
    supplier_lookup: Mapping[str, SupplierInfo],
    *,
    footprint_library_prefix: str = "",
) -> tuple[BomRow, ...]:
    """Group parts by (footprint, value), sort naturally, join to supplier data.

    Args:
        parts: Placed parts to summarize (e.g. a SKiDL circuit's `.parts`).
        supplier_lookup: Sourcing data keyed by the part's raw footprint string.
        footprint_library_prefix: Stripped from the front of each footprint
            before it's stored on the row (e.g. a KiCad library name prefix).

    Returns:
        One `BomRow` per (footprint, value) group, sorted by first designator.

    Raises:
        KeyError: a group's footprint has no `supplier_lookup` entry -- a new
            part template shipping without supplier data must fail the build,
            not produce a BOM with a silent hole in it.
    """
    groups = group_parts(parts)

    rows: list[BomRow] = []
    for (footprint, value), designators in groups.items():
        if footprint not in supplier_lookup:
            msg = (
                f"no supplier entry for footprint {footprint!r} "
                f"(designators: {designators})"
            )
            raise KeyError(msg)
        info = supplier_lookup[footprint]
        rows.append(
            BomRow(
                designators=tuple(sorted(designators, key=natural_sort_key)),
                footprint=footprint.removeprefix(footprint_library_prefix),
                quantity=len(designators),
                designation=value,
                manufacturer=info.manufacturer,
                mfr_part_number=info.mfr_part_number,
                supplier=info.supplier,
                supplier_part_number=info.supplier_part_number,
                note=info.note,
            )
        )
    rows.sort(key=lambda r: natural_sort_key(r.designators[0]))
    return tuple(rows)


def write_bom_xlsx(
    rows: Sequence[BomRow], path: Path, *, header: Sequence[str] | None = None
) -> None:
    """Write `rows` to an XLSX BOM sheet at `path`. Requires the `excel` extra."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "BOM"
    ws.append(list(header) if header is not None else list(DEFAULT_HEADER))
    for row in rows:
        ws.append(
            [
                ", ".join(row.designators),
                row.footprint,
                row.quantity,
                row.designation,
                row.manufacturer,
                row.mfr_part_number,
                row.supplier,
                row.supplier_part_number,
                row.note,
            ]
        )
    ws.column_dimensions["D"].width = 30
    ws.column_dimensions["H"].width = 25
    ws.column_dimensions["I"].width = 60
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
