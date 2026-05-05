"""Tests for schematika.pcb.symbols.power."""

from schematika.pcb.symbols.power import gnd, power_24v


def test_power_24v_has_single_port_named_1() -> None:
    sym = power_24v()
    assert list(sym.ports.keys()) == ["1"]


def test_power_24v_port_is_at_bottom_pointing_up() -> None:
    sym = power_24v()
    port = sym.ports["1"]
    # Port faces upward (chain enters from below)
    assert port.direction.dx == 0
    assert port.direction.dy < 0


def test_power_24v_label_visible() -> None:
    sym = power_24v()
    text_contents = [getattr(el, "content", None) for el in sym.elements]
    assert "+24V" in text_contents


def test_gnd_has_single_port_named_1() -> None:
    sym = gnd()
    assert list(sym.ports.keys()) == ["1"]


def test_gnd_port_is_at_top_pointing_up() -> None:
    sym = gnd()
    port = sym.ports["1"]
    assert port.direction.dx == 0
    # Wire enters from above; symbol hangs below the port
    assert port.direction.dy < 0


def test_gnd_label_visible() -> None:
    sym = gnd()
    text_contents = [getattr(el, "content", None) for el in sym.elements]
    assert "GND" in text_contents
