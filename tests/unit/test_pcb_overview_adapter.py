"""Unit tests for schematika.pcb.overview_adapter."""

import skidl
from skidl import Circuit, Net, Part, Pin

from schematika.overview.extract import graph_from_input
from schematika.overview.inputs import OverviewInput, OverviewWire
from schematika.overview.merge import merge_inputs
from schematika.overview.model import build_graph, pin_id
from schematika.pcb.adapter import adapt
from schematika.pcb.overview_adapter import pcb_nets_for_board


def _fresh_circuit() -> Circuit:
    return Circuit()


def _make_fuse_template() -> Part:
    return Part(
        name="Fuse",
        ref_prefix="F",
        pins=[Pin(num="1", name=""), Pin(num="2", name="")],
        dest=skidl.TEMPLATE,
        tool=skidl.SKIDL,  # ty: ignore[unresolved-attribute]
    )


def test_pcb_nets_for_board_shapes_net_as_board_qualified_pin_ids() -> None:
    c = _fresh_circuit()
    fuse_template = _make_fuse_template()
    f1 = fuse_template(ref="F1", circuit=c)
    f2 = fuse_template(ref="F2", circuit=c)
    net = Net("GND", circuit=c)
    net += f1["1"], f2["1"]

    ir = adapt(c)
    result = pcb_nets_for_board(ir, "JB1")

    board, net_name, pins = result[0]
    assert board == "JB1"
    assert net_name == "GND"
    assert set(pins) == {"JB1.F1.1", "JB1.F2.1"}
    assert (
        pin_id("JB1", "F1", "1") in pins
    )  # locks pin-id format to the canonical convention


def test_pcb_nets_for_board_preserves_net_order_and_all_nets() -> None:
    c = _fresh_circuit()
    fuse_template = _make_fuse_template()
    f1 = fuse_template(ref="F1", circuit=c)
    f2 = fuse_template(ref="F2", circuit=c)
    net_a = Net("net_A", circuit=c)
    net_a += f1["1"], f2["1"]
    net_b = Net("net_B", circuit=c)
    net_b += f1["2"], f2["2"]

    ir = adapt(c)
    result = pcb_nets_for_board(ir, "JB2")

    assert [r[1] for r in result] == ["net_A", "net_B"]
    assert all(r[0] == "JB2" for r in result)


def test_pcb_nets_for_board_filters_out_pinless_nets() -> None:
    """A declared-but-never-wired net has zero pins and must be dropped.

    Passing it through unfiltered would crash build_graph's Phase 7
    (`members[0]` on an empty tuple) with a bare IndexError.
    """
    c = _fresh_circuit()
    fuse_template = _make_fuse_template()
    f1 = fuse_template(ref="F1", circuit=c)
    f2 = fuse_template(ref="F2", circuit=c)
    wired_net = Net("GND", circuit=c)
    wired_net += f1["1"], f2["1"]
    Net("SPARE", circuit=c)  # created but never connected to any part

    ir = adapt(c)
    result = pcb_nets_for_board(ir, "JB1")

    assert [r[1] for r in result] == ["GND"]  # SPARE is filtered out

    # build_graph must be able to consume the filtered result without raising.
    graph = build_graph([], list(result), [], [], {})
    assert isinstance(graph.pins, tuple)


def test_pcb_nets_stitch_to_harness_through_full_merged_pipeline() -> None:
    """Prove continuity through the real adapt/merge/extract pipeline.

    Exercises adapt() -> pcb_nets_for_board() -> merge_inputs() ->
    graph_from_input(), not just hand-built tuples.
    """
    c = _fresh_circuit()
    fuse_template = _make_fuse_template()
    f1 = fuse_template(ref="F1", circuit=c)
    f2 = fuse_template(ref="F2", circuit=c)
    net = Net("GND", circuit=c)
    net += f1["1"], f2["1"]

    ir = adapt(c)
    pcb_nets = pcb_nets_for_board(ir, "JB1")

    pcb_input = OverviewInput(
        wires=(),
        field_device_tags=frozenset(),
        terminal_tags=frozenset(),
        pcb_nets=pcb_nets,
    )
    harness_input = OverviewInput(
        wires=(OverviewWire(a="X1..1", b="JB1.F1.1", label=None),),
        field_device_tags=frozenset(),
        terminal_tags=frozenset({"X1"}),
    )

    merged = merge_inputs(pcb_input, harness_input)
    graph = graph_from_input(merged)

    sig_of = {p.id: p.signal_id for p in graph.pins}
    assert sig_of["X1..1"] == sig_of["JB1.F1.1"] == sig_of["JB1.F2.1"]
