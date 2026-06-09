"""Fixtures for overview unit tests."""

import pytest

from schematika.catalog import PinRef
from schematika.catalog.identifiers import DeviceTag, NetId
from schematika.project import Project


def _make_project() -> Project:
    """Minimal Project: one route (K1.A1 -> X1.3) and one field-device wire."""
    from schematika.catalog.wires import Wire

    p = Project(title="Test Panel")

    # One route: K1 pin A1 -> terminal X1 pin 3
    p.route(
        PinRef(device=DeviceTag("K1"), port_id="A1"),
        PinRef(device=DeviceTag("X1"), port_id="3"),
        net=NetId("NET_K1"),
    )

    # One extra wire representing a field-device connection (FD1 -> X1.5)
    p.add_wires(
        [
            Wire(
                net=NetId("NET_FD1"),
                source=PinRef(device=DeviceTag("FD1"), port_id="1"),
                target=PinRef(device=DeviceTag("X1"), port_id="5"),
            )
        ]
    )

    return p


@pytest.fixture
def small_project() -> Project:
    """Built Project with at least one route wire and one field-device wire."""
    p = _make_project()
    p.build_circuits()
    return p


@pytest.fixture
def unbuilt_project() -> Project:
    """Project with declarations but build_circuits() not yet called."""
    return _make_project()
