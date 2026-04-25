"""Tests for schematika.cable.renderer.

Covers _connector_kwargs, _cable_kwargs, and render_cable_svg against
fabricated CableDrawing inputs. Skips if wireviz is not installed.
"""

import pytest

pytest.importorskip("wireviz")

from schematika.cable.model import (  # noqa: E402
    CableConnection,
    CableConnector,
    CableDef,
    CableDrawing,
)
from schematika.cable.renderer import (  # noqa: E402
    _cable_kwargs,
    _connector_kwargs,
    render_cable_svg,
)

# ---------------------------------------------------------------------------
# _connector_kwargs
# ---------------------------------------------------------------------------


class TestConnectorKwargs:
    def test_minimum_includes_pins_and_pincount(self):
        c = CableConnector(designator="X01", pins=("1", "2"))
        kw = _connector_kwargs(c)
        assert kw["pins"] == ["1", "2"]
        assert kw["show_pincount"] is False

    def test_pins_returned_as_list(self):
        c = CableConnector(designator="X01", pins=("1", "2", "3"))
        kw = _connector_kwargs(c)
        assert isinstance(kw["pins"], list)
        assert kw["pins"] == ["1", "2", "3"]

    def test_omits_empty_string_fields(self):
        c = CableConnector(designator="X01", pins=("1",))
        kw = _connector_kwargs(c)
        assert "type" not in kw
        assert "subtype" not in kw
        assert "style" not in kw
        assert "notes" not in kw
        assert "loops" not in kw

    def test_includes_type_when_set(self):
        c = CableConnector(designator="X01", pins=("1",), type="M12")
        kw = _connector_kwargs(c)
        assert kw["type"] == "M12"

    def test_includes_subtype_when_set(self):
        c = CableConnector(designator="X01", pins=("1",), subtype="female")
        kw = _connector_kwargs(c)
        assert kw["subtype"] == "female"

    def test_includes_style_when_set(self):
        c = CableConnector(designator="X01", pins=("1",), style="simple")
        kw = _connector_kwargs(c)
        assert kw["style"] == "simple"

    def test_includes_notes_when_set(self):
        c = CableConnector(designator="X01", pins=("1",), notes="ferrule")
        kw = _connector_kwargs(c)
        assert kw["notes"] == "ferrule"

    def test_show_pincount_passes_through(self):
        c = CableConnector(designator="X01", pins=("1",), show_pincount=True)
        kw = _connector_kwargs(c)
        assert kw["show_pincount"] is True

    def test_loops_converted_to_list_of_lists(self):
        c = CableConnector(
            designator="X01",
            pins=("1", "2", "3"),
            loops=(("1", "3"),),
        )
        kw = _connector_kwargs(c)
        assert kw["loops"] == [["1", "3"]]

    def test_multiple_loops(self):
        c = CableConnector(
            designator="X01",
            pins=("1", "2", "3", "4"),
            loops=(("1", "2"), ("3", "4")),
        )
        kw = _connector_kwargs(c)
        assert kw["loops"] == [["1", "2"], ["3", "4"]]


# ---------------------------------------------------------------------------
# _cable_kwargs
# ---------------------------------------------------------------------------


class TestCableKwargs:
    def test_minimum_only_wirecount(self):
        cd = CableDef(designator="A-W001", wirecount=4)
        kw = _cable_kwargs(cd)
        assert kw == {"wirecount": 4}

    def test_includes_gauge_and_unit_together(self):
        cd = CableDef(
            designator="A-W001", wirecount=3, wire_gauge=2.5, gauge_unit="mm2"
        )
        kw = _cable_kwargs(cd)
        assert kw["gauge"] == 2.5
        assert kw["gauge_unit"] == "mm2"

    def test_omits_gauge_when_zero(self):
        cd = CableDef(designator="A-W001", wirecount=3, wire_gauge=0.0)
        kw = _cable_kwargs(cd)
        assert "gauge" not in kw
        assert "gauge_unit" not in kw

    def test_includes_length_when_set(self):
        cd = CableDef(designator="A-W001", wirecount=3, length=5.0)
        kw = _cable_kwargs(cd)
        assert kw["length"] == 5.0

    def test_omits_length_when_zero(self):
        cd = CableDef(designator="A-W001", wirecount=3, length=0.0)
        kw = _cable_kwargs(cd)
        assert "length" not in kw

    def test_wire_colors_converted_to_list(self):
        cd = CableDef(
            designator="A-W001",
            wirecount=3,
            wire_colors=("BN", "BU", "GNYE"),
        )
        kw = _cable_kwargs(cd)
        assert kw["colors"] == ["BN", "BU", "GNYE"]

    def test_omits_colors_when_empty(self):
        cd = CableDef(designator="A-W001", wirecount=3, wire_colors=())
        kw = _cable_kwargs(cd)
        assert "colors" not in kw

    def test_omits_default_category(self):
        cd = CableDef(designator="A-W001", wirecount=3, category="cable")
        kw = _cable_kwargs(cd)
        assert "category" not in kw

    def test_includes_non_default_category(self):
        cd = CableDef(designator="A-W001", wirecount=3, category="bundle")
        kw = _cable_kwargs(cd)
        assert kw["category"] == "bundle"

    def test_includes_shield_when_true(self):
        cd = CableDef(designator="A-W001", wirecount=3, shield=True)
        kw = _cable_kwargs(cd)
        assert kw["shield"] is True

    def test_omits_shield_when_false(self):
        cd = CableDef(designator="A-W001", wirecount=3, shield=False)
        kw = _cable_kwargs(cd)
        assert "shield" not in kw

    def test_includes_notes_when_set(self):
        cd = CableDef(designator="A-W001", wirecount=3, notes="3P+PE")
        kw = _cable_kwargs(cd)
        assert kw["notes"] == "3P+PE"

    def test_omits_notes_when_empty(self):
        cd = CableDef(designator="A-W001", wirecount=3)
        kw = _cable_kwargs(cd)
        assert "notes" not in kw


# ---------------------------------------------------------------------------
# render_cable_svg — end-to-end via wireviz
# ---------------------------------------------------------------------------


def _make_drawing(
    *,
    wire_gauge: float = 1.5,
    wire_colors: tuple[str, ...] = ("BN", "BU"),
) -> CableDrawing:
    cable = CableDef(
        designator="A-W001",
        wirecount=2,
        wire_gauge=wire_gauge,
        wire_colors=wire_colors,
    )
    src = CableConnector(designator="X01", pins=("1", "2"))
    dst = CableConnector(designator="J1", pins=("A", "B"))
    connections = (
        CableConnection(
            from_connector="X01",
            from_pin="1",
            cable="A-W001",
            wire=1,
            to_connector="J1",
            to_pin="A",
        ),
        CableConnection(
            from_connector="X01",
            from_pin="2",
            cable="A-W001",
            wire=2,
            to_connector="J1",
            to_pin="B",
        ),
    )
    return CableDrawing(
        cable=cable,
        connectors=(src, dst),
        connections=connections,
        title="Test",
    )


class TestRenderCableSvg:
    def test_returns_string(self):
        svg = render_cable_svg(_make_drawing())
        assert isinstance(svg, str)

    def test_starts_with_svg_or_xml(self):
        svg = render_cable_svg(_make_drawing())
        # WireViz returns either "<svg" or an "<?xml" prologue
        assert svg.startswith("<svg") or svg.startswith("<?xml")

    def test_contains_svg_root_element(self):
        svg = render_cable_svg(_make_drawing())
        assert "<svg" in svg

    def test_contains_connector_designators(self):
        svg = render_cable_svg(_make_drawing())
        assert "X01" in svg
        assert "J1" in svg

    def test_contains_cable_designator(self):
        svg = render_cable_svg(_make_drawing())
        # graphviz HTML-encodes hyphens as &#45;
        assert "W001" in svg

    def test_handles_minimal_cable(self):
        cable = CableDef(designator="A-W099", wirecount=1)
        c1 = CableConnector(designator="X01", pins=("1",))
        c2 = CableConnector(designator="J1", pins=("A",))
        connections = (
            CableConnection(
                from_connector="X01",
                from_pin="1",
                cable="A-W099",
                wire=1,
                to_connector="J1",
                to_pin="A",
            ),
        )
        drawing = CableDrawing(
            cable=cable, connectors=(c1, c2), connections=connections
        )
        svg = render_cable_svg(drawing)
        # graphviz HTML-encodes hyphens
        assert "W099" in svg

    def test_three_connector_drawing(self):
        # Source + two distinct targets
        cable = CableDef(designator="A-W005", wirecount=2)
        src = CableConnector(designator="M1", pins=("U", "V"))
        t1 = CableConnector(designator="X1", pins=("1",))
        t2 = CableConnector(designator="X2", pins=("1",))
        connections = (
            CableConnection(
                from_connector="M1",
                from_pin="U",
                cable="A-W005",
                wire=1,
                to_connector="X1",
                to_pin="1",
            ),
            CableConnection(
                from_connector="M1",
                from_pin="V",
                cable="A-W005",
                wire=2,
                to_connector="X2",
                to_pin="1",
            ),
        )
        drawing = CableDrawing(
            cable=cable, connectors=(src, t1, t2), connections=connections
        )
        svg = render_cable_svg(drawing)
        assert "M1" in svg
        assert "X1" in svg
        assert "X2" in svg

    def test_renders_with_wire_colors(self):
        drawing = _make_drawing(wire_colors=("BN", "BU"))
        svg = render_cable_svg(drawing)
        assert isinstance(svg, str)
        assert "<svg" in svg

    def test_renders_with_loops(self):
        cable = CableDef(designator="A-W001", wirecount=1)
        src = CableConnector(
            designator="X01",
            pins=("1", "2", "3"),
            loops=(("1", "3"),),
        )
        dst = CableConnector(designator="J1", pins=("A",))
        connections = (
            CableConnection(
                from_connector="X01",
                from_pin="2",
                cable="A-W001",
                wire=1,
                to_connector="J1",
                to_pin="A",
            ),
        )
        drawing = CableDrawing(
            cable=cable, connectors=(src, dst), connections=connections
        )
        svg = render_cable_svg(drawing)
        assert "<svg" in svg

    def test_renders_with_connector_metadata(self):
        cable = CableDef(designator="A-W001", wirecount=1)
        src = CableConnector(
            designator="X01",
            pins=("1",),
            type="M12",
            subtype="female",
            notes="example",
        )
        dst = CableConnector(designator="J1", pins=("A",), style="simple")
        connections = (
            CableConnection(
                from_connector="X01",
                from_pin="1",
                cable="A-W001",
                wire=1,
                to_connector="J1",
                to_pin="A",
            ),
        )
        drawing = CableDrawing(
            cable=cable, connectors=(src, dst), connections=connections
        )
        svg = render_cable_svg(drawing)
        assert "<svg" in svg

    def test_renders_with_shield(self):
        cable = CableDef(designator="A-W001", wirecount=2, shield=True)
        src = CableConnector(designator="X01", pins=("1", "2"))
        dst = CableConnector(designator="J1", pins=("A", "B"))
        connections = (
            CableConnection(
                from_connector="X01",
                from_pin="1",
                cable="A-W001",
                wire=1,
                to_connector="J1",
                to_pin="A",
            ),
            CableConnection(
                from_connector="X01",
                from_pin="2",
                cable="A-W001",
                wire=2,
                to_connector="J1",
                to_pin="B",
            ),
        )
        drawing = CableDrawing(
            cable=cable, connectors=(src, dst), connections=connections
        )
        svg = render_cable_svg(drawing)
        assert "<svg" in svg
