"""Unit tests for schematika.pcb.overview_adapter."""

import skidl
from skidl import Circuit, Net, Part, Pin

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

    assert result == (("JB1", "GND", ("JB1.F1.1", "JB1.F2.1")),)


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
