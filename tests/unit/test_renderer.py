from schematika.electrical.model.core import Point, Style, Symbol
from schematika.electrical.model.primitives import (
    Circle,
    Group,
    Line,
    Path,
    Polygon,
    Text,
)
from schematika.electrical.utils.renderer import (
    calculate_bounds,
    render_to_svg,
    save_svg,
    to_xml_element,
)


class TestRendererUnit:
    def test_primitives_xml_generation(self):
        line = Line(Point(0, 0), Point(10, 10))
        c = Circle(Point(5, 5), 2)
        t = Text("Hi", Point(0, 0))

        root = to_xml_element([line, c, t])
        assert root.tag == "svg"

        main_g = root.find("g")
        assert main_g is not None

        assert main_g.find("line") is not None
        assert main_g.find("circle") is not None
        assert main_g.find("text") is not None

    def test_symbol_rendering(self):
        line = Line(Point(0, 0), Point(10, 10))
        sym = Symbol(elements=[line], ports={})

        root = to_xml_element([sym])
        g1 = root.find("g")
        assert g1 is not None
        sym_g = g1.find("g")

        assert sym_g is not None
        assert sym_g.get("class") == "symbol"
        assert sym_g.find("line") is not None

    def test_style_application(self):
        style = Style(stroke="red", stroke_width=2)
        line = Line(Point(0, 0), Point(10, 10), style=style)

        root = to_xml_element([line])
        g1 = root.find("g")
        assert g1 is not None
        line_elem = g1.find("line")
        assert line_elem is not None
        style_str = line_elem.get("style")
        assert style_str is not None

        assert "stroke:red" in style_str
        assert "stroke-width:2" in style_str

    def test_calculate_bounds(self):
        line = Line(Point(10, 20), Point(50, 80))
        c = Circle(Point(50, 50), 10)

        # Test line bounds
        assert calculate_bounds([line]) == (10, 20, 50, 80)

        # Test circle bounds (center +/- radius)
        # 50-10=40, 50+10=60
        assert calculate_bounds([c]) == (40, 40, 60, 60)

        # Test combined
        # min_x=10, min_y=20, max_x=60, max_y=80
        assert calculate_bounds([line, c]) == (10, 20, 60, 80)

    def test_render_to_file_output(self, tmp_path):
        f = tmp_path / "test.svg"
        line = Line(Point(0, 0), Point(10, 10))
        render_to_svg([line], str(f), width="auto", height="auto")

        assert f.exists()
        content = f.read_text(encoding="utf-8")
        assert "<svg" in content
        assert "viewBox" in content


class TestRendererExtended:
    def test_save_svg(self, tmp_path):
        root = to_xml_element([Line(Point(0, 0), Point(10, 10))])
        out = tmp_path / "out.svg"
        save_svg(root, str(out))
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "<?xml" in content
        assert "<svg" in content

    def test_path_rendering(self):
        path = Path(d="M 0 0 L 10 10", style=Style(stroke="black"))
        root = to_xml_element([path])
        g1 = root.find("g")
        assert g1 is not None
        path_elem = g1.find("path")
        assert path_elem is not None
        assert path_elem.get("d") == "M 0 0 L 10 10"

    def test_polygon_rendering(self):
        polygon = Polygon(
            points=[Point(0, 0), Point(10, 0), Point(5, 10)],
            style=Style(stroke="black", fill="none"),
        )
        root = to_xml_element([polygon])
        g1 = root.find("g")
        assert g1 is not None
        poly_elem = g1.find("polygon")
        assert poly_elem is not None
        points_str = poly_elem.get("points")
        assert points_str is not None
        assert "0,0" in points_str

    def test_group_rendering(self):
        group = Group(
            elements=[Line(Point(0, 0), Point(10, 10))], style=Style(stroke="blue")
        )
        root = to_xml_element([group])
        g1 = root.find("g")
        assert g1 is not None
        inner_g = g1.find("g")
        assert inner_g is not None
        assert inner_g.find("line") is not None
        style_str = inner_g.get("style")
        assert style_str is not None
        assert "blue" in style_str

    def test_calculate_bounds_empty_list(self):
        assert calculate_bounds([]) == (0, 0, 100, 100)

    def test_calculate_bounds_single_element(self):
        assert calculate_bounds([Line(Point(5, 10), Point(15, 20))]) == (5, 10, 15, 20)

    def test_calculate_bounds_polygon(self):
        polygon = Polygon(points=[Point(0, 0), Point(20, 0), Point(10, 30)])
        assert calculate_bounds([polygon]) == (0, 0, 20, 30)
