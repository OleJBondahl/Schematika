"""Tests for schematika.overview.merge.merge_inputs."""

from schematika.overview.inputs import OverviewInput, OverviewWire
from schematika.overview.merge import merge_inputs


def test_merge_combines_wires_from_both_inputs() -> None:
    a = OverviewInput(
        wires=(OverviewWire(a="X1..1", b="M1..1", label=None),),
        field_device_tags=frozenset({"M1"}),
        terminal_tags=frozenset({"X1"}),
    )
    b = OverviewInput(
        wires=(OverviewWire(a="X2..1", b="M2..1", label=None),),
        field_device_tags=frozenset({"M2"}),
        terminal_tags=frozenset({"X2"}),
    )
    merged = merge_inputs(a, b)
    assert set(merged.wires) == {a.wires[0], b.wires[0]}
    assert merged.field_device_tags == {"M1", "M2"}
    assert merged.terminal_tags == {"X1", "X2"}


def test_merge_combines_pcb_and_relay_fields() -> None:
    pcb = OverviewInput(
        wires=(),
        field_device_tags=frozenset(),
        terminal_tags=frozenset(),
        pcb_nets=(("JB1", "GND", ("JB1.F1.1",)),),
        fuse_links=(("JB1.F1.fuse", "JB1.F1.1", "JB1.F1.2", None),),
        relay_contacts=(("JB1.K1.c0", "K1", "JB1.K1.11", "JB1.K1.14"),),
        relay_pins={
            "JB1.K1": {"coil": ["JB1.K1.A1"], "contact": [], "contactPairs": []}
        },
    )
    harness = OverviewInput(
        wires=(OverviewWire(a="X1..1", b="JB1.F1.1", label=None),),
        field_device_tags=frozenset(),
        terminal_tags=frozenset({"X1"}),
    )
    merged = merge_inputs(pcb, harness)
    assert merged.pcb_nets == pcb.pcb_nets
    assert merged.fuse_links == pcb.fuse_links
    assert merged.relay_contacts == pcb.relay_contacts
    assert merged.relay_pins == pcb.relay_pins
    assert harness.wires[0] in merged.wires


def test_merge_deduplicates_identical_wires() -> None:
    w = OverviewWire(a="X1..1", b="M1..1", label=None)
    a = OverviewInput(
        wires=(w,), field_device_tags=frozenset(), terminal_tags=frozenset()
    )
    b = OverviewInput(
        wires=(w,), field_device_tags=frozenset(), terminal_tags=frozenset()
    )
    merged = merge_inputs(a, b)
    assert len(merged.wires) == 1


def test_merge_title_takes_first_non_default() -> None:
    a = OverviewInput(
        wires=(),
        field_device_tags=frozenset(),
        terminal_tags=frozenset(),
        title="System Overview",
    )
    b = OverviewInput(
        wires=(),
        field_device_tags=frozenset(),
        terminal_tags=frozenset(),
        title="Juicebox",
    )
    assert merge_inputs(a, b).title == "Juicebox"
    assert merge_inputs(b, a).title == "Juicebox"


def test_merge_single_input_is_a_no_op() -> None:
    a = OverviewInput(
        wires=(OverviewWire(a="X1..1", b="M1..1", label=None),),
        field_device_tags=frozenset({"M1"}),
        terminal_tags=frozenset({"X1"}),
    )
    assert merge_inputs(a) == a
