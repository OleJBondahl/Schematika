"""Schematika — programmatic schematic diagram library."""

# Re-export the electrical tier-1 surface at the top level.
# Project remains accessible via `from schematika.project import Project`.
from .electrical import *
from .electrical import __all__ as _electrical_all

__all__ = list(_electrical_all)
