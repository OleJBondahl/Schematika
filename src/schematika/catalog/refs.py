# src/schematika/catalog/refs.py
"""Catalog reference types: PinRef and PartRef."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from schematika.catalog.identifiers import ConnectorId, DeviceTag, PartId


@dataclass(frozen=True, slots=True, kw_only=True)
class PinRef:
    """Reference to a physical pin on a connector instance.

    ``device`` makes the endpoint self-describing: the same ``ConnectorId``
    (e.g. ``"J1"``) recurs across devices, so ``(connector, port_id)`` alone
    does not locate the device. This mirrors the ``device.connector.pin``
    endpoint key the consumer overview modules use.

    Attributes:
        device: Owning device tag.
        connector: Connector-instance handle.
        port_id: IEC pin label, free-form per spec (e.g. ``"1"``, ``"PE"``).

    Examples:
        >>> from schematika.catalog.identifiers import ConnectorId, DeviceTag
        >>> from schematika.catalog.refs import PinRef
        >>> ref = PinRef(device=DeviceTag("-Q1"),
        ...              connector=ConnectorId("J1"), port_id="1")
        >>> ref.port_id
        '1'
    """

    device: DeviceTag
    connector: ConnectorId
    port_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PartRef:
    """Catalog ref returned from a ``Catalog.add_*`` builder call.

    ``tag`` is filled lazily by the autonumberer when the part is placed in a
    circuit; identity is by ``part`` only.

    Attributes:
        part: Catalog primary key.
        tag: Device tag once placed; ``None`` until then.

    Examples:
        >>> from schematika.catalog.identifiers import PartId
        >>> from schematika.catalog.refs import PartRef
        >>> PartRef(part=PartId("phoenix_3pos")).tag is None
        True
    """

    part: PartId
    tag: DeviceTag | None = None
