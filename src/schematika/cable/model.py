"""Immutable data model for cable harness drawings."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CableConnector:
    """One end of a cable connection (device or terminal block)."""

    designator: str
    pins: tuple[str, ...]
    type: str = ""
    subtype: str = ""
    style: str = ""
    notes: str = ""
    show_pincount: bool = False
    loops: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class CableDef:
    """Physical cable properties."""

    designator: str
    wirecount: int
    wire_gauge: float = 0.0
    gauge_unit: str = "mm2"
    length: float = 0.0
    category: str = "cable"
    wire_colors: tuple[str, ...] = ()
    notes: str = ""
    shield: bool = False


@dataclass(frozen=True)
class CableConnection:
    """A single wire-level connection through a cable."""

    from_connector: str
    from_pin: str
    cable: str
    wire: int
    to_connector: str
    to_pin: str


@dataclass(frozen=True)
class CableDrawing:
    """One cable + its connectors + wire-level connections; renders to one SVG."""

    cable: CableDef
    connectors: tuple[CableConnector, ...]
    connections: tuple[CableConnection, ...]
    title: str = ""
