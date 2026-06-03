"""Catalog: shared identity types and the cross-domain device/cable catalog.

Single source of truth for devices and cable instances that appear across
P&ID, electrical, and cable-schedule drawings.

Import order is fixed (errors -> identifiers -> refs -> parts -> connectors
-> device -> wires -> bom -> nets -> result -> registry -> cables) to keep
the runtime import graph acyclic; see CLAUDE.md "Import-order-sensitive files".
The I001 (isort) rule is suppressed for all __init__.py files in
pyproject.toml, so ruff will not reorder these imports -- do not alphabetize.
"""

from schematika.catalog.errors import (
    CatalogError,
    CatalogLookupError,
    CatalogValidationError,
)
from schematika.catalog.identifiers import (
    CableId,
    CircuitId,
    ConnectorId,
    DeviceTag,
    NetId,
    PartId,
    TagPrefix,
)
from schematika.catalog.refs import PartRef, PinRef
from schematika.catalog.parts import PartCategory, PartSpec
from schematika.catalog.connectors import ConnectorInstance, ConnectorSpec
from schematika.catalog.device import CatalogDevice, InstrumentSpec, ProcessSpec
from schematika.catalog.wires import Wire
from schematika.catalog.bom import BOMRow
from schematika.catalog.nets import normalize_net_name
from schematika.catalog.result import ResolvedCatalog
from schematika.catalog.registry import Catalog, DeviceCatalog
from schematika.catalog.cables import (
    CableInstance,
    CableInstanceRegistry,
    CableProductSpec,
    CableRegistry,
    CableSpec,
)

__all__ = [
    "BOMRow",
    "CableId",
    "CableInstance",
    "CableInstanceRegistry",
    "CableProductSpec",
    "CableRegistry",
    "CableSpec",
    "Catalog",
    "CatalogDevice",
    "CatalogError",
    "CatalogLookupError",
    "CatalogValidationError",
    "CircuitId",
    "ConnectorId",
    "ConnectorInstance",
    "ConnectorSpec",
    "DeviceCatalog",
    "DeviceTag",
    "InstrumentSpec",
    "NetId",
    "PartCategory",
    "PartId",
    "PartRef",
    "PartSpec",
    "PinRef",
    "ProcessSpec",
    "ResolvedCatalog",
    "TagPrefix",
    "Wire",
    "normalize_net_name",
]
