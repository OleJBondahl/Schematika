"""Immutable data model for cable harness drawings."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CableConnector:
    """One end of a cable connection (device or terminal block).

    Attributes:
        designator: Component tag, e.g. "400V Main", "X01", "PT-01".
        pins: Pin names in connection order.
        type: Connector type, e.g. "M12", "Crimp ferrule".
        subtype: Connector subtype, e.g. "female", "0.75mm²".
        style: Visual style; "simple" for single-pin ferrules.
        notes: Free text shown on diagram, e.g. "Wire ferrule".
        show_pincount: Whether to show the pin count label.
        loops: Internal jumper pairs, e.g. (("1", "3"),).
    """

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
    """Physical cable properties.

    Attributes:
        designator: Cable tag, e.g. "A-W001".
        wirecount: Number of conductors.
        wire_gauge: Cross-section value.
        gauge_unit: Unit for wire_gauge, default "mm2".
        length: Cable length value (0 = unspecified).
        category: "cable", "bundle", or "shielded".
        wire_colors: Per-wire IEC color codes, e.g. ("BN", "BU", "GNYE").
        notes: Free text, e.g. "3P+PE".
        shield: Whether the cable has a shield conductor.
    """

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
    """A single wire-level connection through a cable.

    Attributes:
        from_connector: Source connector designator.
        from_pin: Pin name on the source connector.
        cable: Cable designator.
        wire: Wire number (1-based).
        to_connector: Target connector designator.
        to_pin: Pin name on the target connector.
    """

    from_connector: str
    from_pin: str
    cable: str
    wire: int
    to_connector: str
    to_pin: str


@dataclass(frozen=True)
class CableDrawing:
    """Complete cable drawing: one cable with its connectors and wire connections.

    Each CableDrawing maps to one SVG diagram.

    Attributes:
        cable: Cable physical properties.
        connectors: The connectors at each end of the cable.
        connections: Per-wire connection mapping through the cable.
        title: Display title, e.g. "Pump P-01".
    """

    cable: CableDef
    connectors: tuple[CableConnector, ...]
    connections: tuple[CableConnection, ...]
    title: str = ""
