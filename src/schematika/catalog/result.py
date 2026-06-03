# src/schematika/catalog/result.py
"""ResolvedCatalog -- the frozen, pure-resolver snapshot of a Catalog."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from schematika.catalog.errors import CatalogLookupError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from schematika.catalog.cables import CableInstance, CableProductSpec
    from schematika.catalog.connectors import ConnectorSpec
    from schematika.catalog.device import CatalogDevice
    from schematika.catalog.identifiers import PartId
    from schematika.catalog.parts import PartSpec


def _lookup[K, V](mapping: Mapping[K, V], key: K, kind: str) -> V:
    """Return ``mapping[key]`` or raise ``CatalogLookupError`` if absent."""
    try:
        return mapping[key]
    except KeyError:
        msg = f"{kind} {key!r} not found in catalog"
        raise CatalogLookupError(msg) from None


@dataclass(frozen=True, slots=True, kw_only=True)
class ResolvedCatalog:
    """Frozen, pure-resolver snapshot. All lookups are O(1) dict reads.

    Attributes:
        parts: ``PartId`` -> ``PartSpec``.
        connectors: ``PartId`` -> ``ConnectorSpec``.
        cable_products: ``PartId`` -> ``CableProductSpec``.
        devices: device ``tag`` -> ``CatalogDevice``.
        cable_instances: cable ``tag`` -> ``CableInstance``.

    Examples:
        >>> from schematika.catalog.identifiers import PartId
        >>> from schematika.catalog.parts import PartSpec
        >>> from schematika.catalog.result import ResolvedCatalog
        >>> rc = ResolvedCatalog(
        ...     parts={PartId("p1"): PartSpec(part=PartId("p1"), mpn="1",
        ...            category="device", description="d")},
        ...     connectors={}, cable_products={}, devices={}, cable_instances={})
        >>> rc.lookup_part(PartId("p1")).mpn
        '1'
    """

    parts: Mapping[PartId, PartSpec]
    connectors: Mapping[PartId, ConnectorSpec]
    cable_products: Mapping[PartId, CableProductSpec]
    devices: Mapping[str, CatalogDevice]
    cable_instances: Mapping[str, CableInstance]

    def lookup_part(self, name: PartId, /) -> PartSpec:
        """Resolve a part spec by its ``PartId`` key.

        Args:
            name: The catalog primary key.

        Returns:
            The corresponding ``PartSpec``.

        Raises:
            CatalogLookupError: if ``name`` is not registered.
        """
        return _lookup(self.parts, name, "PartSpec")

    def lookup_connector(self, name: PartId, /) -> ConnectorSpec:
        """Resolve a connector spec by its ``PartId`` key.

        Args:
            name: The catalog primary key.

        Returns:
            The corresponding ``ConnectorSpec``.

        Raises:
            CatalogLookupError: if ``name`` is not registered.
        """
        return _lookup(self.connectors, name, "ConnectorSpec")

    def lookup_cable_product(self, name: PartId, /) -> CableProductSpec:
        """Resolve a cable-product spec by its ``PartId`` key.

        Args:
            name: The catalog primary key.

        Returns:
            The corresponding ``CableProductSpec``.

        Raises:
            CatalogLookupError: if ``name`` is not registered.
        """
        return _lookup(self.cable_products, name, "CableProductSpec")

    def lookup_device(self, tag: str, /) -> CatalogDevice:
        """Resolve a device by its tag.

        Args:
            tag: The device tag.

        Returns:
            The corresponding ``CatalogDevice``.

        Raises:
            CatalogLookupError: if ``tag`` is not registered.
        """
        return _lookup(self.devices, tag, "CatalogDevice")

    def lookup_cable_instance(self, tag: str, /) -> CableInstance:
        """Resolve a cable instance by its tag.

        Args:
            tag: The cable tag.

        Returns:
            The corresponding ``CableInstance``.

        Raises:
            CatalogLookupError: if ``tag`` is not registered.
        """
        return _lookup(self.cable_instances, tag, "CableInstance")
