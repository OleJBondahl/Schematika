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
    _fmt_des,
    _reorder_pins_last,
    _resolve_inter_device_pins,
    _sort_synthesized_pins,
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
from schematika.electrical.inter_device import (
    CableTargetEndpoint,
    InterDeviceConnection,
    WireSpec,
)
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

    def test_mpn_only(self):
        cd = ConnectorData(pins=(), mpn="430450200")
        c = _build_connector_from_override("X01", ("1",), cd)
        assert c.mpn == "430450200"
        assert c.pincount is None

    def test_pincount_only(self):
        cd = ConnectorData(pins=(), pincount=4)
        c = _build_connector_from_override("X01", ("1",), cd)
        assert c.mpn == ""
        assert c.pincount == 4

    def test_mpn_and_pincount(self):
        cd = ConnectorData(pins=(), mpn="750-1506", pincount=6)
        c = _build_connector_from_override("X01", ("1",), cd)
        assert c.mpn == "750-1506"
        assert c.pincount == 6

    def test_mpn_pincount_default_none(self):
        cd = ConnectorData(pins=())
        c = _build_connector_from_override("X01", ("1",), cd)
        assert c.mpn == ""
        assert c.pincount is None


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
            to_endpoints=(
                CableTargetEndpoint(
                    device=to_device,
                    connector=to_connector,
                    connector_data=to_connector_data,
                ),
            ),
            cable=cable if cable is not None else CableData(wire_gauge=1.5),
            from_connector_data=from_connector_data,
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
            to_endpoints=(CableTargetEndpoint(device="MOTOR", connector="J2"),),
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
            to_endpoints=(CableTargetEndpoint(device="B", connector="J2"),),
            cable=CableData(wire_gauge=1.5, wire_colors=("BN",)),
        )
        drawings = build_inter_device_drawings([conn])
        assert len(drawings[0].connectors) == 2

    def test_custom_prefix_and_start(self):
        conn = InterDeviceConnection(
            from_device="A",
            from_connector="J1",
            to_endpoints=(CableTargetEndpoint(device="B", connector="J2"),),
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
                to_endpoints=(CableTargetEndpoint(device="B", connector=f"K{i}"),),
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
            to_endpoints=(CableTargetEndpoint(device="B", connector="J2"),),
            cable=CableData(wire_gauge=1.5, wire_colors=("BN", "BU", "GNYE")),
        )
        drawings = build_inter_device_drawings([conn])
        assert len(drawings[0].connections) == 3
        assert [c.wire for c in drawings[0].connections] == [1, 2, 3]

    def test_pins_synthesised_from_wire_colors(self):
        conn = InterDeviceConnection(
            from_device="A",
            from_connector="J1",
            to_endpoints=(CableTargetEndpoint(device="B", connector="J2"),),
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
            to_endpoints=(CableTargetEndpoint(device="B", connector="J2"),),
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
        msg = "boom"
        with pytest.raises(CableError, match="boom"):
            raise CableError(msg)

    def test_caught_as_value_error(self):
        # Confirms backward-compat path
        msg = "compat"
        with pytest.raises(ValueError, match="compat"):
            raise CableError(msg)


# ---------------------------------------------------------------------------
# Fan-out (multi-target) InterDeviceConnection
# ---------------------------------------------------------------------------


class TestFanOutInterDeviceConnection:
    """Tests for fan-out IDC with explicit WireSpec routing."""

    def test_single_target_wires_none_back_compat(self):
        """wires=None with one endpoint renders identically to the old 1:1 path."""
        conn = InterDeviceConnection(
            from_device="PLC1",
            from_connector="J1",
            to_endpoints=(CableTargetEndpoint(device="BMU1", connector="J1"),),
            cable=CableData(wire_gauge=1.5, wire_colors=("BN", "BU")),
        )
        drawings = build_inter_device_drawings([conn])
        assert len(drawings) == 1
        d = drawings[0]
        # Exactly two connectors: source and single target
        assert len(d.connectors) == 2
        assert d.connectors[0].designator == "PLC1-J1"
        assert d.connectors[1].designator == "BMU1-J1"
        assert d.connectors[0].pins == ("1", "2")
        assert d.connectors[1].pins == ("1", "2")
        assert len(d.connections) == 2
        assert d.title == "PLC1-J1 <-> BMU1-J1"

    def test_fan_out_three_endpoints_six_wires(self):
        """Fan-out IDC with 3 targets and 6 wires (2 per target) renders as one drawing."""
        conn = InterDeviceConnection(
            from_device="PLC1",
            from_connector="J1",
            to_endpoints=(
                CableTargetEndpoint(device="BMU1", connector="J1"),
                CableTargetEndpoint(device="BMU2", connector="J1"),
                CableTargetEndpoint(device="BMU3", connector="J1"),
            ),
            cable=CableData(
                wire_gauge=0.75, wire_colors=("BN", "BU", "GN", "YE", "RD", "WH")
            ),
            wires=(
                WireSpec(from_pin="1", to_endpoint=0, to_pin="A"),
                WireSpec(from_pin="2", to_endpoint=0, to_pin="B"),
                WireSpec(from_pin="3", to_endpoint=1, to_pin="A"),
                WireSpec(from_pin="4", to_endpoint=1, to_pin="B"),
                WireSpec(from_pin="5", to_endpoint=2, to_pin="A"),
                WireSpec(from_pin="6", to_endpoint=2, to_pin="B"),
            ),
        )
        drawings = build_inter_device_drawings([conn])
        assert len(drawings) == 1
        d = drawings[0]

        # ONE drawing regardless of fan-out degree
        assert d.cable.wirecount == 6

        # Source connector has all 6 from_pins
        assert d.connectors[0].designator == "PLC1-J1"
        assert d.connectors[0].pins == ("1", "2", "3", "4", "5", "6")

        # Three target connectors, one per endpoint
        assert len(d.connectors) == 4  # source + 3 targets
        target_des = [c.designator for c in d.connectors[1:]]
        assert target_des == ["BMU1-J1", "BMU2-J1", "BMU3-J1"]

        # Each target connector gets 2 pins
        assert d.connectors[1].pins == ("A", "B")
        assert d.connectors[2].pins == ("A", "B")
        assert d.connectors[3].pins == ("A", "B")

        # 6 CableConnection entries, wire numbers 1..6
        assert len(d.connections) == 6
        assert [c.wire for c in d.connections] == [1, 2, 3, 4, 5, 6]

        # Correct routing per wire
        assert d.connections[0].to_connector == "BMU1-J1"
        assert d.connections[0].to_pin == "A"
        assert d.connections[2].to_connector == "BMU2-J1"
        assert d.connections[4].to_connector == "BMU3-J1"

        # Title names all three targets
        assert "BMU1-J1" in d.title
        assert "BMU2-J1" in d.title
        assert "BMU3-J1" in d.title

    def test_fan_out_title_format(self):
        """Title is 'from <-> t0, t1, t2' for fan-out."""
        conn = InterDeviceConnection(
            from_device="SRC",
            from_connector="J1",
            to_endpoints=(
                CableTargetEndpoint(device="T1", connector="J1"),
                CableTargetEndpoint(device="T2", connector="J1"),
            ),
            cable=CableData(wire_gauge=1.0),
            wires=(
                WireSpec(from_pin="1", to_endpoint=0, to_pin="1"),
                WireSpec(from_pin="2", to_endpoint=1, to_pin="1"),
            ),
        )
        drawings = build_inter_device_drawings([conn])
        assert drawings[0].title == "SRC-J1 <-> T1-J1, T2-J1"

    def test_wire_spec_invalid_endpoint_raises(self):
        """WireSpec.to_endpoint out of range raises CableError."""
        conn = InterDeviceConnection(
            from_device="SRC",
            from_connector="J1",
            to_endpoints=(CableTargetEndpoint(device="T1", connector="J1"),),
            cable=CableData(wire_gauge=1.0),
            wires=(
                WireSpec(from_pin="1", to_endpoint=0, to_pin="1"),
                WireSpec(
                    from_pin="2", to_endpoint=1, to_pin="1"
                ),  # index 1 out of range
            ),
        )
        with pytest.raises(CableError, match="out of range"):
            build_inter_device_drawings([conn])

    def test_fan_out_with_connector_data_on_endpoints(self):
        """connector_data on CableTargetEndpoint is applied to the rendered connector."""
        ep_cd = ConnectorData(pins=(), type="M12", subtype="female")
        conn = InterDeviceConnection(
            from_device="SRC",
            from_connector="J1",
            to_endpoints=(
                CableTargetEndpoint(device="T1", connector="J1", connector_data=ep_cd),
                CableTargetEndpoint(device="T2", connector="J1"),
            ),
            cable=CableData(wire_gauge=1.0),
            wires=(
                WireSpec(from_pin="1", to_endpoint=0, to_pin="A"),
                WireSpec(from_pin="2", to_endpoint=1, to_pin="A"),
            ),
        )
        drawings = build_inter_device_drawings([conn])
        d = drawings[0]
        t1_connector = next(c for c in d.connectors if c.designator == "T1-J1")
        assert t1_connector.type == "M12"
        assert t1_connector.subtype == "female"


class TestWireSpecNetName:
    """WireSpec.net_name plumbs through to CableDef.wirelabels."""

    def test_net_name_defaults_to_none(self):
        ws = WireSpec(from_pin="1", to_endpoint=0, to_pin="1")
        assert ws.net_name is None

    def test_net_name_accepts_string(self):
        ws = WireSpec(from_pin="1", to_endpoint=0, to_pin="1", net_name="V24")
        assert ws.net_name == "V24"

    def test_wires_none_path_leaves_wirelabels_empty(self):
        """Simple 1:1 path (wires=None) gets default empty wirelabels."""
        conn = InterDeviceConnection(
            from_device="PLC1",
            from_connector="J1",
            to_endpoints=(CableTargetEndpoint(device="BMU1", connector="J1"),),
            cable=CableData(wire_gauge=1.5, wire_colors=("BN", "BU")),
        )
        drawings = build_inter_device_drawings([conn])
        assert drawings[0].cable.wirelabels == ()

    def test_fan_out_populates_wirelabels_in_order(self):
        """Fan-out path copies net_name from each WireSpec in wire order."""
        conn = InterDeviceConnection(
            from_device="PLC1",
            from_connector="J1",
            to_endpoints=(
                CableTargetEndpoint(device="BMU1", connector="J1"),
                CableTargetEndpoint(device="BMU2", connector="J1"),
            ),
            cable=CableData(wire_gauge=0.75, wire_colors=("BN", "BU", "GN", "YE")),
            wires=(
                WireSpec(from_pin="1", to_endpoint=0, to_pin="A", net_name="V24"),
                WireSpec(from_pin="2", to_endpoint=0, to_pin="B", net_name="GND"),
                WireSpec(from_pin="3", to_endpoint=1, to_pin="A", net_name="CAN_H"),
                WireSpec(from_pin="4", to_endpoint=1, to_pin="B", net_name="CAN_L"),
            ),
        )
        drawings = build_inter_device_drawings([conn])
        assert drawings[0].cable.wirelabels == ("V24", "GND", "CAN_H", "CAN_L")

    def test_fan_out_without_net_names_leaves_wirelabels_empty(self):
        """Fan-out with no net_name on any WireSpec keeps wirelabels empty (default unchanged)."""
        conn = InterDeviceConnection(
            from_device="SRC",
            from_connector="J1",
            to_endpoints=(CableTargetEndpoint(device="T1", connector="J1"),),
            cable=CableData(wire_gauge=1.0),
            wires=(
                WireSpec(from_pin="1", to_endpoint=0, to_pin="1"),
                WireSpec(from_pin="2", to_endpoint=0, to_pin="2"),
            ),
        )
        drawings = build_inter_device_drawings([conn])
        assert drawings[0].cable.wirelabels == ()

    def test_fan_out_mixed_net_names_preserves_none_slots(self):
        """Partial net_name coverage: unlabelled wires keep None in their slot."""
        conn = InterDeviceConnection(
            from_device="SRC",
            from_connector="J1",
            to_endpoints=(CableTargetEndpoint(device="T1", connector="J1"),),
            cable=CableData(wire_gauge=1.0),
            wires=(
                WireSpec(from_pin="1", to_endpoint=0, to_pin="1", net_name="V24"),
                WireSpec(from_pin="2", to_endpoint=0, to_pin="2"),
                WireSpec(from_pin="3", to_endpoint=0, to_pin="3", net_name="GND"),
            ),
        )
        drawings = build_inter_device_drawings([conn])
        assert drawings[0].cable.wirelabels == ("V24", None, "GND")


# ---------------------------------------------------------------------------
# _fmt_des
# ---------------------------------------------------------------------------


class TestFmtDes:
    """Designator formatter drops the dash when the connector part is empty."""

    def test_with_connector(self):
        assert _fmt_des("JB1", "J1") == "JB1-J1"

    def test_empty_connector_no_dash(self):
        assert _fmt_des("X1", "") == "X1"

    def test_empty_both(self):
        assert _fmt_des("", "") == ""


# ---------------------------------------------------------------------------
# CableDrawing.from_designator / to_designators population
# ---------------------------------------------------------------------------


class TestDrawingDesignators:
    """Builder populates from_designator + to_designators for TOC rendering."""

    def test_inter_device_simple_path(self):
        conn = InterDeviceConnection(
            from_device="PLC1",
            from_connector="J1",
            to_endpoints=(CableTargetEndpoint(device="BMU1", connector="J1"),),
            cable=CableData(wire_gauge=1.5, wire_colors=("BN", "BU")),
        )
        d = build_inter_device_drawings([conn])[0]
        assert d.from_designator == "PLC1-J1"
        assert d.to_designators == ("BMU1-J1",)

    def test_inter_device_simple_empty_connector_strips_dash(self):
        conn = InterDeviceConnection(
            from_device="X1",
            from_connector="",
            to_endpoints=(CableTargetEndpoint(device="Q1", connector=""),),
            cable=CableData(wire_gauge=1.5, wire_colors=("BN",)),
        )
        d = build_inter_device_drawings([conn])[0]
        assert d.from_designator == "X1"
        assert d.to_designators == ("Q1",)

    def test_inter_device_fan_out(self):
        conn = InterDeviceConnection(
            from_device="PLC1",
            from_connector="J1",
            to_endpoints=(
                CableTargetEndpoint(device="BMU1", connector="J1"),
                CableTargetEndpoint(device="BMU2", connector="J1"),
                CableTargetEndpoint(device="BMU3", connector="J1"),
            ),
            cable=CableData(wire_gauge=0.75),
            wires=(
                WireSpec(from_pin="1", to_endpoint=0, to_pin="A"),
                WireSpec(from_pin="2", to_endpoint=1, to_pin="A"),
                WireSpec(from_pin="3", to_endpoint=2, to_pin="A"),
            ),
        )
        d = build_inter_device_drawings([conn])[0]
        assert d.from_designator == "PLC1-J1"
        assert d.to_designators == ("BMU1-J1", "BMU2-J1", "BMU3-J1")

    def test_field_device_single_cable(self):
        t = Terminal("X1", "Power")
        drawings = build_cable_drawings(
            external_connections=[
                ("M1", "U", t, "1", "", ""),
                ("M1", "V", t, "2", "", ""),
            ],
            field_devices=[],
        )
        d = drawings[0]
        assert d.from_designator == "M1"
        assert d.to_designators == ("X1",)


# ---------------------------------------------------------------------------
# _sort_synthesized_pins
# ---------------------------------------------------------------------------


class TestSortSynthesizedPins:
    def test_all_integer_sort_int_true(self):
        """All-integer pins, sort_integer_pins=True: ascending numeric order."""
        result = _sort_synthesized_pins(
            ("6", "9", "7", "8"), sort_integers=True, sort_alphabetic=False
        )
        assert result == ("6", "7", "8", "9")

    def test_all_integer_sort_int_false(self):
        """All-integer pins, sort_integer_pins=False: wire-traversal order preserved."""
        result = _sort_synthesized_pins(
            ("6", "9", "7", "8"), sort_integers=False, sort_alphabetic=False
        )
        assert result == ("6", "9", "7", "8")

    def test_all_non_integer_sort_alph_true(self):
        """All non-integer pins, sort_alphabetic_pins=True: lexicographic order."""
        result = _sort_synthesized_pins(
            ("PE", "L", "N"), sort_integers=False, sort_alphabetic=True
        )
        assert result == ("L", "N", "PE")

    def test_all_non_integer_sort_alph_false(self):
        """All non-integer pins, sort_alphabetic_pins=False: wire-traversal order."""
        result = _sort_synthesized_pins(
            ("PE", "L", "N"), sort_integers=False, sort_alphabetic=False
        )
        assert result == ("PE", "L", "N")

    def test_mixed_int_true_alph_false(self):
        """Mixed pins, int=True alph=False: sorted ints first, then non-ints in wire order."""
        result = _sort_synthesized_pins(
            ("L", "N", "PE", "2", "1"), sort_integers=True, sort_alphabetic=False
        )
        assert result == ("1", "2", "L", "N", "PE")

    def test_mixed_int_false_alph_true(self):
        """Mixed pins, int=False alph=True: ints in wire order first, then sorted non-ints."""
        result = _sort_synthesized_pins(
            ("L", "N", "PE", "2", "1"), sort_integers=False, sort_alphabetic=True
        )
        assert result == ("2", "1", "L", "N", "PE")

    def test_mixed_both_true(self):
        """Mixed pins, both=True: sorted ints first, then sorted non-ints."""
        result = _sort_synthesized_pins(
            ("L", "N", "PE", "2", "1"), sort_integers=True, sort_alphabetic=True
        )
        assert result == ("1", "2", "L", "N", "PE")

    def test_mixed_both_false(self):
        """Mixed pins, both=False: ints in wire order, then non-ints in wire order."""
        result = _sort_synthesized_pins(
            ("L", "N", "PE", "2", "1"), sort_integers=False, sort_alphabetic=False
        )
        assert result == ("2", "1", "L", "N", "PE")

    def test_empty_tuple(self):
        assert (
            _sort_synthesized_pins((), sort_integers=True, sort_alphabetic=True) == ()
        )

    def test_integers_sort_numerically_not_lexicographically(self):
        """'9' < '10' numerically; lexicographic would give '10' < '9'."""
        result = _sort_synthesized_pins(
            ("10", "9", "2"), sort_integers=True, sort_alphabetic=False
        )
        assert result == ("2", "9", "10")


# ---------------------------------------------------------------------------
# Pin synthesis from WireSpec pins (Change A) and sort flags (Change B)
# ---------------------------------------------------------------------------


class TestSynthesizedPinSortingFieldDevice:
    """Synthesized target connector pins derive from wire triples and are sorted."""

    def test_target_pins_from_wire_data_not_sequential(self):
        """Target connector pins are the actual terminal_pins, not 1..N."""
        t = Terminal("X1", "Power")
        # external_connections format: (device_tag, device_pin, terminal_obj, terminal_pin, ...)
        # Wires connect to terminal pins 9,6,7,8 in that order
        drawings = build_cable_drawings(
            external_connections=[
                ("M1", "U", t, "9", "", ""),
                ("M1", "V", t, "6", "", ""),
                ("M1", "W", t, "7", "", ""),
                ("M1", "PE", t, "8", "", ""),
            ],
            field_devices=[],
            pins_last=(),
        )
        target = drawings[0].connectors[1]
        # sort_integer_pins=True (default): ascending 6,7,8,9
        assert target.pins == ("6", "7", "8", "9")

    def test_target_pins_sort_integer_false_preserves_wire_order(self):
        """sort_integer_pins=False: pins keep wire-traversal order."""
        t = Terminal("X1", "Power")
        drawings = build_cable_drawings(
            external_connections=[
                ("M1", "U", t, "9", "", ""),
                ("M1", "V", t, "6", "", ""),
                ("M1", "W", t, "7", "", ""),
            ],
            field_devices=[],
            pins_last=(),
            sort_integer_pins=False,
        )
        target = drawings[0].connectors[1]
        assert target.pins == ("9", "6", "7")

    def test_target_pins_mixed_sort_int_true(self):
        """Mixed target pins: ints sorted ascending first, then non-ints in wire order."""
        t = Terminal("X1", "Power")
        drawings = build_cable_drawings(
            external_connections=[
                ("M1", "L", t, "L", "", ""),
                ("M1", "N", t, "N", "", ""),
                ("M1", "PE", t, "PE", "", ""),
                ("M1", "2", t, "2", "", ""),
                ("M1", "1", t, "1", "", ""),
            ],
            field_devices=[],
            pins_last=(),
            sort_integer_pins=True,
            sort_alphabetic_pins=False,
        )
        target = drawings[0].connectors[1]
        assert target.pins == ("1", "2", "L", "N", "PE")

    def test_source_connector_data_skips_target_sort(self):
        """ConnectorData on source does not affect target connector pin sorting."""
        from schematika.electrical.field_devices import (
            DeviceTemplate,
            PinDef,
        )

        t = Terminal("X1", "Power")
        template = DeviceTemplate(mpn="motor", pins=(PinDef("U", t),))
        connector = ConnectorData(pins=(), type="M12")
        device = FieldDevice(
            tag="M1",
            template=template,
            terminal=t,
            connectors=(connector,),
        )
        drawings = build_cable_drawings(
            external_connections=[
                ("M1", "U", t, "9", "", ""),
                ("M1", "V", t, "6", "", ""),
                ("M1", "W", t, "7", "", ""),
            ],
            field_devices=[device],
            sort_integer_pins=True,
            pins_last=(),
        )
        # Target connector pins should still be sorted (source has ConnectorData, target does not)
        target = drawings[0].connectors[1]
        assert target.pins == ("6", "7", "9")


class TestSynthesizedPinSortingInterDevice:
    """Fan-out IDC synthesized pins sorted; explicit connector_data verbatim."""

    def test_fan_out_target_pins_sorted_ascending(self):
        """Fan-out: to_pin values sorted ascending when sort_integer_pins=True."""
        conn = InterDeviceConnection(
            from_device="PLC1",
            from_connector="J1",
            to_endpoints=(CableTargetEndpoint(device="BMU1", connector="J1"),),
            cable=CableData(wire_gauge=0.75),
            wires=(
                WireSpec(from_pin="1", to_endpoint=0, to_pin="9"),
                WireSpec(from_pin="2", to_endpoint=0, to_pin="6"),
                WireSpec(from_pin="3", to_endpoint=0, to_pin="7"),
                WireSpec(from_pin="4", to_endpoint=0, to_pin="8"),
            ),
        )
        drawings = build_inter_device_drawings([conn], sort_integer_pins=True)
        target = drawings[0].connectors[1]
        assert target.pins == ("6", "7", "8", "9")

    def test_fan_out_target_pins_wire_order_when_sort_int_false(self):
        """Fan-out: to_pin values in wire order when sort_integer_pins=False."""
        conn = InterDeviceConnection(
            from_device="PLC1",
            from_connector="J1",
            to_endpoints=(CableTargetEndpoint(device="BMU1", connector="J1"),),
            cable=CableData(wire_gauge=0.75),
            wires=(
                WireSpec(from_pin="1", to_endpoint=0, to_pin="9"),
                WireSpec(from_pin="2", to_endpoint=0, to_pin="6"),
                WireSpec(from_pin="3", to_endpoint=0, to_pin="7"),
            ),
        )
        drawings = build_inter_device_drawings([conn], sort_integer_pins=False)
        target = drawings[0].connectors[1]
        assert target.pins == ("9", "6", "7")

    def test_fan_out_connector_data_skips_sort(self):
        """When connector_data is set, to_pin wire values are used verbatim (no sort)."""
        ep_cd = ConnectorData(pins=(), type="M12")
        conn = InterDeviceConnection(
            from_device="SRC",
            from_connector="J1",
            to_endpoints=(
                CableTargetEndpoint(device="T1", connector="J1", connector_data=ep_cd),
            ),
            cable=CableData(wire_gauge=1.0),
            wires=(
                WireSpec(from_pin="1", to_endpoint=0, to_pin="9"),
                WireSpec(from_pin="2", to_endpoint=0, to_pin="6"),
                WireSpec(from_pin="3", to_endpoint=0, to_pin="7"),
            ),
        )
        # sort_integer_pins=True but connector_data is set → no sort on that endpoint
        drawings = build_inter_device_drawings([conn], sort_integer_pins=True)
        t1 = next(c for c in drawings[0].connectors if c.designator == "T1-J1")
        # Wire-traversal order preserved (no sort) because connector_data is present
        assert t1.pins == ("9", "6", "7")

    def test_simple_path_synthesized_pins_sorted(self):
        """Simple 1:1 path: wire_colors-synthesized pins sorted when sort_integer_pins=True."""
        conn = InterDeviceConnection(
            from_device="A",
            from_connector="J1",
            to_endpoints=(CableTargetEndpoint(device="B", connector="J2"),),
            cable=CableData(wire_gauge=1.5, wire_colors=("BN", "BU", "GNYE")),
        )
        drawings = build_inter_device_drawings([conn], sort_integer_pins=True)
        # Synthesized pins are "1","2","3" — sorted ascending (same order)
        assert drawings[0].connectors[0].pins == ("1", "2", "3")
        assert drawings[0].connectors[1].pins == ("1", "2", "3")


class TestProjectSortFlags:
    """Project.__init__ sort flags default and propagate to cable_pages."""

    def test_defaults(self):
        from schematika import Project

        p = Project()
        assert p.sort_integer_pins is True
        assert p.sort_alphabetic_pins is False

    def test_explicit_values(self):
        from schematika import Project

        p = Project(sort_integer_pins=False, sort_alphabetic_pins=True)
        assert p.sort_integer_pins is False
        assert p.sort_alphabetic_pins is True
