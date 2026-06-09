"""Tests for schematika.overview.model graph construction."""

from schematika.overview.model import (
    UnionFind,
    build_graph,
    classify_net,
    device_class,
    pin_id,
)

# ---------------------------------------------------------------------------
# Unit helpers
# ---------------------------------------------------------------------------


def test_classify_net_can_before_power() -> None:
    # "CAN_pwr" contains both "can" and "pwr" — CAN wins because it is checked first
    assert classify_net("CAN_pwr") == "CAN"
    assert classify_net("pwr24") == "power"
    assert classify_net("GND") == "GND"
    assert classify_net(None) == "signal"
    assert classify_net("") == "signal"


def test_device_class_strips_trailing_digits() -> None:
    assert device_class("BMU1") == "BMU"
    assert device_class("BMU12") == "BMU"
    assert device_class("CHASSIS") == "CHASSIS"
    assert device_class("X-FUSED") == "X-FUSED"
    # single digit
    assert device_class("A1") == "A"


def test_pin_id_format() -> None:
    assert pin_id("BMU1", "J3", "3") == "BMU1.J3.3"
    # empty connector produces double-dot
    assert pin_id("X1", "", "1") == "X1..1"


def test_union_find_grouping() -> None:
    uf = UnionFind()
    uf.union("a", "b")
    uf.union("b", "c")
    assert uf.find("a") == uf.find("c")
    uf.add("d")
    assert uf.find("d") != uf.find("a")


# ---------------------------------------------------------------------------
# build_graph integration
# ---------------------------------------------------------------------------


def test_build_graph_shared_pin_one_signal() -> None:
    """Two wires sharing a pin must produce ONE signal."""
    wires = [
        ("A1.J1.1", "B1.J1.1", "pwr24"),
        ("A1.J1.1", "C1.J1.1", "pwr24"),
    ]
    g = build_graph(wires, [], [], [], {})
    pins_by_id = {p.id: p for p in g.pins}
    # All three pins must share the same signal_id
    assert pins_by_id["A1.J1.1"].signal_id == pins_by_id["B1.J1.1"].signal_id
    assert pins_by_id["A1.J1.1"].signal_id == pins_by_id["C1.J1.1"].signal_id
    # The shared signal should be net_class "power"
    sig_id = pins_by_id["A1.J1.1"].signal_id
    sig = next(s for s in g.signals if s.id == sig_id)
    assert sig.net_class == "power"


def test_to_dict_meta_and_top_level_keys() -> None:
    """to_dict() must emit version 2 meta and all 7 top-level keys."""
    wires = [("A1.J1.1", "B1.J1.1", "pwr24")]
    g = build_graph(wires, [], [], [], {})
    d = g.to_dict()
    assert d["meta"] == {"version": "2", "maxVisibleEdgeBudget": 250}
    for key in ("pins", "edges", "signals", "compound", "nets", "metaEdges", "meta"):
        assert key in d, f"missing top-level key: {key}"


def test_to_dict_compound_sub_keys() -> None:
    """compound must have exactly the 4 sub-keys."""
    wires = [("A1.J1.1", "B1.J1.1", "pwr24")]
    d = build_graph(wires, [], [], [], {}).to_dict()
    compound = d["compound"]
    for key in ("devices", "connectors", "relays", "fuses"):
        assert key in compound, f"compound missing: {key}"


def test_to_dict_pins_share_signal_id() -> None:
    """Both pins on a shared-pin wire group must emit the same signalId."""
    wires = [
        ("A1.J1.1", "B1.J1.1", "pwr24"),
        ("A1.J1.1", "C1.J1.1", "pwr24"),
    ]
    d = build_graph(wires, [], [], [], {}).to_dict()
    by_id = {p["id"]: p for p in d["pins"]}
    assert by_id["A1.J1.1"]["signalId"] == by_id["B1.J1.1"]["signalId"]
    assert by_id["A1.J1.1"]["signalId"] == by_id["C1.J1.1"]["signalId"]


def test_to_dict_can_edge_meta_edge() -> None:
    """A CAN harness edge must have netClass 'CAN' and a populated metaEdge key."""
    wires = [("A1.J1.1", "B1.J1.1", "CAN_H")]
    d = build_graph(wires, [], [], [], {}).to_dict()
    edges = d["edges"]
    assert len(edges) == 1
    e = edges[0]
    assert e["netClass"] == "CAN"
    assert e["metaEdge"] == "meta:A1|B1"


def test_harness_edge_no_relay_state_keys() -> None:
    """Harness edges must NOT include relay/state/signalA/signalB keys."""
    wires = [("A1.J1.1", "B1.J1.1", "signal_x")]
    d = build_graph(wires, [], [], [], {}).to_dict()
    e = d["edges"][0]
    for forbidden in ("relay", "state", "signalA", "signalB"):
        assert forbidden not in e, f"harness edge should not have key: {forbidden}"


def test_relay_contact_edge_signal_ab_keys() -> None:
    """relay-contact edges must carry signalA and signalB, not signalId."""
    wires = [
        ("A1.J1.1", "B1.J1.1", "pwr24"),
        ("A1.J1.2", "B1.J1.2", "pwr24"),
    ]
    relay_contacts = [("rc:K1.1", "A1.J1.1", "A1.J1.2", "K1")]
    relay_pins: dict = {
        "K1": {
            "coil": ("A1.J1.1",),
            "contact": ("A1.J1.2",),
            "contactPairs": [("A1.J1.1", "A1.J1.2")],
        }
    }
    d = build_graph(wires, [], [], relay_contacts, relay_pins).to_dict()
    rc_edges = [e for e in d["edges"] if e["kind"] == "relay-contact"]
    assert len(rc_edges) == 1
    rc = rc_edges[0]
    assert "signalA" in rc
    assert "signalB" in rc
    assert "signalId" not in rc
