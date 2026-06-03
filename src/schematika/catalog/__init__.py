"""Catalog: shared identity types and the cross-domain device/cable catalog.

Single source of truth for devices and cable instances that appear across
P&ID, electrical, and cable-schedule drawings.

Import order is fixed (errors -> device -> registry -> cables) to keep the
runtime import graph acyclic; see CLAUDE.md "Import-order-sensitive files".
The I001 (isort) rule is suppressed for all __init__.py files in
pyproject.toml, so ruff will not reorder these imports -- do not alphabetize.
"""

from schematika.catalog.errors import CatalogError
from schematika.catalog.device import CatalogDevice, InstrumentSpec, ProcessSpec
from schematika.catalog.registry import Catalog, DeviceCatalog
from schematika.catalog.cables import (
    CableInstance,
    CableInstanceRegistry,
    CableRegistry,
    CableSpec,
)

__all__ = [
    "CableInstance",
    "CableInstanceRegistry",
    "CableRegistry",
    "CableSpec",
    "Catalog",
    "CatalogDevice",
    "CatalogError",
    "DeviceCatalog",
    "InstrumentSpec",
    "ProcessSpec",
]
