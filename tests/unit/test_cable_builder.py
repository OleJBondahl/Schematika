"""Tests for schematika.cable.builder.

Covers build_cable_drawings and the internal helpers (_reorder_pins_last,
_build_connector_from_override, _build_cable_def, _build_target_connectors).
"""

import pytest

from schematika.cable.builder import (
    _build_cable_def,
    _build_connector_from_override,
    _build_target_connectors,
    _fmt_des,
    _reorder_pins_last,
    _sort_synthesized_pins,
    build_cable_drawings,
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
# Synthesized pin sorting for field-device cables
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
