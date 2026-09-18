"""Tests for schematika.overview.inputs.OverviewInput's PCB/fuse/relay fields."""

from schematika.overview.inputs import OverviewInput


def test_overview_input_pcb_fields_default_empty() -> None:
    inp = OverviewInput(
        wires=(), field_device_tags=frozenset(), terminal_tags=frozenset()
    )
    assert inp.pcb_nets == ()
    assert inp.fuse_links == ()
    assert inp.relay_contacts == ()
    assert inp.relay_pins == {}


def test_overview_input_accepts_pcb_fields() -> None:
    inp = OverviewInput(
        wires=(),
        field_device_tags=frozenset(),
        terminal_tags=frozenset(),
        pcb_nets=(("JB1", "GND", ("JB1.F1.1", "JB1.K1.A1")),),
        fuse_links=(("JB1.F1.fuse", "JB1.F1.1", "JB1.F1.2", None),),
        relay_contacts=(("JB1.K1.c0", "K1", "JB1.K1.11", "JB1.K1.14"),),
        relay_pins={
            "JB1.K1": {
                "coil": ["JB1.K1.A1"],
                "contact": ["JB1.K1.11"],
                "contactPairs": [["JB1.K1.11", "JB1.K1.14"]],
            }
        },
    )
    assert inp.pcb_nets[0][1] == "GND"
    assert inp.fuse_links[0][0] == "JB1.F1.fuse"
    assert inp.relay_contacts[0][1] == "K1"
    assert inp.relay_pins["JB1.K1"]["coil"] == ["JB1.K1.A1"]
