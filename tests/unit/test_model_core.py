from dataclasses import FrozenInstanceError

import pytest

from schematika.electrical.model.core import Point, Port, Style, Symbol, Vector


class TestModelCore:
    def test_vector_creation_and_ops(self):
        v1 = Vector(1.0, 2.0)
        assert v1.dx == 1.0
        assert v1.dy == 2.0

        v2 = Vector(3, 4)
        v3 = v1 + v2
        assert v3.dx == 4
        assert v3.dy == 6

        v4 = v1 * 2
        assert v4.dx == 2
        assert v4.dy == 4

    def test_point_creation_and_ops(self):
        p1 = Point(10.0, 20.0)
        assert p1.x == 10.0
        assert p1.y == 20.0

        v = Vector(5, 5)
        p2 = p1 + v
        assert isinstance(p2, Point)
        assert p2.x == 15
        assert p2.y == 25

        v_res = p2 - p1
        assert isinstance(v_res, Vector)
        assert v_res.dx == 5
        assert v_res.dy == 5

        with pytest.raises(TypeError):
            p1 + p2

        with pytest.raises(TypeError):
            p1 - v  # ty: ignore[unsupported-operator]

    def test_immutability(self):
        v = Vector(1, 1)
        with pytest.raises(FrozenInstanceError):
            v.dx = 2  # ty: ignore[invalid-assignment]

        p = Point(0, 0)
        with pytest.raises(FrozenInstanceError):
            p.x = 1  # ty: ignore[invalid-assignment]

    def test_style_defaults(self):
        s = Style()
        assert s.stroke == "black"
        assert s.stroke_width == 1.0
        assert s.fill == "none"
        assert s.opacity == 1.0

    def test_port_and_symbol(self):
        p = Point(0, 0)
        v = Vector(1, 0)
        port = Port(id="1", position=p, direction=v)
        assert port.id == "1"

        sym = Symbol(elements=[], ports={}, label="K1")
        assert sym.label == "K1"


class TestStandardPins:
    """Tests for flat pin constant definitions."""

    def test_coil_pins(self):
        from schematika.electrical.model.constants import COIL_PINS

        assert COIL_PINS == ("A1", "A2")

    def test_no_contact_pins(self):
        from schematika.electrical.model.constants import NO_CONTACT_PINS

        assert NO_CONTACT_PINS == ("13", "14")

    def test_nc_contact_pins(self):
        from schematika.electrical.model.constants import NC_CONTACT_PINS

        assert NC_CONTACT_PINS == ("11", "12")

    def test_cb_3p_pins(self):
        from schematika.electrical.model.constants import CB_3P_PINS

        assert CB_3P_PINS == ("1", "2", "3", "4", "5", "6")

    def test_cb_2p_pins(self):
        from schematika.electrical.model.constants import CB_2P_PINS

        assert CB_2P_PINS == ("1", "2", "3", "4")

    def test_contactor_3p_pins(self):
        from schematika.electrical.model.constants import CONTACTOR_3P_PINS

        assert CONTACTOR_3P_PINS == ("L1", "T1", "L2", "T2", "L3", "T3")

    def test_thermal_overload_pins(self):
        from schematika.electrical.model.constants import THERMAL_OVERLOAD_PINS

        assert THERMAL_OVERLOAD_PINS == ("", "T1", "", "T2", "", "T3")
