"""CabinetGridAllocator: fixed Y-zones + per-rung column allocation.

Spike prototype for the `grid-astar-router` research track. Grounded in
Schematika's real mm-based spacing constants (schematika.core.constants /
schematika.electrical.model.constants) rather than arbitrary pixel values,
so the zone boundaries look like something a real cabinet drawing would use.

Not production code: no docstring-coverage/darglint compliance attempted.
"""

from dataclasses import dataclass

from schematika.core.geometry import Point
from schematika.electrical.model.constants import CIRCUIT_SPACING, SPACING_STANDARD


@dataclass(frozen=True)
class GridZones:
    """Fixed Y-coordinates (mm) for each horizontal band of a cabinet ladder.

    Spacing between zones reuses SPACING_STANDARD (60mm) — the existing
    "standard symbol / compact circuit spacing" constant from
    electrical/model/constants.py — rather than inventing a new number.
    """

    power_rail_top: float = 0.0
    protection: float = SPACING_STANDARD
    control: float = 2 * SPACING_STANDARD
    coils: float = 3 * SPACING_STANDARD
    power_rail_bottom: float = 4 * SPACING_STANDARD
    terminals: float = 5 * SPACING_STANDARD


ZONE_ORDER: tuple[str, ...] = (
    "power_rail_top",
    "protection",
    "control",
    "coils",
    "power_rail_bottom",
    "terminals",
)


@dataclass(frozen=True)
class GridSlot:
    """One allocated cell: a (column, zone) pair resolved to a real Point."""

    column: int
    zone: str
    point: Point


class CabinetGridAllocator:
    """Deterministic column/zone allocator for a cabinet-ladder page.

    Columns are rungs (vertical circuit branches); zones are the fixed
    horizontal bands every rung shares (power rail, protection, control,
    coils, power rail, terminals). `column_spacing` reuses CIRCUIT_SPACING
    (100mm — "control / single-pole circuits" per the existing constant
    table) as the default rung pitch.
    """

    def __init__(
        self,
        zones: GridZones | None = None,
        *,
        column_spacing: float = CIRCUIT_SPACING,
        start_x: float = 0.0,
    ) -> None:
        self.zones = zones or GridZones()
        self.column_spacing = column_spacing
        self.start_x = start_x

    def column_x(self, column: int) -> float:
        """X-coordinate (mm) of the given rung index."""
        return self.start_x + column * self.column_spacing

    def slot(self, column: int, zone: str) -> GridSlot:
        """Resolve a single (column, zone) cell to a real-coordinate Point."""
        y = getattr(self.zones, zone)
        return GridSlot(column=column, zone=zone, point=Point(self.column_x(column), y))

    def place_rung(self, column: int, zone_sequence: list[str]) -> list[GridSlot]:
        """Allocate one rung's worth of slots, top-to-bottom, in `zone_sequence`.

        `zone_sequence` need not use every zone (e.g. a rung with no
        terminal branch just omits "terminals") but must list zones in the
        order they appear in ZONE_ORDER, since a rung always flows
        top-to-bottom.
        """
        return [self.slot(column, z) for z in zone_sequence]

    def rail_span(
        self, zone: str, first_column: int, last_column: int
    ) -> tuple[Point, Point]:
        """Endpoints (mm) of a horizontal power-rail bus spanning columns."""
        y = getattr(self.zones, zone)
        return (
            Point(self.column_x(first_column), y),
            Point(self.column_x(last_column), y),
        )
