"""Tests for the Route multi-point primitive and route_to_wires."""

import pytest

from schematika.catalog.errors import CatalogValidationError
from schematika.catalog.identifiers import DeviceTag, NetId
from schematika.catalog.refs import PinRef
from schematika.catalog.routes import Route, route_to_wires


def _pin(device, port):
    return PinRef(device=DeviceTag(device), port_id=port)


def test_route_to_wires_three_points_two_wires():
    a, t, p = _pin("-M1", "U"), _pin("X100", "1"), _pin("PLC-DI1", "3")
    wires = route_to_wires(Route(net=NetId("M1_U"), waypoints=(a, t, p)))
    assert len(wires) == 2
    assert wires[0].source is a
    assert wires[0].target is t
    assert wires[1].source is t
    assert wires[1].target is p
    assert all(w.net == "M1_U" for w in wires)


def test_route_to_wires_two_points_one_wire():
    a, b = _pin("-M1", "U"), _pin("X100", "1")
    wires = route_to_wires(Route(net=NetId("n"), waypoints=(a, b)))
    assert len(wires) == 1


def test_route_rejects_fewer_than_two_waypoints():
    with pytest.raises(CatalogValidationError):
        Route(net=NetId("n"), waypoints=(_pin("-M1", "U"),))
    with pytest.raises(CatalogValidationError):
        Route(net=NetId("n"), waypoints=())


def test_route_exported_from_package():
    from schematika.catalog import Route as PkgRoute
    from schematika.catalog import route_to_wires as pkg_rtw

    assert PkgRoute is Route
    assert pkg_rtw is route_to_wires
