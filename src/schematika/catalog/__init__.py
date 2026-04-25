"""Device catalog for cross-domain instrument tracking.

Provides a single source of truth for devices that appear on both
P&ID and electrical drawings.
"""

from schematika.catalog.device import CatalogDevice, InstrumentSpec, ProcessSpec
from schematika.catalog.errors import CatalogError
from schematika.catalog.registry import DeviceCatalog

__all__ = [
    "CatalogDevice",
    "CatalogError",
    "DeviceCatalog",
    "InstrumentSpec",
    "ProcessSpec",
]
