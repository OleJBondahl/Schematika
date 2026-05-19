"""Tests for the cable module's frozen dataclasses.

Round-trips CableConnector, CableDef, CableConnection, and CableDrawing,
asserts frozen-ness, and pins default values.
"""

import dataclasses

import pytest

from schematika.cable.model import (
    CableConnection,
    CableConnector,
    CableDef,
    CableDrawing,
)

# ---------------------------------------------------------------------------
# CableConnector
# ---------------------------------------------------------------------------


class TestCableConnector:
    def test_round_trip_minimum(self):
        c = CableConnector(designator="X01", pins=("1", "2", "3"))
        assert c.designator == "X01"
        assert c.pins == ("1", "2", "3")

    def test_default_field_values(self):
        c = CableConnector(designator="X01", pins=("1",))
        assert c.type == ""
        assert c.subtype == ""
        assert c.style == ""
        assert c.notes == ""
        assert c.show_pincount is False
        assert c.loops == ()

    def test_full_field_round_trip(self):
        c = CableConnector(
            designator="J1",
            pins=("A", "B"),
            type="M12",
            subtype="female",
            style="simple",
            notes="example note",
            show_pincount=True,
            loops=(("A", "B"),),
        )
        assert c.type == "M12"
        assert c.subtype == "female"
        assert c.style == "simple"
        assert c.notes == "example note"
        assert c.show_pincount is True
        assert c.loops == (("A", "B"),)

    def test_is_frozen(self):
        c = CableConnector(designator="X01", pins=("1",))
        with pytest.raises(dataclasses.FrozenInstanceError):
            c.designator = "X99"  # ty: ignore[invalid-assignment]

    def test_frozen_pins(self):
        c = CableConnector(designator="X01", pins=("1",))
        with pytest.raises(dataclasses.FrozenInstanceError):
            c.pins = ("2",)  # ty: ignore[invalid-assignment]

    def test_pins_tuple_type(self):
        c = CableConnector(designator="X01", pins=("1", "2"))
        # tuples are immutable — confirm we can't append
        assert isinstance(c.pins, tuple)

    def test_equality_by_value(self):
        a = CableConnector(designator="X01", pins=("1", "2"))
        b = CableConnector(designator="X01", pins=("1", "2"))
        assert a == b

    def test_inequality_by_pins(self):
        a = CableConnector(designator="X01", pins=("1", "2"))
        b = CableConnector(designator="X01", pins=("1",))
        assert a != b

    def test_hashable(self):
        c = CableConnector(designator="X01", pins=("1",))
        assert hash(c) == hash(CableConnector(designator="X01", pins=("1",)))


# ---------------------------------------------------------------------------
# CableDef
# ---------------------------------------------------------------------------


class TestCableDef:
    def test_round_trip_minimum(self):
        cd = CableDef(designator="A-W001", wirecount=4)
        assert cd.designator == "A-W001"
        assert cd.wirecount == 4

    def test_default_field_values(self):
        cd = CableDef(designator="A-W001", wirecount=4)
        assert cd.wire_gauge == 0.0
        assert cd.gauge_unit == "mm2"
        assert cd.length == 0.0
        assert cd.category == "cable"
        assert cd.wire_colors == ()
        assert cd.notes == ""
        assert cd.shield is False

    def test_full_field_round_trip(self):
        cd = CableDef(
            designator="A-W001",
            wirecount=3,
            wire_gauge=2.5,
            gauge_unit="AWG",
            length=10.0,
            category="bundle",
            wire_colors=("BN", "BU", "GNYE"),
            notes="3P+PE",
            shield=True,
        )
        assert cd.wire_gauge == 2.5
        assert cd.gauge_unit == "AWG"
        assert cd.length == 10.0
        assert cd.category == "bundle"
        assert cd.wire_colors == ("BN", "BU", "GNYE")
        assert cd.notes == "3P+PE"
        assert cd.shield is True

    def test_is_frozen(self):
        cd = CableDef(designator="A-W001", wirecount=4)
        with pytest.raises(dataclasses.FrozenInstanceError):
            cd.wirecount = 99  # ty: ignore[invalid-assignment]

    def test_equality_by_value(self):
        a = CableDef(designator="A-W001", wirecount=4)
        b = CableDef(designator="A-W001", wirecount=4)
        assert a == b

    def test_wirelabels_defaults_to_empty_tuple(self):
        cd = CableDef(designator="A-W001", wirecount=2)
        assert cd.wirelabels == ()

    def test_wirelabels_round_trip(self):
        cd = CableDef(
            designator="A-W001",
            wirecount=3,
            wirelabels=("V24", None, "GND"),
        )
        assert cd.wirelabels == ("V24", None, "GND")

    def test_wirelabels_is_frozen(self):
        cd = CableDef(designator="A-W001", wirecount=2, wirelabels=("A", "B"))
        with pytest.raises(dataclasses.FrozenInstanceError):
            cd.wirelabels = ("X", "Y")  # ty: ignore[invalid-assignment]


# ---------------------------------------------------------------------------
# CableConnection
# ---------------------------------------------------------------------------


class TestCableConnection:
    def test_round_trip(self):
        conn = CableConnection(
            from_connector="X01",
            from_pin="1",
            cable="A-W001",
            wire=1,
            to_connector="J1",
            to_pin="A",
        )
        assert conn.from_connector == "X01"
        assert conn.from_pin == "1"
        assert conn.cable == "A-W001"
        assert conn.wire == 1
        assert conn.to_connector == "J1"
        assert conn.to_pin == "A"

    def test_is_frozen(self):
        conn = CableConnection(
            from_connector="X01",
            from_pin="1",
            cable="A-W001",
            wire=1,
            to_connector="J1",
            to_pin="A",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            conn.wire = 99  # ty: ignore[invalid-assignment]

    def test_wire_must_be_int(self):
        # No __post_init__ enforcement, but the type hint says int.
        # round-trip a couple of values
        conn = CableConnection(
            from_connector="X",
            from_pin="1",
            cable="W",
            wire=42,
            to_connector="Y",
            to_pin="2",
        )
        assert conn.wire == 42

    def test_equality_by_value(self):
        kwargs = {
            "from_connector": "X",
            "from_pin": "1",
            "cable": "W",
            "wire": 1,
            "to_connector": "Y",
            "to_pin": "2",
        }
        assert CableConnection(**kwargs) == CableConnection(**kwargs)


# ---------------------------------------------------------------------------
# CableDrawing
# ---------------------------------------------------------------------------


class TestCableDrawing:
    def _make(self) -> CableDrawing:
        cable = CableDef(designator="A-W001", wirecount=2)
        c1 = CableConnector(designator="X01", pins=("1", "2"))
        c2 = CableConnector(designator="J1", pins=("A", "B"))
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
            connectors=(c1, c2),
            connections=connections,
            title="Test",
        )

    def test_round_trip(self):
        d = self._make()
        assert d.title == "Test"
        assert d.cable.designator == "A-W001"
        assert len(d.connectors) == 2
        assert len(d.connections) == 2

    def test_default_title_is_empty(self):
        cable = CableDef(designator="A-W001", wirecount=1)
        d = CableDrawing(cable=cable, connectors=(), connections=())
        assert d.title == ""

    def test_default_from_and_to_designators(self):
        cable = CableDef(designator="A-W001", wirecount=1)
        d = CableDrawing(cable=cable, connectors=(), connections=())
        assert d.from_designator == ""
        assert d.to_designators == ()

    def test_from_and_to_designators_round_trip(self):
        cable = CableDef(designator="A-W001", wirecount=1)
        d = CableDrawing(
            cable=cable,
            connectors=(),
            connections=(),
            from_designator="X1-1",
            to_designators=("JB1-J1", "JB2-J2"),
        )
        assert d.from_designator == "X1-1"
        assert d.to_designators == ("JB1-J1", "JB2-J2")

    def test_is_frozen(self):
        d = self._make()
        with pytest.raises(dataclasses.FrozenInstanceError):
            d.title = "Other"  # ty: ignore[invalid-assignment]

    def test_equality_by_value(self):
        a = self._make()
        b = self._make()
        assert a == b

    def test_connectors_is_tuple(self):
        d = self._make()
        assert isinstance(d.connectors, tuple)
        assert isinstance(d.connections, tuple)
