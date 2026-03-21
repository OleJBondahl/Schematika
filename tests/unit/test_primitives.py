from schematika.electrical.model.core import Point, Style
from schematika.electrical.model.primitives import (
    Circle,
    Group,
    Line,
    Path,
    Polygon,
    Text,
)


class TestPrimitivesUnit:
    def test_line(self):
        p1 = Point(0, 0)
        p2 = Point(10, 10)
        line = Line(start=p1, end=p2)
        assert line.start == p1
        assert line.end == p2
        assert isinstance(line.style, Style)

    def test_circle(self):
        center = Point(5, 5)
        circle = Circle(center=center, radius=3.0)
        assert circle.center == center
        assert circle.radius == 3.0

    def test_text(self):
        pos = Point(0, 0)
        txt = Text(content="Hello", position=pos)
        assert txt.content == "Hello"
        assert txt.position == pos
        assert txt.anchor == "middle"  # default
        assert txt.font_size == 12.0  # default

    def test_path(self):
        d = "M 0 0 L 10 10"
        path = Path(d=d)
        assert path.d == d

    def test_polygon(self):
        points = [Point(0, 0), Point(10, 0), Point(5, 10)]
        poly = Polygon(points=points)
        assert poly.points == points

    def test_group(self):
        line = Line(Point(0, 0), Point(1, 1))
        c = Circle(Point(2, 2), 5)
        g = Group(elements=[line, c])
        assert len(g.elements) == 2
        assert g.elements[0] == line
