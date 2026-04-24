"""Bounding box utility for core geometric elements and symbols.

This module provides a typed BoundingBox dataclass and a
``compute_bounding_box`` function that walks element trees recursively,
mirroring the logic in ``core.renderer.calculate_bounds`` but returning
a structured result usable by both the electrical and P&ID modules.
"""

from dataclasses import dataclass

from schematika.core.geometry import Element, Point
from schematika.core.primitives import Circle, Group, Line, Path, Polygon, Text
from schematika.core.symbol import Symbol
from schematika.core.transform import tokenize_path_d


@dataclass(frozen=True)
class BoundingBox:
    """Axis-aligned bounding box in diagram coordinates (mm).

    Attributes:
        min_x: Left edge.
        max_x: Right edge.
        min_y: Top edge.
        max_y: Bottom edge.
    """

    min_x: float
    max_x: float
    min_y: float
    max_y: float

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        return self.max_y - self.min_y

    @property
    def center(self) -> Point:
        return Point((self.min_x + self.max_x) / 2, (self.min_y + self.max_y) / 2)


def _collect_points(elem: Element, points: list[tuple[float, float]]) -> None:  # noqa: C901
    """Recursively extract representative points from an element tree."""
    if isinstance(elem, Line):
        points.append((elem.start.x, elem.start.y))
        points.append((elem.end.x, elem.end.y))

    elif isinstance(elem, Circle):
        r = elem.radius
        points.append((elem.center.x - r, elem.center.y - r))
        points.append((elem.center.x + r, elem.center.y + r))

    elif isinstance(elem, Text):
        # Text extent is not computed; use the anchor position only.
        points.append((elem.position.x, elem.position.y))

    elif isinstance(elem, Polygon):
        for p in elem.points:
            points.append((p.x, p.y))

    elif isinstance(elem, Path):
        # Parse absolute coordinates from the d string (approximate).
        _collect_path_points(elem.d, points)

    elif isinstance(elem, (Group, Symbol)):
        for child in elem.elements:
            _collect_points(child, points)


def _collect_path_points(d: str, points: list[tuple[float, float]]) -> None:
    """Extract x,y pairs from absolute SVG path commands (approximate)."""
    tokens = tokenize_path_d(d)
    i = 0
    cmd = ""
    while i < len(tokens):
        token = tokens[i]
        if token.isalpha():
            cmd = token
            i += 1
            continue

        # Only process absolute commands (uppercase) that carry x,y pairs.
        if cmd in ("M", "L", "T", "C", "S", "Q"):
            if i + 1 < len(tokens) and not tokens[i + 1].isalpha():
                try:
                    points.append((float(token), float(tokens[i + 1])))
                except ValueError:
                    pass
                i += 2
            else:
                i += 1
        elif cmd == "H":
            i += 1  # single x — skip; no y available
        elif cmd == "V":
            i += 1  # single y — skip; no x available
        else:
            i += 1


def compute_bounding_box(item: Symbol | list[Element]) -> BoundingBox:
    """Compute the bounding box of a symbol or a list of elements.

    Walks the element tree recursively:
    - ``Line``: start and end points
    - ``Circle``: center ± radius
    - ``Text``: position point only (text extent not computed)
    - ``Path``: absolute coordinate pairs parsed from the ``d`` attribute
    - ``Polygon``: all vertex points
    - ``Group`` / ``Symbol``: recurse into children

    Args:
        item: A ``Symbol`` or a flat list of ``Element`` objects.

    Returns:
        A ``BoundingBox`` covering all extracted points.  Falls back to
        ``BoundingBox(0, 0, 0, 0)`` when no points can be extracted.
    """
    raw_points: list[tuple[float, float]] = []

    if isinstance(item, Symbol):
        _collect_points(item, raw_points)
    else:
        for elem in item:
            _collect_points(elem, raw_points)

    if not raw_points:
        return BoundingBox(min_x=0.0, max_x=0.0, min_y=0.0, max_y=0.0)

    xs = [p[0] for p in raw_points]
    ys = [p[1] for p in raw_points]
    return BoundingBox(
        min_x=min(xs),
        max_x=max(xs),
        min_y=min(ys),
        max_y=max(ys),
    )
