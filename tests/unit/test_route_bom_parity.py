"""R3.5: route() counts the same terminal pins the legacy tuple path did.

Regression for the aux_v3 R4 PDF-diff: a route whose OTHER end has an empty pin
must still count the FIRST waypoint's (key terminal) pin in the BOM. Before the
fix, _wires_to_terminal_rows anchored the key terminal in cols [0]/[1], so
_count_terminal_pins (which reads cols [2]/[3]) counted the empty far pin and
undercounted the terminal block.

The frozen expectation below was captured from the legacy ``internal_wiring()``
reference path before it was deleted.
"""

from schematika.catalog.identifiers import DeviceTag
from schematika.catalog.refs import PinRef
from schematika.project import Project


def test_route_counts_frozen_terminal_pins() -> None:
    routed = Project().route(
        PinRef(device=DeviceTag("X1"), port_id="1"),
        PinRef(device=DeviceTag("X2"), port_id=""),
    )
    routed._resolve_routes()

    # The key terminal pin X1:1 must be counted (the regression dropped it).
    assert dict(routed._count_terminal_pins()) == {"X1": 1}
