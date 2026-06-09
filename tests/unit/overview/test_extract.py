"""Tests for schematika.overview.extract.graph_from_input."""

from schematika.overview.extract import graph_from_input
from schematika.overview.inputs import OverviewInput, OverviewWire


def _inp(wires, *, field=frozenset(), term=frozenset()):
    return OverviewInput(
        wires=tuple(OverviewWire(a=a, b=b, label=lbl) for a, b, lbl in wires),
        field_device_tags=field,
        terminal_tags=term,
        title="T",
    )


def test_field_devices_collapse_to_field_class() -> None:
    inp = _inp([("X1..1", "M1..1", None)], field={"M1"}, term={"X1"})
    g = graph_from_input(inp)

    devices_by_id = {d.id: d for d in g.devices}
    assert devices_by_id["M1"].device_class == "FIELD"
    assert devices_by_id["X1"].device_class == "X"

    m1_pins = [p for p in g.pins if p.device == "M1"]
    assert m1_pins, "expected at least one pin for M1"
    assert all(p.device_class == "FIELD" for p in m1_pins)


def test_spare_terminal_pins_gap_filled() -> None:
    inp = _inp(
        [("X1..1", "A..1", None), ("X1..3", "A..2", None)],
        term={"X1"},
    )
    g = graph_from_input(inp)

    x1_pins = sorted(p.pin for p in g.pins if p.device == "X1")
    assert x1_pins == ["1", "2", "3"], f"expected ['1','2','3'], got {x1_pins}"

    # Injected pin "2" must have its own signal id distinct from pin "1" and "3"
    pins_by_pin = {p.pin: p for p in g.pins if p.device == "X1"}
    sid_1 = pins_by_pin["1"].signal_id
    sid_2 = pins_by_pin["2"].signal_id
    sid_3 = pins_by_pin["3"].signal_id
    assert sid_2 != sid_1
    assert sid_2 != sid_3


def test_no_spare_injection_for_non_integer_terminal() -> None:
    inp = _inp([("X1..PE", "A..1", None)], term={"X1"})
    g = graph_from_input(inp)

    x1_pins = [p.pin for p in g.pins if p.device == "X1"]
    assert x1_pins == ["PE"], f"expected no injection, got {x1_pins}"


def test_terminal_anchor_orders_by_field_row() -> None:
    inp = _inp(
        [("X1..1", "M1..1", None), ("X2..1", "M2..1", None)],
        field={"M1", "M2"},
        term={"X1", "X2"},
    )
    g = graph_from_input(inp)

    devices_by_id = {d.id: d for d in g.devices}
    x1_anchor = devices_by_id["X1"].anchor
    x2_anchor = devices_by_id["X2"].anchor

    assert x1_anchor is not None
    assert x2_anchor is not None

    # M1 sorts before M2 naturally, so X1 (connected to M1) gets a lower anchor
    # than X2 (connected to M2) — but also accept the reverse if natural sort differs.
    # What matters: the terminal connected to the earlier field device has lower anchor.
    from schematika.overview.extract import _natural_key

    m1_row = sorted(["M1", "M2"], key=_natural_key).index("M1")
    m2_row = sorted(["M1", "M2"], key=_natural_key).index("M2")

    if m1_row < m2_row:
        assert x1_anchor < x2_anchor, (
            f"expected X1.anchor({x1_anchor}) < X2.anchor({x2_anchor})"
        )
    else:
        assert x2_anchor < x1_anchor, (
            f"expected X2.anchor({x2_anchor}) < X1.anchor({x1_anchor})"
        )


def test_unconnected_terminal_gets_sentinel_anchor() -> None:
    # X1 has a pin but no field device on the other side
    inp = _inp([("X1..1", "A..1", None)], term={"X1"})
    g = graph_from_input(inp)

    devices_by_id = {d.id: d for d in g.devices}
    assert devices_by_id["X1"].anchor == 1e9
