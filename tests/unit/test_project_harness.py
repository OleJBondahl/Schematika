"""Tests for Project.route / add_wires and the owned-Harness resolver."""

from schematika.catalog.identifiers import DeviceTag, NetId
from schematika.catalog.refs import PinRef
from schematika.catalog.wires import Wire
from schematika.electrical.harness import Plc
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
