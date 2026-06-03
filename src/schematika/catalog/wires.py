# src/schematika/catalog/wires.py
"""Wire — the logical connection record."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from schematika.catalog.identifiers import NetId
    from schematika.catalog.refs import PinRef


@dataclass(frozen=True, slots=True, kw_only=True)
class Wire:
    """Logical connection record between two pins on a net.

    Attributes:
        net: Canonical net name.
        source: Source pin reference.
        target: Target pin reference.
        color: Conductor color; ``None`` if unknown.
        length_mm: Length in mm; ``None`` if unknown.
        notes: Cosmetic; ``None`` if unspecified.

    Examples:
        >>> from schematika.catalog.identifiers import ConnectorId, DeviceTag, NetId
        >>> from schematika.catalog.refs import PinRef
        >>> from schematika.catalog.wires import Wire
        >>> p = PinRef(device=DeviceTag("-Q1"), connector=ConnectorId("J1"),
        ...            port_id="1")
        >>> Wire(net=NetId("VBUS"), source=p, target=p).net
        'VBUS'
    """

    net: NetId
    source: PinRef
    target: PinRef
    color: str | None = None
    length_mm: float | None = None
    notes: str | None = None
