"""CableBuilder — accumulate wires + connectors into a CableBuildResult."""

from __future__ import annotations

from typing import TYPE_CHECKING

from schematika.cable.errors import CableError
from schematika.cable.result import CableBuildResult

if TYPE_CHECKING:
    from schematika.catalog.connectors import ConnectorInstance
    from schematika.catalog.identifiers import CableId, ConnectorId, DeviceTag, PartId
    from schematika.catalog.result import ResolvedCatalog
    from schematika.catalog.wires import Wire


class CableBuilder:
    """Mutable builder for one cable's wires and connectors.

    Mutable-builder exception (invariant 5): like ``Catalog``, it accumulates
    state across ``add_*`` calls and freezes on ``build()``. It takes a
    ``ResolvedCatalog`` at construction; ``build()`` is parameterless.

    Examples:
        >>> from schematika.cable.cable_builder import CableBuilder
        >>> from schematika.catalog.identifiers import CableId, PartId
        >>> from schematika.catalog.cables import CableProductSpec
        >>> from schematika.catalog.result import ResolvedCatalog
        >>> cat = ResolvedCatalog(parts={}, connectors={},
        ...     cable_products={PartId("cab"): CableProductSpec(
        ...         part=PartId("cab"), conductor_count=1)},
        ...     devices={}, cable_instances={})
        >>> b = CableBuilder(name=CableId("W1"), catalog=cat)
        >>> b.set_cable_product(PartId("cab"))
        >>> b.build().cable_product
        'cab'
    """

    def __init__(self, *, name: CableId, catalog: ResolvedCatalog) -> None:
        """Start a cable builder bound to *name* and a resolved *catalog*."""
        self._name = name
        self._catalog = catalog
        self._cable_product: PartId | None = None
        self._connectors: dict[tuple[DeviceTag, ConnectorId], ConnectorInstance] = {}
        self._wires: list[Wire] = []

    def set_cable_product(self, part: PartId, /) -> None:
        """Set the cable product key; it must resolve in the catalog.

        Raises:
            CatalogLookupError: if *part* is not a registered cable product.
        """
        self._catalog.lookup_cable_product(part)
        self._cable_product = part

    def add_connector(self, connector: ConnectorInstance, /) -> None:
        """Register a connector instance at one end of the cable.

        Raises:
            CatalogLookupError: if the connector's part is not registered.
        """
        self._catalog.lookup_connector(connector.part)
        self._connectors[connector.device, connector.name] = connector

    def add_wire(self, wire: Wire, /) -> None:
        """Add a wire; any connectorized endpoint must be a registered connector.

        Raises:
            CableError: if an endpoint references an unregistered connector.
        """
        for endpoint in (wire.source, wire.target):
            if (
                endpoint.connector is not None
                and (endpoint.device, endpoint.connector) not in self._connectors
            ):
                msg = f"Wire references unregistered connector {endpoint.connector!r}"
                raise CableError(msg)
        self._wires.append(wire)

    def build(self) -> CableBuildResult:
        """Freeze the accumulated state into a ``CableBuildResult``.

        Raises:
            CableError: if no cable product has been set.
        """
        if self._cable_product is None:
            msg = f"Cable {self._name!r} has no cable product set"
            raise CableError(msg)
        return CableBuildResult(
            name=self._name,
            wires=tuple(self._wires),
            connectors=tuple(self._connectors.values()),
            cable_product=self._cable_product,
        )
