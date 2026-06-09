"""Snapshot type for the system-overview pipeline."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True, kw_only=True)
class OverviewWire:
    """One normalised two-endpoint connection in the canonical pin_id vocabulary."""

    a: str  # canonical pin id "DEV.CONN.PIN"; empty connector -> "DEV..PIN"
    b: str
    label: str | None
    kind: str = "harness"


@dataclass(frozen=True, slots=True, kw_only=True)
class OverviewInput:
    """Frozen snapshot of all connectivity produced by a built Project."""

    wires: tuple[OverviewWire, ...]
    field_device_tags: frozenset[str]
    terminal_tags: frozenset[str]
    title: str = "System Overview"


class ProjectLike(Protocol):
    """Structural type for objects that can produce an OverviewInput."""

    def overview_input(self) -> "OverviewInput":
        """Return a frozen OverviewInput snapshot of all project connectivity."""
        ...
