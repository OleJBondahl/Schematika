"""Geometric primitives for electrical schematics.

This module provides the basic geometric building blocks used to construct
electrical symbols, including lines, circles, text, paths, polygons, and groups.
All primitives are immutable dataclasses that inherit from Element.
"""

from dataclasses import dataclass

from schematika.core.geometry import Element, Point, Style


@dataclass(frozen=True)
class Line(Element):
    """A straight line segment.

    Attributes:
        start (Point): Starting point.
        end (Point): Ending point.
        style (Style): Styling attributes.
    """

    start: Point
    end: Point
    style: Style = Style()


@dataclass(frozen=True)
class Circle(Element):
    """A circle.

    Attributes:
        center (Point): Center point of the circle.
        radius (float): Radius of the circle.
        style (Style): Styling attributes.
    """

    center: Point
    radius: float
    style: Style = Style()


@dataclass(frozen=True)
class Text(Element):
    """Text element.

    Attributes:
        content (str): The text string to display.
        position (Point): The position coordinates (anchor point).
        style (Style): Styling attributes.
        anchor (str): Text anchor alignment
            ('start', 'middle', 'end'). Default 'middle'.
        dominant_baseline (str): Vertical alignment
            ('auto', 'middle', 'central'). Default 'auto'.
        font_size (float): Font size in user units. Default 12.0.
        rotation (float): Rotation angle in degrees. Default 0.0.
    """

    content: str
    position: Point
    style: Style = Style()
    anchor: str = "middle"
    dominant_baseline: str = "auto"
    font_size: float = 12.0
    rotation: float = 0.0


@dataclass(frozen=True)
class Path(Element):
    """A generic SVG path.

    Attributes:
        d (str): The SVG path data string.
        style (Style): Styling attributes.
    """

    d: str
    style: Style = Style()


@dataclass(frozen=True)
class Group(Element):
    """A logical collection of elements.

    Attributes:
        elements (list[Element]): List of child elements.
        style (Style | None): Optional style to apply to the group (inherited).
    """

    elements: list[Element]
    style: Style | None = None


@dataclass(frozen=True)
class Polygon(Element):
    """A defined polygon from a list of points.

    Attributes:
        points (list[Point]): Vertices of the polygon.
        style (Style): Styling attributes.
    """

    points: list[Point]
    style: Style = Style()
