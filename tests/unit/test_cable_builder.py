"""Tests for schematika.cable.builder.

Covers build_cable_drawings, build_inter_device_drawings, and the
internal helpers (_reorder_pins_last, _build_connector_from_override,
_build_cable_def, _build_target_connectors, _resolve_inter_device_pins).
"""

import pytest

from schematika.cable.builder import (
    _build_cable_def,
    _build_connector_from_override,
    _build_target_connectors,
    _reorder_pins_last,
    _resolve_inter_device_pins,
    build_cable_drawings,
    build_inter_device_drawings,
)
from schematika.cable.errors import CableError
from schematika.cable.model import CableConnector, CableDef
from schematika.electrical.field_devices import (
    CableData,
    ConnectorData,
    DeviceCable,
    DeviceTemplate,
    FieldDevice,
    PinDef,
)
from schematika.electrical.inter_device import InterDeviceConnection
from schematika.electrical.terminal import Terminal

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class TestReorderPinsLast:
    def test_no_pins_last_returns_input(self):
        triples = [("U", "X1", "1"), ("V", "X1", "2")]
        assert _reorder_pins_last(triples, ()) == triples

    def test_moves_pe_to_end(self):
        triples = [
            ("U", "X1", "1"),
            ("PE", "X1", "2"),
            ("V", "X1", "3"),
        ]
        result = _reorder_pins_last(triples, ("PE",))
        assert [t[0] for t in result] == ["U", "V", "PE"]

    def test_preserves_order_among_normals(self):
        triples = [
            ("PE", "X1", "1"),
            ("U", "X1", "2"),
            ("V", "X1", "3"),
            ("W", "X1", "4"),
        ]
        result = _reorder_pins_last(triples, ("PE",))
        assert [t[0] for t in result] == ["U", "V", "W", "PE"]

    def test_multiple_deferred_pins(self):
        triples = [
            ("U", "X1", "1"),
            ("PE", "X1", "2"),
            ("V", "X1", "3"),
            ("N", "X1", "4"),
        ]
        result = _reorder_pins_last(triples, ("PE", "N"))
        # Both deferred go to end, in original relative order
        assert [t[0] for t in result] == ["U", "V", "PE", "N"]

    def test_no_match_returns_unchanged_order(self):
        triples = [("U", "X1", "1"), ("V", "X1", "2")]
        result = _reorder_pins_last(triples, ("PE",))
        assert result == triples


class TestBuildConnectorFromOverride:
    def test_no_connector_data(self):
        c = _build_connector_from_override("X01", ("1", "2"), None)
        assert c == CableConnector(designator="X01", pins=("1", "2"))

    def test_overrides_type_and_subtype(self):
        cd = ConnectorData(
            pins=(),
            type="M12",
            subtype="female",
        )
        c = _build_connector_from_override("X01", ("1", "2"), cd)
        assert c.type == "M12"
        assert c.subtype == "female"
        assert c.pins == ("1", "2")

    def test_loops_with_pins_replaces_pins(self):
        cd = ConnectorData(
            pins=("L1", "L2", "L3"),
            loops=((1, 2),),
        )
        c = _build_connector_from_override("X01", ("a", "b"), cd)
        # When loops *and* pins are set, the override pins win
        assert c.pins == ("L1", "L2", "L3")
        assert c.loops == (("1", "2"),)

    def test_loops_only_no_pin_replacement(self):
        cd = ConnectorData(pins=(), loops=((1, 3),))
        c = _build_connector_from_override("X01", ("a", "b"), cd)
        # No override pins → default to caller's pins
        assert c.pins == ("a", "b")
        assert c.loops == (("1", "3"),)

    def test_loops_converted_to_string_pairs(self):
        cd = ConnectorData(pins=(), loops=((1, 2), (3, 4)))
        c = _build_connector_from_override("X01", ("a", "b", "c", "d"), cd)
        assert c.loops == (("1", "2"), ("3", "4"))

    def test_notes_and_style(self):
        cd = ConnectorData(pins=(), style="simple", notes="Wire ferrule")
        c = _build_connector_from_override("X01", ("1",), cd)
        assert c.style == "simple"
        assert c.notes == "Wire ferrule"

    def test_empty_string_when_field_is_none(self):
        cd = ConnectorData(pins=())
        c = _build_connector_from_override("X01", ("1",), cd)
        assert c.type == ""
        assert c.subtype == ""
        assert c.style == ""
        assert c.notes == ""


class TestBuildCableDef:
    def test_no_cable_data(self):
        cd = _build_cable_def("A-W001", 4, None)
        assert cd == CableDef(designator="A-W001", wirecount=4)

    def test_copies_cable_data_fields(self):
        data = CableData(
            wire_gauge=2.5,
            cable_length=10.0,
            category="bundle",
            wire_colors=("BN", "BU", "GNYE"),
            cable_note="3P+PE",
        )
        cd = _build_cable_def("A-W001", 3, data)
        assert cd.wire_gauge == 2.5
        assert cd.length == 10.0
        assert cd.category == "bundle"
        assert cd.wire_colors == ("BN", "BU", "GNYE")
        assert cd.notes == "3P+PE"

    def test_none_cable_length_becomes_zero(self):
        data = CableData(wire_gauge=1.5, cable_length=None)
        cd = _build_cable_def("A-W001", 2, data)
        assert cd.length == 0.0

    def test_none_wire_colors_becomes_empty(self):
        data = CableData(wire_gauge=1.5)
        cd = _build_cable_def("A-W001", 2, data)
        assert cd.wire_colors == ()


class TestBuildTargetConnectors:
    def test_single_target(self):
        triples = [("U", "X1", "1"), ("V", "X1", "2"), ("W", "X1", "3")]
        connectors, wire_targets = _build_target_connectors(triples)
        assert len(connectors) == 1
        assert connectors[0].designator == "X1"
        assert connectors[0].pins == ("1", "2", "3")
        assert connectors[0].notes == "Wire ferrule"
        assert wire_targets == {0: ("X1", "1"), 1: ("X1", "2"), 2: ("X1", "3")}

    def test_multiple_targets(self):
        triples = [
            ("U", "X1", "1"),
            ("V", "X2", "1"),
            ("W", "X1", "2"),
        ]
        connectors, _ = _build_target_connectors(triples)
        names = [c.designator for c in connectors]
        # Insertion order preserved (X1 first, X2 second)
        assert names == ["X1", "X2"]
        x1 = next(c for c in connectors if c.designator == "X1")
        assert x1.pins == ("1", "2")

    def test_empty_input(self):
        connectors, wire_targets = _build_target_connectors([])
        assert connectors == []
        assert wire_targets == {}


# ---------------------------------------------------------------------------
# build_cable_drawings — public API
# ---------------------------------------------------------------------------


class TestBuildCableDrawings:
    def test_single_device_no_metadata(self):
        t = Terminal("X1", "Power")
        drawings = build_cable_drawings(
            external_connections=[
                ("M1", "U", t, "1", "PLC", ""),
                ("M1", "V", t, "2", "PLC", ""),
            ],
            field_devices=[],
        )
        assert len(drawings) == 1
        d = drawings[0]
        assert d.cable.designator == "A-W001"
        assert d.cable.wirecount == 2
        assert d.title == "M1"

    def test_default_cable_prefix_and_start(self):
        t = Terminal("X1", "Power")
        drawings = build_cable_drawings(
            external_connections=[("M1", "U", t, "1", "", "")],
            field_devices=[],
        )
        assert drawings[0].cable.designator == "A-W001"

    def test_custom_cable_prefix(self):
        t = Terminal("X1", "Power")
        drawings = build_cable_drawings(
            external_connections=[("M1", "U", t, "1", "", "")],
            field_devices=[],
            cable_prefix="B-W",
        )
        assert drawings[0].cable.designator == "B-W001"

    def test_custom_cable_start(self):
        t = Terminal("X1", "Power")
        drawings = build_cable_drawings(
            external_connections=[("M1", "U", t, "1", "", "")],
            field_devices=[],
            cable_start=42,
        )
        assert drawings[0].cable.designator == "A-W042"

    def test_cable_numbering_increments(self):
        t = Terminal("X1", "Power")
        drawings = build_cable_drawings(
            external_connections=[
                ("M1", "U", t, "1", "", ""),
                ("M2", "U", t, "2", "", ""),
                ("M3", "U", t, "3", "", ""),
            ],
            field_devices=[],
        )
        assert [d.cable.designator for d in drawings] == [
            "A-W001",
            "A-W002",
            "A-W003",
        ]

    def test_pe_pin_moved_last_by_default(self):
        t = Terminal("X1", "Power")
        drawings = build_cable_drawings(
            external_connections=[
                ("M1", "U", t, "1", "", ""),
                ("M1", "PE", t, "2", "", ""),
                ("M1", "V", t, "3", "", ""),
            ],
            field_devices=[],
        )
        d = drawings[0]
        # Source connector pins ordered: U, V, PE
        source = d.connectors[0]
        assert source.pins == ("U", "V", "PE")

    def test_custom_pins_last(self):
        t = Terminal("X1", "Power")
        drawings = build_cable_drawings(
            external_connections=[
                ("M1", "A", t, "1", "", ""),
                ("M1", "Z", t, "2", "", ""),
                ("M1", "B", t, "3", "", ""),
            ],
            field_devices=[],
            pins_last=("Z",),
        )
        d = drawings[0]
        assert d.connectors[0].pins == ("A", "B", "Z")

    def test_empty_connections(self):
        drawings = build_cable_drawings(
            external_connections=[],
            field_devices=[],
        )
        assert drawings == []

    def test_field_device_contributes_cable_data(self):
        t = Terminal("X1", "Power")
        template = DeviceTemplate(mpn="motor", pins=(PinDef("U", t),))
        cable = CableData(
            wire_gauge=2.5,
            cable_length=5.0,
            wire_colors=("BN", "BU"),
        )
        device = FieldDevice(tag="M1", template=template, terminal=t, cable=cable)
        drawings = build_cable_drawings(
            external_connections=[
                ("M1", "U", t, "1", "", ""),
                ("M1", "V", t, "2", "", ""),
            ],
            field_devices=[device],
        )
        assert drawings[0].cable.wire_gauge == 2.5
        assert drawings[0].cable.length == 5.0
        assert drawings[0].cable.wire_colors == ("BN", "BU")

    def test_field_device_connector_data(self):
        t = Terminal("X1", "Power")
        template = DeviceTemplate(mpn="motor", pins=(PinDef("U", t),))
        connector = ConnectorData(pins=(), type="M12", subtype="female")
        device = FieldDevice(
            tag="M1",
            template=template,
            terminal=t,
            connectors=(connector,),
        )
        drawings = build_cable_drawings(
            external_connections=[("M1", "U", t, "1", "", "")],
            field_devices=[device],
        )
        source = drawings[0].connectors[0]
        assert source.type == "M12"
        assert source.subtype == "female"

    def test_target_connector_has_wire_ferrule_note(self):
        t = Terminal("X1", "Power")
        drawings = build_cable_drawings(
            external_connections=[("M1", "U", t, "1", "", "")],
            field_devices=[],
        )
        # connectors[0] is source, connectors[1] is target  # noqa: ERA001
        target = drawings[0].connectors[1]
        assert target.notes == "Wire ferrule"

    def test_connection_wires_are_one_indexed(self):
        t = Terminal("X1", "Power")
        drawings = build_cable_drawings(
            external_connections=[
                ("M1", "U", t, "1", "", ""),
                ("M1", "V", t, "2", "", ""),
            ],
            field_devices=[],
        )
        wires = [c.wire for c in drawings[0].connections]
        assert wires == [1, 2]

    def test_devices_grouped_by_first_field(self):
        t = Terminal("X1", "Power")
        drawings = build_cable_drawings(
            external_connections=[
                ("M1", "U", t, "1", "", ""),
                ("M2", "U", t, "2", "", ""),
                ("M1", "V", t, "3", "", ""),
            ],
            field_devices=[],
        )
        # Two distinct devices = two drawings
        assert len(drawings) == 2
        m1_drawing = next(d for d in drawings if d.title == "M1")
        # M1 has two pins (U, V) — both rows merged
        assert m1_drawing.cable.wirecount == 2

    def test_multi_cable_device_yields_multiple_drawings(self):
        t = Terminal("X1", "IO")
        template = DeviceTemplate(
            mpn="valve",
            pins=(
                PinDef("1", t),
                PinDef("2", t),
                PinDef("3", t),
                PinDef("4", t),
            ),
        )
        dc1 = DeviceCable(pins=("1", "2"), cable=CableData(wire_gauge=1.5))
        dc2 = DeviceCable(pins=("3", "4"), cable=CableData(wire_gauge=0.75))
        device = FieldDevice(
            tag="CV1", template=template, terminal=t, cables=(dc1, dc2)
        )
        drawings = build_cable_drawings(
            external_connections=[
                ("CV1", "1", t, "1", "", ""),
                ("CV1", "2", t, "2", "", ""),
                ("CV1", "3", t, "3", "", ""),
                ("CV1", "4", t, "4", "", ""),
            ],
            field_devices=[device],
        )
        assert len(drawings) == 2
        # Per-group wire gauge
        assert drawings[0].cable.wire_gauge == 1.5
        assert drawings[1].cable.wire_gauge == 0.75

    def test_multi_cable_uses_group_label_in_designator(self):
        t = Terminal("X1", "IO")
        template = DeviceTemplate(
            mpn="valve",
            pins=(PinDef("1", t), PinDef("2", t)),
        )
        dc1 = DeviceCable(pins=("1",), cable=CableData(wire_gauge=1.5))
        dc2 = DeviceCable(pins=("2",), cable=CableData(wire_gauge=0.75))
        device = FieldDevice(
            tag="CV1", template=template, terminal=t, cables=(dc1, dc2)
        )
        drawings = build_cable_drawings(
            external_connections=[
                ("CV1", "1", t, "1", "", ""),
                ("CV1", "2", t, "2", "", ""),
            ],
            field_devices=[device],
        )
        # Source connectors named "CV1 [A]" and "CV1 [B]"
        source_designators = [d.connectors[0].designator for d in drawings]
        assert source_designators == ["CV1 [A]", "CV1 [B]"]

    def test_multi_cable_skips_empty_groups(self):
        t = Terminal("X1", "IO")
        template = DeviceTemplate(
            mpn="valve",
            pins=(PinDef("1", t), PinDef("2", t)),
        )
        dc1 = DeviceCable(pins=("1",), cable=CableData(wire_gauge=1.5))
        dc2 = DeviceCable(pins=("2",), cable=CableData(wire_gauge=0.75))
        device = FieldDevice(
            tag="CV1", template=template, terminal=t, cables=(dc1, dc2)
        )
        # Only group A has connections — group B is empty
        drawings = build_cable_drawings(
            external_connections=[("CV1", "1", t, "1", "", "")],
            field_devices=[device],
        )
        assert len(drawings) == 1
        assert drawings[0].connectors[0].designator == "CV1 [A]"


# ---------------------------------------------------------------------------
# _resolve_inter_device_pins
# ---------------------------------------------------------------------------


class TestResolveInterDevicePins:
    def _conn(
        self,
        *,
        from_device: str = "A",
        from_connector: str = "J1",
        to_device: str = "B",
        to_connector: str = "J2",
        cable: CableData | None = None,
        from_connector_data: ConnectorData | None = None,
        to_connector_data: ConnectorData | None = None,
    ) -> InterDeviceConnection:
        return InterDeviceConnection(
            from_device=from_device,
            from_connector=from_connector,
            to_device=to_device,
            to_connector=to_connector,
            cable=cable if cable is not None else CableData(wire_gauge=1.5),
            from_connector_data=from_connector_data,
            to_connector_data=to_connector_data,
        )

    def test_neither_side_with_wire_colors_synthesises_pins(self):
        conn = self._conn(
            cable=CableData(wire_gauge=1.5, wire_colors=("BN", "BU", "GNYE")),
        )
        from_cd, to_cd, pins = _resolve_inter_device_pins(conn)
        assert from_cd is None
        assert to_cd is None
        assert pins == ("1", "2", "3")

    def test_neither_side_no_wire_colors_raises(self):
        conn = self._conn(cable=CableData(wire_gauge=1.5))
        with pytest.raises(CableError, match="wire count is undefined"):
            _resolve_inter_device_pins(conn)

    def test_only_from_side_mirrors(self):
        from_cd = ConnectorData(pins=("1", "2"), type="M12")
        conn = self._conn(from_connector_data=from_cd)
        a, b, pins = _resolve_inter_device_pins(conn)
        assert a is from_cd
        assert b is from_cd
        assert pins == ("1", "2")

    def test_only_to_side_mirrors(self):
        to_cd = ConnectorData(pins=("a", "b"), type="M12")
        conn = self._conn(to_connector_data=to_cd)
        a, b, pins = _resolve_inter_device_pins(conn)
        assert a is to_cd
        assert b is to_cd
        assert pins == ("a", "b")

    def test_both_sides_equal_pin_counts(self):
        from_cd = ConnectorData(pins=("1", "2"))
        to_cd = ConnectorData(pins=("a", "b"))
        conn = self._conn(from_connector_data=from_cd, to_connector_data=to_cd)
        a, b, pins = _resolve_inter_device_pins(conn)
        assert a is from_cd
        assert b is to_cd
        # pins comes from from_cd if non-empty
        assert pins == ("1", "2")

    def test_both_sides_unequal_raises(self):
        from_cd = ConnectorData(pins=("1", "2", "3"))
        to_cd = ConnectorData(pins=("a", "b"))
        conn = self._conn(from_connector_data=from_cd, to_connector_data=to_cd)
        with pytest.raises(CableError, match="connector pin counts differ"):
            _resolve_inter_device_pins(conn)

    def test_both_sides_empty_pins_uses_from(self):
        from_cd = ConnectorData(pins=(), type="X")
        to_cd = ConnectorData(pins=(), type="Y")
        conn = self._conn(from_connector_data=from_cd, to_connector_data=to_cd)
        _a, _b, pins = _resolve_inter_device_pins(conn)
        assert pins == ()


# ---------------------------------------------------------------------------
# build_inter_device_drawings
# ---------------------------------------------------------------------------


class TestBuildInterDeviceDrawings:
    def test_empty_list(self):
        assert build_inter_device_drawings([]) == []

    def test_single_connection_default_numbering(self):
        conn = InterDeviceConnection(
            from_device="BACKPLANE",
            from_connector="J1",
            to_device="MOTOR",
            to_connector="J2",
            cable=CableData(wire_gauge=1.5, wire_colors=("BN", "BU")),
        )
        drawings = build_inter_device_drawings([conn])
        assert len(drawings) == 1
        d = drawings[0]
        assert d.cable.designator == "A-W001"
        assert d.title == "BACKPLANE-J1 <-> MOTOR-J2"

    def test_two_connectors_per_drawing(self):
        conn = InterDeviceConnection(
            from_device="A",
            from_connector="J1",
            to_device="B",
            to_connector="J2",
            cable=CableData(wire_gauge=1.5, wire_colors=("BN",)),
        )
        drawings = build_inter_device_drawings([conn])
        assert len(drawings[0].connectors) == 2

    def test_custom_prefix_and_start(self):
        conn = InterDeviceConnection(
            from_device="A",
            from_connector="J1",
            to_device="B",
            to_connector="J2",
            cable=CableData(wire_gauge=1.5, wire_colors=("BN",)),
        )
        drawings = build_inter_device_drawings(
            [conn], cable_prefix="C-W", cable_start=10
        )
        assert drawings[0].cable.designator == "C-W010"

    def test_cable_numbering_increments(self):
        cable = CableData(wire_gauge=1.5, wire_colors=("BN",))
        conns = [
            InterDeviceConnection(
                from_device="A",
                from_connector=f"J{i}",
                to_device="B",
                to_connector=f"K{i}",
                cable=cable,
            )
            for i in range(3)
        ]
        drawings = build_inter_device_drawings(conns)
        assert [d.cable.designator for d in drawings] == [
            "A-W001",
            "A-W002",
            "A-W003",
        ]

    def test_connection_count_matches_pin_count(self):
        conn = InterDeviceConnection(
            from_device="A",
            from_connector="J1",
            to_device="B",
            to_connector="J2",
            cable=CableData(wire_gauge=1.5, wire_colors=("BN", "BU", "GNYE")),
        )
        drawings = build_inter_device_drawings([conn])
        assert len(drawings[0].connections) == 3
        assert [c.wire for c in drawings[0].connections] == [1, 2, 3]

    def test_pins_synthesised_from_wire_colors(self):
        conn = InterDeviceConnection(
            from_device="A",
            from_connector="J1",
            to_device="B",
            to_connector="J2",
            cable=CableData(wire_gauge=1.5, wire_colors=("BN", "BU")),
        )
        drawings = build_inter_device_drawings([conn])
        d = drawings[0]
        assert d.connectors[0].pins == ("1", "2")
        assert d.connectors[1].pins == ("1", "2")

    def test_missing_wire_data_raises(self):
        conn = InterDeviceConnection(
            from_device="A",
            from_connector="J1",
            to_device="B",
            to_connector="J2",
            cable=CableData(wire_gauge=1.5),
        )
        with pytest.raises(CableError):
            build_inter_device_drawings([conn])


# ---------------------------------------------------------------------------
# CableError
# ---------------------------------------------------------------------------


class TestCableError:
    def test_inherits_from_value_error(self):
        # Documented backward-compat — old call sites catch ValueError
        assert issubclass(CableError, ValueError)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(CableError, match="boom"):
            msg = "boom"
            raise CableError(msg)

    def test_caught_as_value_error(self):
        # Confirms backward-compat path
        with pytest.raises(ValueError, match="compat"):
            msg = "compat"
            raise CableError(msg)
