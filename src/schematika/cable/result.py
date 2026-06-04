"""CableBuildResult — the frozen output of CableBuilder.build()."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from schematika.catalog.connectors import ConnectorInstance
    from schematika.catalog.identifiers import CableId, PartId
    from schematika.catalog.wires import Wire


@dataclass(frozen=True, slots=True, kw_only=True)
class CableBuildResult:
    """A resolved cable: its wires, connector instances, and product key.

    Attributes:
        name: Cable instance handle.
        wires: The cable's wire-level connections.
        connectors: Connector instances at the cable's ends.
        cable_product: Catalog key of the cable product; used for BOM generation.

    Examples:
        >>> from schematika.cable.result import CableBuildResult
        >>> from schematika.catalog.identifiers import CableId, PartId
        >>> CableBuildResult(name=CableId("W1"), wires=(), connectors=(),
        ...                  cable_product=PartId("cab")).cable_product
        'cab'
    """

    name: CableId
    wires: tuple[Wire, ...]
    connectors: tuple[ConnectorInstance, ...]
    cable_product: PartId
