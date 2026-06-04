"""Tests for Project.route / add_wires and the owned-Harness resolver."""

from schematika.catalog.identifiers import DeviceTag, NetId
from schematika.catalog.refs import PinRef
from schematika.catalog.wires import Wire
from schematika.electrical.harness import Plc
from schematika.electrical.plc_resolver import PlcModuleType
from schematika.project import Project


def _pin(dev, port):
    return PinRef(device=DeviceTag(dev), port_id=port)


def test_route_buffers_and_returns_self():
    p = Project()
    out = p.route(_pin("-M1", "U"), _pin("X1", "1"))
    assert out is p
    assert len(p._route_decls) == 1
    waypoints, net = p._route_decls[0]
    assert net is None
    assert waypoints == (_pin("-M1", "U"), _pin("X1", "1"))


def test_route_records_explicit_net_and_plc_waypoint():
    p = Project()
    p.route(_pin("TT-1", "1"), _pin("X1", "2"), Plc(signal_type="DI"), net=NetId("N"))
    waypoints, net = p._route_decls[0]
    assert net == NetId("N")
    assert waypoints[-1] == Plc(signal_type="DI")


def test_add_wires_buffers_and_returns_self():
    p = Project()
    w = Wire(net=NetId("N1"), source=_pin("A", "1"), target=_pin("B", "2"))
    out = p.add_wires([w])
    assert out is p
    assert p._added_wires == [w]


def _di_rack(channels=4):
    return [
        (
            "DI1",
            PlcModuleType(
                mpn="DI16",
                signal_type="DI",
                channels=channels,
                pins_per_channel=("",),  # single unlabeled signal pin per DI channel
            ),
        )
    ]


def test_resolve_harness_route_to_wires():
    p = Project()
    p.route(_pin("-M1", "U"), _pin("X1", "1"), _pin("X2", "5"))
    result = p._resolve_harness()
    assert len(result.wires) == 2
    assert {str(w.net) for w in result.wires} == {"-M1_U"}
    assert result.plc_assignments == ()


def test_resolve_harness_allocates_plc_against_rack():
    p = Project()
    p.plc_rack(_di_rack())
    p.route(_pin("TT-101", "1"), _pin("X1", "3"), Plc(signal_type="DI"))
    result = p._resolve_harness()
    assert len(result.wires) == 2
    assert len(result.plc_assignments) == 1
    assert result.plc_assignments[0].module == "DI1"


def test_resolve_harness_folds_in_added_wires():
    p = Project()
    p.route(_pin("-M1", "U"), _pin("X1", "1"))  # -> 1 wire
    extra = Wire(net=NetId("CAN_H"), source=_pin("E1", "1"), target=_pin("E2", "2"))
    p.add_wires([extra])
    result = p._resolve_harness()
    assert len(result.wires) == 2
    assert extra in result.wires
    assert result.plc_assignments == ()


def test_resolve_harness_empty_is_empty():
    result = Project()._resolve_harness()
    assert result.wires == ()
    assert result.plc_assignments == ()
