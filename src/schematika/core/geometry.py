"""Cross-domain geometric primitives: Vector, Point, Style, Element."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Vector:
    """2D vector (direction + magnitude)."""

    dx: float
    dy: float

    def __add__(self, other: "Vector") -> "Vector":
        """Add two vectors."""
        if not isinstance(other, Vector):
            return NotImplemented
        return Vector(self.dx + other.dx, self.dy + other.dy)

    def __mul__(self, scalar: float) -> "Vector":
        """Scale the vector by a scalar."""
        return Vector(self.dx * scalar, self.dy * scalar)


@dataclass(frozen=True)
class Point:
    """2D point."""

    x: float
    y: float

    def __add__(self, other: "Point | Vector") -> "Point":
        """Point + Vector -> Point; raises TypeError for Point + Point."""
        if isinstance(other, Vector):
            return Point(self.x + other.dx, self.y + other.dy)
        msg = f"Can only add Vector to Point, got {type(other)}"
        raise TypeError(msg)

    def __sub__(self, other: "Point") -> "Vector":
        """Point - Point -> Vector pointing from *other* to self."""
        if isinstance(other, Point):
            return Vector(self.x - other.x, self.y - other.y)
        msg = f"Can only subtract Point from Point, got {type(other)}"
        raise TypeError(msg)


@dataclass(frozen=True)
class Style:
    """SVG style attributes."""

    stroke: str = "black"
    stroke_width: float = 1.0
    fill: str = "none"
    stroke_dasharray: str | None = None
    opacity: float = 1.0
    font_family: str | None = None


@dataclass(frozen=True)
class Element:
    """Base class for all geometric primitives and symbols."""
