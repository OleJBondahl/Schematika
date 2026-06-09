"""Tests for schematika.overview.validate."""

import dataclasses

from schematika.overview.extract import graph_from_input
from schematika.overview.inputs import OverviewInput, OverviewWire
from schematika.overview.validate import validate_overview_graph


def _inp(wires, *, field=frozenset(), term=frozenset()):
    return OverviewInput(
        wires=tuple(OverviewWire(a=a, b=b, label=lbl) for a, b, lbl in wires),
        field_device_tags=field,
        terminal_tags=term,
        title="T",
    )


def test_complete_graph_validates() -> None:
    inp = _inp(
        [("X1..1", "M1..1", None)], field=frozenset({"M1"}), term=frozenset({"X1"})
    )
    g = graph_from_input(inp)
    rep = validate_overview_graph(g, inp)
    assert rep.ok is True
    assert rep.problems == ()


def test_missing_device_node_flagged() -> None:
    inp = _inp(
        [("X1..1", "M1..1", None)], field=frozenset({"M1"}), term=frozenset({"X1"})
    )
    g = graph_from_input(inp)
    g2 = dataclasses.replace(g, devices=tuple(d for d in g.devices if d.id != "M1"))
    rep = validate_overview_graph(g2, inp)
    assert rep.ok is False
    assert any("M1" in p for p in rep.problems)


def test_orphan_pin_flagged() -> None:
    inp = _inp(
        [("X1..1", "M1..1", None)], field=frozenset({"M1"}), term=frozenset({"X1"})
    )
    g = graph_from_input(inp)
    bad_pin = dataclasses.replace(g.pins[0], signal_id=999)
    g2 = dataclasses.replace(g, pins=(bad_pin, *g.pins[1:]))
    rep = validate_overview_graph(g2, inp)
    assert not rep.ok
    assert any("orphan pin" in p for p in rep.problems)


def test_edge_wire_count_mismatch_flagged() -> None:
    inp = _inp(
        [("X1..1", "M1..1", None)], field=frozenset({"M1"}), term=frozenset({"X1"})
    )
    g = graph_from_input(inp)
    g2 = dataclasses.replace(g, edges=())
    rep = validate_overview_graph(g2, inp)
    assert not rep.ok
    assert any("edge_count" in p for p in rep.problems)


def test_problems_are_deterministic() -> None:
    inp = _inp(
        [("X1..1", "M1..1", None)], field=frozenset({"M1"}), term=frozenset({"X1"})
    )
    g = graph_from_input(inp)
    # Break it: remove M1, drop edges, orphan a pin
    g2 = dataclasses.replace(
        g,
        devices=tuple(d for d in g.devices if d.id != "M1"),
        edges=(),
    )
    rep1 = validate_overview_graph(g2, inp)
    rep2 = validate_overview_graph(g2, inp)
    assert rep1.problems == rep2.problems
