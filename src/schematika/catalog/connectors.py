# src/schematika/catalog/connectors.py
"""Connector product spec and project-level connector instance."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from schematika.catalog.identifiers import ConnectorId, DeviceTag, PartId


@dataclass(frozen=True, slots=True, kw_only=True)
class ConnectorSpec:
    """Canonical connector product specification.

    The pins tuple lives here, not on ``ConnectorInstance``, so connectors
    with identical pinouts reference one spec (audit F10).

    Attributes:
        part: Catalog primary key.
        pincount: Declared pin count.
        pins: Canonical ``port_id`` ordering.
        style: Cosmetic; ``None`` if unspecified.
        notes: Cosmetic; ``None`` if unspecified.

    Examples:
        >>> from schematika.catalog.identifiers import PartId
        >>> from schematika.catalog.connectors import ConnectorSpec
        >>> ConnectorSpec(part=PartId("phoenix_3pos"), pincount=3,
        ...               pins=("1", "2", "PE")).pins
        ('1', '2', 'PE')
    """

    part: PartId
    pincount: int
    pins: tuple[str, ...]
    style: str | None = None
    notes: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ConnectorInstance:
    """A project-level connector instance.

    The wired pin set is derived from ``Wire`` endpoints by the validator,
    not stored here. ``device`` is the owning device: the catalog registry is
    keyed by the ``(device, name)`` pair because the same ``ConnectorId``
    recurs across devices.

    Attributes:
        device: Owning device tag.
        name: Connector-instance handle.
        part: Connector product key.
        notes: Cosmetic; ``None`` if unspecified.

    Examples:
        >>> from schematika.catalog.identifiers import ConnectorId, DeviceTag, PartId
        >>> from schematika.catalog.connectors import ConnectorInstance
        >>> ConnectorInstance(
        ...     device=DeviceTag("-Q1"), name=ConnectorId("J1"),
        ...     part=PartId("phoenix_3pos"),
        ... ).name
        'J1'
    """

    device: DeviceTag
    name: ConnectorId
    part: PartId
    notes: str | None = None
