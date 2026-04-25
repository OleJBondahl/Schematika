"""Device catalog for cross-domain instrument tracking.

Provides a single source of truth for devices that appear on both
P&ID and electrical drawings.
"""

from schematika.catalog.device import (
    CatalogDevice,
    ElectricalSpec,
    InstrumentSpec,
    ProcessSpec,
)
from schematika.catalog.cables import CableRegistry, CableSpec
from schematika.catalog.registry import DeviceCatalog
