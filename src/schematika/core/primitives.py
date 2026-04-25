"""Frozen geometric primitives: Line, Circle, Text, Path, Group, Polygon."""

from dataclasses import dataclass, field

from schematika.core.geometry import Element, Point, Style


@dataclass(frozen=True)
class Line(Element):
    """A straight line segment."""

    start: Point
    end: Point
    style: Style = field(default_factory=Style)


@dataclass(frozen=True)
class Circle(Element):
    """A circle."""

    center: Point
    radius: float
    style: Style = field(default_factory=Style)


@dataclass(frozen=True)
class Text(Element):
    """Text element."""

    content: str
    position: Point
    style: Style = field(default_factory=Style)
    anchor: str = "middle"
    dominant_baseline: str = "auto"
    font_size: float = 12.0
    rotation: float = 0.0


@dataclass(frozen=True)
class Path(Element):
    """A generic SVG path."""

    d: str
    style: Style = field(default_factory=Style)


@dataclass(frozen=True)
class Group(Element):
    """Logical group; *style*, if set, is inherited by children at render time."""

    elements: list[Element]
    style: Style | None = None


@dataclass(frozen=True)
class Polygon(Element):
    """A polygon from a list of vertex points."""

    points: list[Point]
    style: Style = field(default_factory=Style)
