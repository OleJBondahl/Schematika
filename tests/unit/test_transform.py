import math
import warnings

from schematika.electrical.model.core import Point, Port, Style, Symbol, Vector
from schematika.electrical.model.primitives import (
    Circle,
    Group,
    Line,
    Path,
    Polygon,
    Text,
)
from schematika.electrical.utils.transform import (
    _rotate_path_d,
    _translate_path_d,
    rotate,
    rotate_point,
    rotate_vector,
    translate,
)


class TestTransformUnit:
    def test_translate_point(self):
        p = Point(0, 0)
        p2 = translate(p, 10, 5)
        assert p2.x == 10
        assert p2.y == 5

    def test_translate_line(self):
        line = Line(Point(0, 0), Point(1, 1))
        line2 = translate(line, 2, 2)
        assert line2.start == Point(2, 2)
        assert line2.end == Point(3, 3)

    def test_translate_symbol_recursive(self):
        # Symbol containing a Line
        line = Line(Point(0, 0), Point(1, 1))
        port = Port("1", Point(0, 0), Vector(1, 0))
        sym = Symbol(elements=[line], ports={"1": port}, label="S1")

        sym2 = translate(sym, 10, 10)

        elem0 = sym2.elements[0]
        assert isinstance(elem0, Line)
        assert elem0.start == Point(10, 10)
        assert sym2.ports["1"].position == Point(10, 10)

    def test_rotate_point(self):
        # Rotate (1,0) 90 deg around (0,0) -> (0,1)
        p = Point(1, 0)
        p_rot = rotate_point(p, 90, Point(0, 0))
        assert math.isclose(p_rot.x, 0, abs_tol=1e-9)
        assert math.isclose(p_rot.y, 1, abs_tol=1e-9)

    def test_rotate_vector(self):
        v = Vector(1, 0)
        v_rot = rotate_vector(v, 90)
        assert math.isclose(v_rot.dx, 0, abs_tol=1e-9)
        assert math.isclose(v_rot.dy, 1, abs_tol=1e-9)

    def test_rotate_symbol_recursive(self):
        # Symbol with line from (0,0) to (1,0)
        line = Line(Point(0, 0), Point(1, 0))
        sym = Symbol(elements=[line], ports={}, label="S2")

        # Rotate 90 deg around (0,0)
        sym_rot = rotate(sym, 90, Point(0, 0))

        l_rot = sym_rot.elements[0]
        assert math.isclose(l_rot.start.x, 0, abs_tol=1e-9)
        assert math.isclose(l_rot.start.y, 0, abs_tol=1e-9)
        assert math.isclose(l_rot.end.x, 0, abs_tol=1e-9)
        assert math.isclose(l_rot.end.y, 1, abs_tol=1e-9)

    # ------------------------------------------------------------------ #
    # translate() — additional element types
    # ------------------------------------------------------------------ #

    def test_translate_port(self):
        p = Port("1", Point(0, 0), Vector(0, 1))
        p2 = translate(p, 5, 10)
        assert p2.position == Point(5, 10)
        assert p2.direction == Vector(0, 1)  # direction unchanged
        assert p2.id == "1"

    def test_translate_circle(self):
        c = Circle(center=Point(0, 0), radius=5)
        c2 = translate(c, 3, 4)
        assert c2.center == Point(3, 4)
        assert c2.radius == 5

    def test_translate_circle_preserves_style(self):
        s = Style(stroke="red", stroke_width=2.0)
        c = Circle(center=Point(1, 2), radius=3, style=s)
        c2 = translate(c, 10, 20)
        assert c2.center == Point(11, 22)
        assert c2.style == s

    def test_translate_text(self):
        t = Text(content="hello", position=Point(0, 0))
        t2 = translate(t, 1, 2)
        assert t2.position == Point(1, 2)
        assert t2.content == "hello"

    def test_translate_text_preserves_attributes(self):
        t = Text(
            content="label",
            position=Point(5, 5),
            anchor="start",
            font_size=14.0,
            rotation=45.0,
        )
        t2 = translate(t, 10, 20)
        assert t2.position == Point(15, 25)
        assert t2.anchor == "start"
        assert t2.font_size == 14.0
        assert t2.rotation == 45.0
        assert t2.content == "label"

    def test_translate_group(self):
        g = Group(
            elements=[
                Line(Point(0, 0), Point(1, 1)),
                Circle(center=Point(0, 0), radius=1),
            ]
        )
        g2 = translate(g, 10, 10)
        assert isinstance(g2, Group)
        g2_elem0 = g2.elements[0]
        assert isinstance(g2_elem0, Line)
        assert g2_elem0.start == Point(10, 10)
        assert g2_elem0.end == Point(11, 11)
        g2_elem1 = g2.elements[1]
        assert isinstance(g2_elem1, Circle)
        assert g2_elem1.center == Point(10, 10)

    def test_translate_group_nested(self):
        """Nested groups are translated recursively."""
        inner = Group(elements=[Line(Point(0, 0), Point(1, 0))])
        outer = Group(elements=[inner])
        outer2 = translate(outer, 5, 5)
        inner_translated = outer2.elements[0]
        assert isinstance(inner_translated, Group)
        inner_translated_elem0 = inner_translated.elements[0]
        assert isinstance(inner_translated_elem0, Line)
        assert inner_translated_elem0.start == Point(5, 5)
        assert inner_translated_elem0.end == Point(6, 5)

    def test_translate_polygon(self):
        poly = Polygon(points=[Point(0, 0), Point(1, 0), Point(0.5, 1)])
        poly2 = translate(poly, 5, 5)
        assert poly2.points[0] == Point(5, 5)
        assert poly2.points[1] == Point(6, 5)
        assert poly2.points[2] == Point(5.5, 6)

    def test_translate_path(self):
        p = Path(d="M 0 0 L 10 10")
        p2 = translate(p, 5, 5)
        # After translation: M 5 5 L 15 15
        assert "5.0" in p2.d
        assert "15.0" in p2.d

    def test_translate_path_preserves_style(self):
        s = Style(stroke="blue", fill="red")
        p = Path(d="M 0 0 L 10 0", style=s)
        p2 = translate(p, 1, 1)
        assert p2.style == s

    def test_translate_unhandled_type_warns(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = translate(42, 1, 1)  # type: ignore[invalid-argument-type]
            assert result == 42
            assert len(w) == 1
            assert "no handler" in str(w[0].message).lower()
            assert issubclass(w[0].category, RuntimeWarning)

    def test_translate_zero_offset(self):
        """Translating by (0,0) returns equivalent objects."""
        p = Point(3, 7)
        assert translate(p, 0, 0) == Point(3, 7)

        line = Line(Point(1, 2), Point(3, 4))
        line2 = translate(line, 0, 0)
        assert line2.start == Point(1, 2)
        assert line2.end == Point(3, 4)

    def test_translate_negative_offsets(self):
        p = Point(10, 20)
        p2 = translate(p, -5, -10)
        assert p2 == Point(5, 10)

    # ------------------------------------------------------------------ #
    # _translate_path_d() — direct tests
    # ------------------------------------------------------------------ #

    def test_translate_path_d_M_L_T(self):
        d = "M 0 0 L 10 20 T 5 5"
        result = _translate_path_d(d, 3, 4)
        # Expected: M 3.0 4.0 L 13.0 24.0 T 8.0 9.0
        assert "3.0" in result
        assert "4.0" in result
        assert "13.0" in result
        assert "24.0" in result
        assert "8.0" in result
        assert "9.0" in result

    def test_translate_path_d_H(self):
        d = "M 0 0 H 10"
        result = _translate_path_d(d, 5, 0)
        assert "15.0" in result

    def test_translate_path_d_V(self):
        d = "M 0 0 V 10"
        result = _translate_path_d(d, 0, 5)
        assert "15.0" in result

    def test_translate_path_d_C(self):
        d = "M 0 0 C 1 2 3 4 5 6"
        result = _translate_path_d(d, 10, 10)
        # All pairs shifted by (10, 10):
        # (1+10, 2+10) = (11, 12), (3+10, 4+10) = (13, 14), (5+10, 6+10) = (15, 16)
        assert "11.0" in result
        assert "12.0" in result
        assert "13.0" in result
        assert "14.0" in result
        assert "15.0" in result
        assert "16.0" in result

    def test_translate_path_d_S(self):
        d = "M 0 0 S 1 2 3 4"
        result = _translate_path_d(d, 5, 5)
        # (1+5, 2+5) = (6, 7), (3+5, 4+5) = (8, 9)
        assert "6.0" in result
        assert "7.0" in result
        assert "8.0" in result
        assert "9.0" in result

    def test_translate_path_d_Q(self):
        d = "M 0 0 Q 2 4 6 8"
        result = _translate_path_d(d, 1, 1)
        # (2+1, 4+1) = (3, 5), (6+1, 8+1) = (7, 9)
        assert "3.0" in result
        assert "5.0" in result
        assert "7.0" in result
        assert "9.0" in result

    def test_translate_path_d_Z(self):
        d = "M 0 0 L 10 0 L 10 10 Z"
        result = _translate_path_d(d, 5, 5)
        assert "Z" in result
        assert "5.0" in result
        assert "15.0" in result

    def test_translate_path_d_relative_commands_unchanged(self):
        """Relative (lowercase) commands should pass through unchanged."""
        d = "M 0 0 l 10 10"
        result = _translate_path_d(d, 5, 5)
        # M is translated, but l remains relative
        assert "5.0" in result
        # The relative operands should pass through as-is
        assert "10" in result

    def test_translate_path_d_empty(self):
        d = ""
        result = _translate_path_d(d, 5, 5)
        assert result.strip() == ""

    def test_translate_path_d_multiple_M(self):
        d = "M 0 0 L 1 1 M 10 10 L 11 11"
        result = _translate_path_d(d, 2, 3)
        # First M: (0+2, 0+3) = (2, 3)
        # First L: (1+2, 1+3) = (3, 4)
        # Second M: (10+2, 10+3) = (12, 13)
        # Second L: (11+2, 11+3) = (13, 14)
        assert "12.0" in result
        assert "13.0" in result

    # ------------------------------------------------------------------ #
    # rotate() — additional element types
    # ------------------------------------------------------------------ #

    def test_rotate_port(self):
        p = Port("1", Point(1, 0), Vector(1, 0))
        p2 = rotate(p, 90, Point(0, 0))
        assert math.isclose(p2.position.x, 0, abs_tol=1e-9)
        assert math.isclose(p2.position.y, 1, abs_tol=1e-9)
        assert math.isclose(p2.direction.dx, 0, abs_tol=1e-9)
        assert math.isclose(p2.direction.dy, 1, abs_tol=1e-9)
        assert p2.id == "1"

    def test_rotate_port_180(self):
        p = Port("A1", Point(5, 0), Vector(0, 1))
        p2 = rotate(p, 180, Point(0, 0))
        assert math.isclose(p2.position.x, -5, abs_tol=1e-9)
        assert math.isclose(p2.position.y, 0, abs_tol=1e-9)
        assert math.isclose(p2.direction.dx, 0, abs_tol=1e-9)
        assert math.isclose(p2.direction.dy, -1, abs_tol=1e-9)

    def test_rotate_group(self):
        g = Group(elements=[Line(Point(1, 0), Point(2, 0))])
        g2 = rotate(g, 90, Point(0, 0))
        assert isinstance(g2, Group)
        assert math.isclose(g2.elements[0].start.x, 0, abs_tol=1e-9)
        assert math.isclose(g2.elements[0].start.y, 1, abs_tol=1e-9)
        assert math.isclose(g2.elements[0].end.x, 0, abs_tol=1e-9)
        assert math.isclose(g2.elements[0].end.y, 2, abs_tol=1e-9)

    def test_rotate_group_nested(self):
        """Nested groups are rotated recursively."""
        inner = Group(elements=[Line(Point(1, 0), Point(2, 0))])
        outer = Group(elements=[inner])
        outer2 = rotate(outer, 90, Point(0, 0))
        inner_rotated = outer2.elements[0]
        assert isinstance(inner_rotated, Group)
        assert math.isclose(inner_rotated.elements[0].start.y, 1, abs_tol=1e-9)
        assert math.isclose(inner_rotated.elements[0].end.y, 2, abs_tol=1e-9)

    def test_rotate_polygon(self):
        poly = Polygon(points=[Point(1, 0), Point(0, 0), Point(0, 1)])
        poly2 = rotate(poly, 90, Point(0, 0))
        assert math.isclose(poly2.points[0].x, 0, abs_tol=1e-9)
        assert math.isclose(poly2.points[0].y, 1, abs_tol=1e-9)
        assert math.isclose(poly2.points[1].x, 0, abs_tol=1e-9)
        assert math.isclose(poly2.points[1].y, 0, abs_tol=1e-9)
        assert math.isclose(poly2.points[2].x, -1, abs_tol=1e-9)
        assert math.isclose(poly2.points[2].y, 0, abs_tol=1e-9)

    def test_rotate_circle(self):
        c = Circle(center=Point(1, 0), radius=5)
        c2 = rotate(c, 90, Point(0, 0))
        assert math.isclose(c2.center.x, 0, abs_tol=1e-9)
        assert math.isclose(c2.center.y, 1, abs_tol=1e-9)
        assert c2.radius == 5

    def test_rotate_circle_preserves_style(self):
        s = Style(stroke="green", stroke_width=3.0)
        c = Circle(center=Point(5, 0), radius=2, style=s)
        c2 = rotate(c, 90, Point(0, 0))
        assert c2.style == s

    def test_rotate_text_180_flips_start_to_end(self):
        t = Text(content="test", position=Point(1, 0), anchor="start")
        t2 = rotate(t, 180, Point(0, 0))
        assert t2.anchor == "end"
        assert math.isclose(t2.position.x, -1, abs_tol=1e-9)
        assert math.isclose(t2.position.y, 0, abs_tol=1e-9)

    def test_rotate_text_180_flips_end_to_start(self):
        t = Text(content="test", position=Point(1, 0), anchor="end")
        t2 = rotate(t, 180, Point(0, 0))
        assert t2.anchor == "start"

    def test_rotate_text_180_middle_unchanged(self):
        t = Text(content="test", position=Point(1, 0), anchor="middle")
        t2 = rotate(t, 180, Point(0, 0))
        assert t2.anchor == "middle"

    def test_rotate_text_90_no_anchor_change(self):
        t = Text(content="test", position=Point(1, 0), anchor="start")
        t2 = rotate(t, 90, Point(0, 0))
        assert t2.anchor == "start"

    def test_rotate_text_270_no_anchor_change(self):
        t = Text(content="test", position=Point(1, 0), anchor="end")
        t2 = rotate(t, 270, Point(0, 0))
        assert t2.anchor == "end"

    def test_rotate_text_540_flips_anchor(self):
        """540 degrees is equivalent to 180 degrees, so anchor should flip."""
        t = Text(content="test", position=Point(1, 0), anchor="start")
        t2 = rotate(t, 540, Point(0, 0))
        assert t2.anchor == "end"

    def test_rotate_text_preserves_content_and_style(self):
        s = Style(stroke="black", font_family="Arial")
        t = Text(
            content="label",
            position=Point(5, 0),
            style=s,
            font_size=10.0,
            anchor="start",
        )
        t2 = rotate(t, 90, Point(0, 0))
        assert t2.content == "label"
        assert t2.style == s
        assert t2.font_size == 10.0

    def test_rotate_path(self):
        p = Path(d="M 1 0 L 2 0")
        p2 = rotate(p, 90, Point(0, 0))
        # After 90 deg rotation: (1,0) -> (0,1), (2,0) -> (0,2)
        assert isinstance(p2, Path)
        # The path d string should contain the rotated coordinates

    def test_rotate_path_preserves_style(self):
        s = Style(stroke="purple")
        p = Path(d="M 0 0 L 1 0", style=s)
        p2 = rotate(p, 45, Point(0, 0))
        assert p2.style == s

    def test_rotate_unhandled_type_warns(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = rotate(42, 90)
            assert result == 42
            assert len(w) == 1
            assert "no handler" in str(w[0].message).lower()
            assert issubclass(w[0].category, RuntimeWarning)

    def test_rotate_zero_degrees_identity(self):
        """Rotating by 0 degrees should return equivalent objects."""
        p = Point(3, 7)
        p2 = rotate(p, 0, Point(0, 0))
        assert math.isclose(p2.x, 3, abs_tol=1e-9)
        assert math.isclose(p2.y, 7, abs_tol=1e-9)

    def test_rotate_360_degrees_identity(self):
        """Rotating by 360 degrees should return equivalent objects."""
        c = Circle(center=Point(5, 10), radius=3)
        c2 = rotate(c, 360, Point(0, 0))
        assert math.isclose(c2.center.x, 5, abs_tol=1e-9)
        assert math.isclose(c2.center.y, 10, abs_tol=1e-9)

    def test_rotate_around_non_origin_center(self):
        """Rotation around a non-origin center point."""
        p = Point(10, 5)
        p2 = rotate(p, 90, Point(5, 5))
        # (10,5) relative to (5,5) is (5,0), rotated 90 -> (0,5), back to (5,10)
        assert math.isclose(p2.x, 5, abs_tol=1e-9)
        assert math.isclose(p2.y, 10, abs_tol=1e-9)

    # ------------------------------------------------------------------ #
    # _rotate_path_d() — direct tests
    # ------------------------------------------------------------------ #

    def test_rotate_path_d_ML(self):
        d = "M 1 0 L 2 0"
        result = _rotate_path_d(d, 90, Point(0, 0))
        # (1,0) rotated 90 -> (0,1), (2,0) rotated 90 -> (0,2)
        # Parse the result to check values
        parts = result.split()
        # Should be: M <~0> <~1> L <~0> <~2>
        assert "M" in parts
        assert "L" in parts

    def test_rotate_path_d_ML_values(self):
        """Verify actual numeric values after 90 degree rotation."""
        d = "M 1 0 L 2 0"
        result = _rotate_path_d(d, 90, Point(0, 0))
        # Extract numeric values (including scientific notation) from result
        import re

        numbers = [
            float(x)
            for x in re.findall(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", result)
        ]
        # (1,0) -> (0,1) and (2,0) -> (0,2) approximately
        # Numbers should be close to [0, 1, 0, 2]
        assert math.isclose(numbers[0], 0, abs_tol=1e-9)
        assert math.isclose(numbers[1], 1, abs_tol=1e-9)
        assert math.isclose(numbers[2], 0, abs_tol=1e-9)
        assert math.isclose(numbers[3], 2, abs_tol=1e-9)

    def test_rotate_path_d_H_converts_to_L(self):
        d = "M 0 0 H 10"
        result = _rotate_path_d(d, 90, Point(0, 0))
        assert "L" in result
        # H 10 means move horizontally to x=10, y stays at 0
        # After 90 deg rotation: (10, 0) -> (0, 10)
        assert "H" not in result

    def test_rotate_path_d_V_converts_to_L(self):
        d = "M 0 0 V 10"
        result = _rotate_path_d(d, 90, Point(0, 0))
        assert "L" in result
        # V 10 means move vertically to y=10, x stays at 0
        # After 90 deg rotation: (0, 10) -> (-10, 0)
        assert "V" not in result

    def test_rotate_path_d_C(self):
        d = "M 0 0 C 1 0 2 0 3 0"
        result = _rotate_path_d(d, 90, Point(0, 0))
        assert "C" in result
        # All three pairs rotated 90 degrees
        # (1,0)->(0,1), (2,0)->(0,2), (3,0)->(0,3)

    def test_rotate_path_d_S(self):
        d = "M 0 0 S 1 0 2 0"
        result = _rotate_path_d(d, 90, Point(0, 0))
        assert "S" in result

    def test_rotate_path_d_Q(self):
        d = "M 0 0 Q 1 0 2 0"
        result = _rotate_path_d(d, 90, Point(0, 0))
        assert "Q" in result

    def test_rotate_path_d_T(self):
        d = "M 0 0 T 1 0"
        result = _rotate_path_d(d, 90, Point(0, 0))
        assert "T" in result

    def test_rotate_path_d_Z(self):
        d = "M 0 0 L 1 0 Z"
        result = _rotate_path_d(d, 90, Point(0, 0))
        assert "Z" in result

    def test_rotate_path_d_relative_unchanged(self):
        """Relative (lowercase) commands pass through unchanged."""
        d = "M 0 0 l 10 10"
        result = _rotate_path_d(d, 90, Point(0, 0))
        # M is rotated, but 'l' remains relative and tokens pass through
        assert "l" in result

    def test_rotate_path_d_180_degrees(self):
        """180 degree rotation: (1,0) -> (-1,0)."""
        d = "M 1 0"
        result = _rotate_path_d(d, 180, Point(0, 0))
        import re

        numbers = [
            float(x)
            for x in re.findall(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", result)
        ]
        assert math.isclose(numbers[0], -1, abs_tol=1e-9)
        assert math.isclose(numbers[1], 0, abs_tol=1e-9)

    def test_rotate_path_d_around_non_origin(self):
        """Rotation around a non-origin center."""
        d = "M 10 5"
        result = _rotate_path_d(d, 90, Point(5, 5))
        # (10,5) relative to (5,5) is (5,0), rotated 90 -> (0,5), back to (5,10)
        import re

        numbers = [float(x) for x in re.findall(r"[-+]?(?:\d+\.?\d*|\.\d+)", result)]
        assert math.isclose(numbers[0], 5, abs_tol=1e-6)
        assert math.isclose(numbers[1], 10, abs_tol=1e-6)

    def test_rotate_path_d_empty(self):
        d = ""
        result = _rotate_path_d(d, 90, Point(0, 0))
        assert result.strip() == ""

    def test_rotate_path_d_complex_path(self):
        """A path with multiple command types."""
        d = "M 0 0 L 5 0 H 10 V 10 C 10 5 5 10 0 10 Z"
        result = _rotate_path_d(d, 90, Point(0, 0))
        assert "M" in result
        assert "L" in result
        assert "C" in result
        assert "Z" in result
        # H and V should be converted to L
        assert result.count("L") >= 3  # original L + converted H + converted V

    # ------------------------------------------------------------------ #
    # rotate() — Symbol with label special case
    # ------------------------------------------------------------------ #

    def test_rotate_symbol_with_ports(self):
        """Symbol rotation also rotates all ports."""
        port = Port("1", Point(1, 0), Vector(1, 0))
        line = Line(Point(0, 0), Point(1, 0))
        sym = Symbol(elements=[line], ports={"1": port}, label="K1")
        sym2 = rotate(sym, 90, Point(0, 0))
        p = sym2.ports["1"]
        assert math.isclose(p.position.x, 0, abs_tol=1e-9)
        assert math.isclose(p.position.y, 1, abs_tol=1e-9)
        assert math.isclose(p.direction.dx, 0, abs_tol=1e-9)
        assert math.isclose(p.direction.dy, 1, abs_tol=1e-9)

    # ------------------------------------------------------------------ #
    # Translate Symbol with multiple element types
    # ------------------------------------------------------------------ #

    def test_translate_symbol_with_diverse_elements(self):
        """Symbol containing different element types translates all of them."""
        line = Line(Point(0, 0), Point(1, 0))
        circle = Circle(center=Point(0.5, 0.5), radius=0.5)
        text = Text(content="X", position=Point(0, 1))
        port = Port("1", Point(0, 0), Vector(0, -1))

        sym = Symbol(elements=[line, circle, text], ports={"1": port}, label="Q1")
        sym2 = translate(sym, 100, 200)

        sym2_elem0 = sym2.elements[0]
        assert isinstance(sym2_elem0, Line)
        assert sym2_elem0.start == Point(100, 200)
        assert sym2_elem0.end == Point(101, 200)
        sym2_elem1 = sym2.elements[1]
        assert isinstance(sym2_elem1, Circle)
        assert sym2_elem1.center == Point(100.5, 200.5)
        sym2_elem2 = sym2.elements[2]
        assert isinstance(sym2_elem2, Text)
        assert sym2_elem2.position == Point(100, 201)
        assert sym2.ports["1"].position == Point(100, 200)

    # ------------------------------------------------------------------ #
    # Edge cases: incomplete pair fallbacks in _translate_path_d
    # ------------------------------------------------------------------ #

    def test_translate_path_d_M_incomplete_pair(self):
        """M command with only one number before the next command letter."""
        # "M 5 L 1 2" — M has only one number (5) before L appears
        d = "M 5 L 1 2"
        result = _translate_path_d(d, 10, 10)
        # The lone "5" for M should be passed through as-is (else branch)
        assert "5" in result
        # The L pair should be translated: (1+10, 2+10) = (11, 12)
        assert "11.0" in result
        assert "12.0" in result

    def test_translate_path_d_C_incomplete_pair(self):
        """C command with fewer than 3 pairs (interrupted by next command)."""
        # "C 1 2 3 L 0 0" — C expects 3 pairs but gets only 1 full pair + single "3"
        d = "M 0 0 C 1 2 3 L 0 0"
        result = _translate_path_d(d, 10, 10)
        # First pair (1,2) translated to (11, 12)
        # Then "3" is followed by "L" (alpha), so falls into the else branch
        assert "11.0" in result
        assert "12.0" in result

    def test_translate_path_d_S_incomplete_pair(self):
        """S command with fewer than 2 complete pairs."""
        d = "M 0 0 S 1 2 3 Z"
        result = _translate_path_d(d, 5, 5)
        # First pair (1,2) -> (6, 7)
        # "3" followed by "Z" -> passed through as-is
        assert "6.0" in result
        assert "7.0" in result

    # ------------------------------------------------------------------ #
    # Edge cases: incomplete pair fallbacks in _rotate_path_d
    # ------------------------------------------------------------------ #

    def test_rotate_path_d_M_incomplete_pair(self):
        """M command with only one number before the next command letter."""
        d = "M 5 L 1 0"
        result = _rotate_path_d(d, 90, Point(0, 0))
        # The lone "5" for M should be passed through as-is
        assert "5" in result
        # L pair (1,0) rotated 90 -> (0,1) approximately
        assert "L" in result

    def test_rotate_path_d_C_incomplete_pair(self):
        """C command interrupted by a letter before all 3 pairs are parsed."""
        d = "M 0 0 C 1 0 3 L 5 0"
        result = _rotate_path_d(d, 90, Point(0, 0))
        # The C gets 1 full pair (1,0) and then "3" is followed by "L"
        # "3" is passed through as-is from the else branch
        assert "L" in result

    # ------------------------------------------------------------------ #
    # Edge case: Symbol with label Text element — forced position on rotate
    # ------------------------------------------------------------------ #

    def test_translate_path_d_Z_followed_by_number(self):
        """Z command followed by a spurious number token — the number is skipped."""
        d = "M 0 0 L 5 5 Z 99"
        result = _translate_path_d(d, 1, 1)
        # The "99" after Z should be consumed/skipped
        assert "Z" in result
        assert "99" not in result

    def test_rotate_path_d_Z_followed_by_number(self):
        """Z command followed by a spurious number token — the number is skipped."""
        d = "M 0 0 L 5 0 Z 99"
        result = _rotate_path_d(d, 90, Point(0, 0))
        assert "Z" in result
        # The "99" should have been consumed by the Z handler and not appear
        # as a separate token in the output. Check that result ends with Z.
        assert result.strip().endswith("Z")

    def test_rotate_symbol_label_text_forced_position(self):
        """When a Symbol's label matches a Text element's content,
        the text is forced to a fixed position during rotation."""
        from schematika.electrical.model.constants import TEXT_OFFSET_X

        label_text = Text(content="K1", position=Point(5, 0), anchor="start")
        line = Line(Point(0, 0), Point(0, 10))
        sym = Symbol(elements=[label_text, line], ports={}, label="K1")

        center = Point(10, 20)
        sym2 = rotate(sym, 90, center)

        forced = sym2.elements[0]
        assert isinstance(forced, Text)
        assert forced.position == Point(center.x + TEXT_OFFSET_X, center.y)
        assert forced.anchor == "end"

    # ------------------------------------------------------------------ #
    # Wave-3 hardening — exact-value rotation_vector at diverse angles
    # Targets mutants 304 (cos_a + sin_a swap), 306 (v.dx / sin_a),
    # 308 (v.dy / cos_a). These mutations are numerically invisible at
    # angles like 180° but diverge sharply at 30° / 45° / 90° / 270°.
    # ------------------------------------------------------------------ #

    def test_rotate_vector_30_deg(self):
        v = Vector(1, 0)
        r = rotate_vector(v, 30)
        # x -> cos30, y -> sin30
        assert math.isclose(r.dx, math.cos(math.radians(30)), abs_tol=1e-12)
        assert math.isclose(r.dy, math.sin(math.radians(30)), abs_tol=1e-12)

    def test_rotate_vector_45_deg_vector_1_0(self):
        r = rotate_vector(Vector(1, 0), 45)
        assert math.isclose(r.dx, math.sqrt(2) / 2, abs_tol=1e-12)
        assert math.isclose(r.dy, math.sqrt(2) / 2, abs_tol=1e-12)

    def test_rotate_vector_45_deg_vector_0_1(self):
        """At 45° and v=(0,1), the result is (-sqrt(2)/2, sqrt(2)/2).

        This discriminates mutant 304 (cos+sin for dx): with the mutation
        the x-component would be +sqrt(2)/2.
        """
        r = rotate_vector(Vector(0, 1), 45)
        assert math.isclose(r.dx, -math.sqrt(2) / 2, abs_tol=1e-12)
        assert math.isclose(r.dy, math.sqrt(2) / 2, abs_tol=1e-12)

    def test_rotate_vector_90_deg_1_0_is_0_1(self):
        r = rotate_vector(Vector(1, 0), 90)
        assert math.isclose(r.dx, 0, abs_tol=1e-12)
        assert math.isclose(r.dy, 1, abs_tol=1e-12)

    def test_rotate_vector_90_deg_0_1_is_neg1_0(self):
        """Kills mutant 304: with cos+sin the dx would be 1 instead of -1."""
        r = rotate_vector(Vector(0, 1), 90)
        assert math.isclose(r.dx, -1, abs_tol=1e-12)
        assert math.isclose(r.dy, 0, abs_tol=1e-12)

    def test_rotate_vector_270_deg_1_0_is_0_neg1(self):
        r = rotate_vector(Vector(1, 0), 270)
        assert math.isclose(r.dx, 0, abs_tol=1e-12)
        assert math.isclose(r.dy, -1, abs_tol=1e-12)

    def test_rotate_vector_30_deg_mixed(self):
        """v=(3, 4) at 30°: kills division-for-multiplication mutants 306/308.

        Expected: dx = 3 cos30 - 4 sin30,  dy = 3 sin30 + 4 cos30.
        If sin_a or cos_a were used as divisors, the magnitude would explode.
        """
        r = rotate_vector(Vector(3, 4), 30)
        c, s = math.cos(math.radians(30)), math.sin(math.radians(30))
        assert math.isclose(r.dx, 3 * c - 4 * s, abs_tol=1e-12)
        assert math.isclose(r.dy, 3 * s + 4 * c, abs_tol=1e-12)

    def test_rotate_vector_preserves_magnitude(self):
        """A rotated vector has the same length (Euclidean) as the original.

        Kills mutants 306 & 308 where `v.dx / sin_a` or `v.dy / cos_a`
        would produce unbounded magnitudes near sin=0 / cos=0, and
        wrong magnitudes everywhere else.
        """
        for angle in (15, 45, 60, 135, 222.5, 321):
            v = Vector(3, 4)
            r = rotate_vector(v, angle)
            orig_mag = math.hypot(v.dx, v.dy)
            new_mag = math.hypot(r.dx, r.dy)
            assert math.isclose(orig_mag, new_mag, abs_tol=1e-9), (
                f"magnitude drift at {angle}°: {orig_mag} vs {new_mag}"
            )

    # ------------------------------------------------------------------ #
    # Translate default handler warning — mutants 281, 282
    # ------------------------------------------------------------------ #

    def test_translate_path_d_ml_trailing_lone_number(self):
        """M/L/T followed by a lone trailing number (no pair partner).

        Kills mutant 326 in _translate_path_d: the `i + 1 < len(tokens)`
        boundary-check is what prevents IndexError on a final odd number.
        Mutant 326 replaces it with `i - 1 < len(tokens)` (always True),
        so tokens[i+1] would then raise IndexError.
        """
        # "M 1 2 L 3" — the final "3" is a lone number with no partner.
        # With the boundary intact, it should fall through to the else branch.
        result = _translate_path_d("M 1 2 L 3", 10, 20)
        # No IndexError — the lone "3" is passed through without translation.
        assert "3" in result

    def test_rotate_path_d_ml_trailing_lone_number(self):
        """Same boundary-check in _rotate_path_d (mutant 326-family in rotate)."""
        result = _rotate_path_d("M 1 2 L 3", 90, Point(0, 0))
        assert "3" in result

    def test_translate_unhandled_warning_message_contains_type(self):
        """Mutant 281 replaces the formatted message with a literal marker."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            translate(object(), 0, 0)  # type: ignore[invalid-argument-type]
            assert len(w) == 1
            msg = str(w[0].message)
            assert "translate()" in msg
            assert "object" in msg
            assert "returning unchanged" in msg

    def test_rotate_symbol_non_label_text_not_forced(self):
        """Text elements that don't match the Symbol label are rotated normally."""
        label_text = Text(content="K1", position=Point(5, 0), anchor="start")
        other_text = Text(content="other", position=Point(1, 0), anchor="middle")
        sym = Symbol(elements=[label_text, other_text], ports={}, label="K1")

        center = Point(0, 0)
        sym2 = rotate(sym, 90, center)

        # "other" text should be rotated normally, not forced
        other_rotated = sym2.elements[1]
        assert isinstance(other_rotated, Text)
        # (1,0) rotated 90 -> (0,1)
        assert math.isclose(other_rotated.position.x, 0, abs_tol=1e-9)
        assert math.isclose(other_rotated.position.y, 1, abs_tol=1e-9)
        assert other_rotated.anchor == "middle"
