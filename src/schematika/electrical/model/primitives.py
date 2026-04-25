"""Re-export shim: actual code lives in schematika.core.primitives."""

from schematika.core.geometry import Element
from schematika.core.primitives import (
    Circle,
    Group,
    Line,
    Path,
    Polygon,
    Text,
)

__all__ = [
    "Circle",
    "Element",
    "Group",
    "Line",
    "Path",
    "Polygon",
    "Text",
]
