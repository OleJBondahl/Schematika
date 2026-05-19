"""Tests for the ConnectorBlock composite symbol."""

import pytest

from schematika.pcb.symbols.connector_block import connector_block


def test_creates_one_port_per_pin() -> None:
    sym = connector_block(ref="J1", pins=("1", "2", "3", "4"))
    assert sorted(sym.ports.keys()) == ["1", "2", "3", "4"]


def test_ports_face_down() -> None:
    sym = connector_block(ref="J1", pins=("1", "2"))
    for port in sym.ports.values():
        assert port.direction.dx == 0
        assert port.direction.dy > 0  # outgoing downward


def test_ref_label_rendered() -> None:
    sym = connector_block(ref="J5", pins=("1", "2"))
    contents = [getattr(el, "content", None) for el in sym.elements]
    assert "J5" in contents


def test_functional_label_rendered_when_provided() -> None:
    sym = connector_block(ref="J1", pins=("1", "2"), functional_label="PSU, Em.Stop")
    contents = [getattr(el, "content", None) for el in sym.elements]
    assert "PSU, Em.Stop" in contents


def test_pin_numbers_rendered_inside_block() -> None:
    sym = connector_block(ref="J1", pins=("1", "2", "3"))
    contents = [getattr(el, "content", None) for el in sym.elements]
    for pin in ("1", "2", "3"):
        assert pin in contents


def test_alphanumeric_pin_ids_supported() -> None:
    sym = connector_block(ref="K1", pins=("A1", "A2"))
    assert sorted(sym.ports.keys()) == ["A1", "A2"]


def test_empty_pins_raises() -> None:
    with pytest.raises(ValueError, match="at least one pin"):
        connector_block(ref="J1", pins=())
