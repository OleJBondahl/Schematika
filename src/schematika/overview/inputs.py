"""Snapshot type for the system-overview pipeline."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True, kw_only=True)
class OverviewWire:
    """One normalised two-endpoint connection in the canonical pin_id vocabulary.

    Examples:
        >>> from schematika.overview.inputs import OverviewWire
        >>> w = OverviewWire(a="BMU1.J1.1", b="X1..1", label="GND")
        >>> w.kind
        'harness'
    """

    a: str  # canonical pin id "DEV.CONN.PIN"; empty connector -> "DEV..PIN"
    b: str
    label: str | None
    kind: str = "harness"


@dataclass(frozen=True, slots=True, kw_only=True)
class OverviewInput:
    """Frozen snapshot of all connectivity produced by a built Project.

    Examples:
        >>> from schematika.overview.inputs import OverviewInput, OverviewWire
        >>> w = OverviewWire(a="BMU1.J1.1", b="X1..1", label=None)
        >>> inp = OverviewInput(
        ...     wires=(w,),
        ...     field_device_tags=frozenset(),
        ...     terminal_tags=frozenset({"X1"}),
        ... )
        >>> inp.title
        'System Overview'
    """

    wires: tuple[OverviewWire, ...]
    field_device_tags: frozenset[str]
    terminal_tags: frozenset[str]
    title: str = "System Overview"


class ProjectLike(Protocol):
    """Structural type for objects that can produce an OverviewInput.

    Any object with an ``overview_input()`` method satisfies this Protocol;
    no explicit inheritance required.

    Examples:
        >>> from schematika.overview.inputs import OverviewInput, OverviewWire
        >>> from schematika.overview.render import build
        >>> class Stub:
        ...     def overview_input(self):
        ...         return OverviewInput(
        ...             wires=(), field_device_tags=frozenset(),
        ...             terminal_tags=frozenset())
        >>> hasattr(Stub(), "overview_input")
        True
    """

    def overview_input(self) -> "OverviewInput":
        """Return a frozen OverviewInput snapshot of all project connectivity."""
        ...
